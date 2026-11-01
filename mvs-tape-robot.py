import argparse
import functools
import datetime
import logging
import os
import pathlib
import re
import subprocess
import sys
import time

import urllib.parse
import urllib.request

from enum import Enum, auto


@functools.cache
def compile_regex(regex):
    return re.compile(regex)

class HerculesCommander:
    def __init__(self, url):
        if url.endswith("/"):
            url = url[:-1]
        self.url = url

    def command(self, cmd):
        logging.info("Telling hercules '%s'", cmd)
        query_params = urllib.parse.urlencode({"msgcount": 1, "command": cmd})
        url = f"{self.url}/cgi-bin/api/v1/syslog?{query_params}"

        # 4. Create and send the request
        req = urllib.request.Request(url, method="POST")

        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
            if status != 200:
                logging.warning("status from '%s' = %d", url, status)

def create_tape(volser: str, tape_dir: pathlib.Path, tapefile_type: str = '.het', jobname: None | str = None):
    fn = volser
    if jobname is not None:
        fn += f"_{jobname}"
    fn += "_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fn += tapefile_type
    fn = tape_dir.absolute() / pathlib.Path(fn)
    cmdline = [
        'hetinit',
        '-i',
    ]
    if tapefile_type == '.aws':
        cmdline.append('-d')
    cmdline.extend([str(fn.absolute()), volser.upper()])
    logging.info("Creating tape: %s", " ".join(cmdline))
    subprocess.run(cmdline, shell=False)
    return fn

def find_latest_log_file(file_path: pathlib.Path):
    all_files = list(file_path.glob("mvslog.*.txt"))
    if len(all_files) == 0:
        return None
    all_files.sort()
    return all_files[-1]

def tail_follow(file_path: pathlib.Path):
    current_file_name = None
    check_file = True
    last_file_check_time = time.time()
    f = None
    first = True
    while True:
        try:
            if check_file:
                check_file = False
                latest_log_file = find_latest_log_file(file_path)
                if latest_log_file is not None and current_file_name != latest_log_file:
                    logging.info("Detected new file: %s", latest_log_file)
                    if f is not None:
                        f.close()
                    f = open(latest_log_file, "r")
                    current_file_name = latest_log_file
                    if first:
                        # Move the file pointer to the very end of the file
                        f.seek(0, os.SEEK_END)
                        first = False

            if f is not None:
                line = f.readline()
                if not line:
                    time.sleep(0.1)     # Sleep briefly to save CPU while waiting for data
                    yield None          # give robots a chance to housekeep
                    now = time.time()
                    if now - last_file_check_time > 5:
                        last_file_check_time = now
                        check_file = True
                    continue
                yield line
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt: I'll go quietly. honest...")
            return

class Robot:
    def __init__(self, herc : HerculesCommander | None = None):
        assert herc is not None
        self.herc = herc
        self.logger = logging.getLogger(__class__.__name__)

    def process(self, s : str | None = None):
        pass


class FormRobotState(Enum):
    UNKNOWN = auto()
    NEEDS_SETUP = auto()
    NEEDS_START = auto()
    WAITING = auto()
    PRINTING = auto()
    NEEDS_RESET = auto()
    WAITING_FOR_DRAIN = auto()

class JobInformation:
    jobname: str | bytes
    jobid: str | bytes
    form: str | bytes
    filepath: pathlib.Path

    def format(self, s : str):
        j = {
            "jobname": self.jobname,
            "jobid": self.jobid,
            "form": self.form,
        }
        return s.format(**j)

class PunchJobHandler:
    def handle(self, job_information: JobInformation):
        pass

