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
from ctypes import cast


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
                    time.sleep(0.1)  # Sleep briefly to save CPU while waiting for data
                    now = time.time()
                    if now - last_file_check_time > 5:
                        last_file_check_time = now
                        check_file = True
                    continue
                yield line
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt: I'll go quietly. honest...")
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
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    # Parse arguments passed from the shell script wrapper
    try:
        args = parser.parse_args(sys.argv[1:])
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
    for new_line in tail_follow(args.mvs_logs_dir):
        new_line = new_line.rstrip()
        print(new_line)
        m = compile_regex(r'^.*(?:IEC502E|IEF234E) (?:K|D|RK|RD|R) (?P<cuu>[0-9A-F]{3,4}),.*$').match(new_line)
        if m:
            cuu = m.group("cuu")
            # need to filter out non-tape devices
            logging.info("need to devinit %s *", cuu)
            c.command(f"devinit {cuu} *")
            continue

        m = compile_regex(r'^.*(?:IEC501A|IEF233[AD]) M (?P<cuu>[0-9A-F]{3,4}),(?P<volser>[^,]{6}),[^,]*,(?P<job>[^,]*),.*$').match(new_line)
        if m:
            cuu = m.group("cuu")
            # need to filter out non-tape devices
            volser = m.group("volser").upper()
            logging.info("need to mount volume %s on device %s", volser, cuu)
            if volser == "PRIVAT" or volser == "SCRTCH":
                jobname = m.group("job")
                tapefile = create_tape(volser, tape_dir=args.scratch_dir, jobname=jobname)
            elif volser == "SMFTAP":
                tapefile = create_tape(volser, tape_dir=args.smf_tape_dir, tapefile_type=".aws")
            else:
                candidates = []
                logging.info("Looking for %s in %s", volser, args.tape_dir.absolute())
                for g in (f"{volser}*.aws", f"{volser}*.het"):
                    xx = list(args.tape_dir.glob(g, case_sensitive=False))
                    for x in xx:
                        print(x)
                        candidates.append(x)
                tapefile = None
                if len(candidates) == 1:
                    tapefile = candidates[0]
                elif len(candidates) == 0:
                    logging.info("Cannot find tape '%s'", volser)
                else:
                    logging.info("Too many choices for tape '%s': %s", volser, candidates)
            if tapefile is not None:
                c.command(f"devinit {cuu} {tapefile}")
            continue

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rc = main(sys.argv[1:])
    sys.exit(rc)