class PunchFN(PunchJobHandler):
    def handle(self, job_information: JobInformation):
        of = None
        op = None
        with open(job_information.filepath, "r") as f:
            for i, line in enumerate(f):
                line = line.rstrip()
                if i == 0:
                    m = re.search(r'^#\s+(.*)', line)
                    if m:
                        s = m.group(1)
                        ss = job_information.format(s)
                        ss = ss.replace(' ', '')
                        op = job_information.filepath.with_name(ss)
                        logging.info("copying %s to %s", job_information.filepath, op)
                        of = open(op, "w")
                    else:
                        logging.error("file %s has incorrect first line", job_information.filepath)
                        break
                else:
                    print(line, file=of)
        if of is not None:
            of.close()

            if op.suffix in ('.pgm', '.ppm'):
                cmd = ['display', op]

                # Spawn the process completely decoupled from parent I/O streams
                # noinspection bad-argument-type
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Breaks the process group ties on POSIX systems
                )


class FormRobot(Robot):
    def __init__(self,
                 herc: HerculesCommander | None = None,
                 device: str | None = None,
                 output_dir: pathlib.Path | None = None):
        super().__init__(herc)
        assert device is not None
        self.device = device.upper()
        assert output_dir is not None
        self.output_dir = output_dir

        self.cuu = None
        self.t0: dict[str, float | int  | None] = {}
        self.robot_state = FormRobotState.UNKNOWN

        self.job_information: JobInformation | None = None

        self.logger = logging.getLogger(__class__.__name__ + '.' + self.device)
        self.logger.setLevel(logging.INFO)

        self.is_punch = device.startswith('PUN')

        self.handlers: dict[str, PunchJobHandler] = {
            '#FN': PunchFN(),
        }

    def set_robot_state(self, s: FormRobotState):
        if s != self.robot_state:
            self.logger.info("state: %s -> %s", self.robot_state, s)
            self.robot_state = s

    def send_command(self, s):
        self.logger.debug("Called send_command: '%s'", s)
        t0 = self.t0.get(s)
        now = time.time()
        if t0 is None or (now - t0) > 5 or not s.startswith("/$DU,"):
            self.herc.command(s)
            self.t0[s] = now
        else:
            self.logger.debug("...not issuing (too soon)")

    def process(self, s : str | None = None):
        if s is None:
            if self.cuu is None or self.robot_state in (FormRobotState.NEEDS_START, FormRobotState.WAITING_FOR_DRAIN, FormRobotState.UNKNOWN):
                self.send_command(f'/$DU,{self.device}')
            return

        # self.logger.debug("received '%s'", s)

        m = compile_regex(fr'^.*\$HASP000 ({self.device})\s+(?P<cuu>[0-9A-F]{{{3}}})\s+(?P<state>\S+).*\s+F=(?P<f>\S*).*$').match(s)
        if m:
            self.logger.info("processing '%s'", s)

            if self.cuu is None:
                self.cuu = m.group("cuu")
                self.logger.info("device is @ %s", self.cuu)

            device_state = m.group("state")
            forms = m.group("f")

            if device_state == 'ACTIVE':
                self.set_robot_state(FormRobotState.PRINTING)
                return

            if device_state == 'INACTIVE':
                self.set_robot_state(FormRobotState.WAITING)
                return

            if self.robot_state == FormRobotState.WAITING_FOR_DRAIN:
                if device_state == 'DRAINED':
                    if self.job_information is not None:
                        self.herc.command(f'devinit {self.cuu} /dev/null')
                        self.logger.info("Need to post process file %s", self.job_information.filepath)
                        h = self.handlers.get(self.job_information.form[:3])
                        if h is not None:
                            h.handle(self.job_information)
                        else:
                            self.logger.info("File %s, no handler for form %s", self.job_information.filepath, self.job_information.form)
                        self.job_information = None
                    self.robot_state = FormRobotState.NEEDS_SETUP
                else:
                    self.send_command(f"/$P{self.device}")


            if self.robot_state in (FormRobotState.UNKNOWN, FormRobotState.NEEDS_SETUP, FormRobotState.WAITING):
                if forms != "XXXX,AUTOM":
                    self.set_robot_state(FormRobotState.NEEDS_SETUP)
                    # TODO is this a good fix?
                    sysout_class = "2" if self.is_punch else "T"
                    self.send_command(f"/$T{self.device},F=XXXX,F=AUTOM,Q={sysout_class}")
                    return

                # forms are good
                self.set_robot_state(FormRobotState.NEEDS_START)

            if self.robot_state == FormRobotState.NEEDS_START:
                if device_state not in ("INACTIVE", "ACTIVE"):
                    self.send_command(f"/$S{self.device}")
                    self.set_robot_state(FormRobotState.WAITING)
                    return

            return

        m = compile_regex(fr'^.*?(?P<jobid>(?:JOB|STC|TSU)\s+\d+)?\s+\*\$HASP190\s+(?P<jobname>\S+)\s+SETUP -- {self.device}\s+-- F = (?P<form>\S+).*$').match(s)
        if m:
            assert self.job_information is None
            ji = self.job_information = JobInformation()
            self.job_information.jobid = m.group("jobid").replace(" ", "")
            self.job_information.jobname = m.group("jobname")
            self.job_information.form = m.group("form")
            self.job_information.filepath = self.output_dir / f"{ji.jobname}_{ji.jobid}_{ji.form}"


            self.logger.info("processing '%s'", s)
            devinit_cmd = f"devinit {self.cuu} {ji.filepath}"
            if self.is_punch:
                devinit_cmd += ' ascii'
            self.herc.command(devinit_cmd)
            self.herc.command(f'/$S{self.device}')  # send regardless of time

        '''
        handle these seperately. don't need to drain on PAUSED.
        Need to figure out how to devinit * without starting'''
        m = compile_regex(fr'^.*\$HASP(160|175)\s+{self.device}\s+(INACTIVE|PAUSED).*$').match(s)
        if m:
            self.logger.info("processing '%s'", s)
            self.send_command(f'/$P{self.device}')
            self.set_robot_state(FormRobotState.WAITING_FOR_DRAIN)
        return


class TapeRobot(Robot):
    def __init__(self,
                 herc: HerculesCommander | None = None,
                 scratch_dir: pathlib.Path | None = None,
                 tape_dir: pathlib.Path | None = None,
                 smf_tape_dir: pathlib.Path | None = None):
        super().__init__(herc)
        assert scratch_dir is not None
        self.scratch_dir = scratch_dir
        assert tape_dir is not None
        self.tape_dir = tape_dir
        assert smf_tape_dir is not None
        self.smf_tape_dir = smf_tape_dir

    def process(self, s : str | None = None):
        if s is None:
            return
        m = compile_regex(r'^.*(?:IEC502E|IEF234E) (?:K|D|RK|RD|R) (?P<cuu>[0-9A-F]{3,4}),.*$').match(s)
        if m:
            cuu = m.group("cuu")
            # need to filter out non-tape devices
            self.logger.info("need to devinit %s *", cuu)
            self.herc.command(f"devinit {cuu} *")
            return

        m = compile_regex(r'^.*(?:IEC501A|IEF233[AD]) M (?P<cuu>[0-9A-F]{3,4}),(?P<volser>[^,]{6}),[^,]*,(?P<job>[^,]*),.*$').match(s)
        if m:
            self.logger.info("handling '%s'", s)
            cuu = m.group("cuu")
            # need to filter out non-tape devices
            volser = m.group("volser").upper()
            self.logger.info("need to mount volume %s on device %s", volser, cuu)
            if volser == "PRIVAT" or volser == "SCRTCH":
                jobname = m.group("job")
                tapefile = create_tape(volser, tape_dir=self.scratch_dir, jobname=jobname)
            elif volser == "SMFTAP":
                tapefile = create_tape(volser, tape_dir=self.smf_tape_dir, tapefile_type=".aws")
            else:
                candidates = []
                self.logger.info("Looking for %s in %s", volser, self.tape_dir.absolute())
                for g in (f"{volser}*.aws", f"{volser}*.het"):
                    xx = list(self.tape_dir.glob(g, case_sensitive=False))
                    for x in xx:
                        self.logger.debug("%s found %s", g, x)
                        candidates.append(x)
                tapefile = None
                if len(candidates) == 1:
                    tapefile = candidates[0]
                elif len(candidates) == 0:
                    self.logger.warning("Cannot find tape '%s'", volser)
                else:
                    self.logger.warning("Too many choices for tape '%s': %s", volser, candidates)
            if tapefile is not None:
                self.herc.command(f"devinit {cuu} {tapefile}")
            return

        # original worried about IEF455D, but that is only issued in conjunction with IEF233D,
        # which is causing a mount, so we should be ok.
        m = compile_regex(r'^.*(?:IEF455D)\s.*$').match(s)
        if m:
            self.logger.info("Ignoring %s", s)
            return

        m = compile_regex(r'^.*(?:IEC502E|IEF234E|IEC501A|IEF233[AD]).*$').match(s)
        if m:
            self.logger.warning("Should have parsed this, but didn't: %s", s)
            return

        return



# Usage
def main(argv):
    # Set up the parser
    parser = argparse.ArgumentParser(description="hercules mvs 3.8j tape robot")
    parser.add_argument("--mvs", help="path of MVS directory", type=pathlib.Path, required=True)
    parser.add_argument("--url", help="base URL of Hercules", required=True)
    parser.add_argument("--scratch-dir", type=pathlib.Path, help="path to directory of scratch tapes")
    parser.add_argument("--tape-dir", type=pathlib.Path, help="path to directory of tapes")
    parser.add_argument("--smf-tape-dir", type=pathlib.Path, help="path to directory of SMF tapes")
    parser.add_argument("--mvs-logs-dir", type=pathlib.Path, help="path to directory of MVS logs")
    parser.add_argument("--punch-dir", type=pathlib.Path, help="path to directory for punch output")
    parser.add_argument("--print-dir", type=pathlib.Path, help="path to directory for print output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    # Parse arguments passed from the shell script wrapper
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # Forward the exit status (e.g. if --help was requested or validation failed)
        return e.code

    if args.verbose:
        logging.getLogger('').setLevel(logging.DEBUG)

    assert args.mvs.is_dir()

    if args.scratch_dir is None:
        args.scratch_dir = args.mvs.joinpath("scratch_tapes")
    assert args.scratch_dir.is_dir()

    if args.tape_dir is None:
        args.tape_dir = args.mvs.joinpath("tapes")
    assert args.tape_dir.is_dir()

    if args.smf_tape_dir is None:
        args.smf_tape_dir = args.mvs.joinpath("smftapes")
    assert args.smf_tape_dir.is_dir()

    if args.mvs_logs_dir is None:
        args.mvs_logs_dir = args.mvs.joinpath("prt")
    assert args.mvs_logs_dir.is_dir()

    c = HerculesCommander(args.url)
    robots: list[Robot] = []

    robots.append(TapeRobot(herc = c,
                            scratch_dir=args.scratch_dir,
                            tape_dir=args.tape_dir,
                            smf_tape_dir=args.smf_tape_dir))

    # need to change this so each device can have it's own directory?
    # specify devices on cmd line?

    robots.append(FormRobot(herc = c,
                            device = 'PUNCH3',
                            output_dir=args.punch_dir))

    robots.append(FormRobot(herc = c,
                            device = 'PRINTER3',
                            output_dir=args.print_dir))

    for new_line in tail_follow(args.mvs_logs_dir):
        if new_line is not None:
            new_line = new_line.rstrip()
        logging.debug("MVS said: %s", new_line)
        for robot in robots:
            robot.process(new_line)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rc = main(sys.argv[1:])
    sys.exit(rc)
