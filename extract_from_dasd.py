#!/usr/bin/env python3

import argparse
import logging
import pathlib
import re
import subprocess
import sys

def eval_expression(input_string, info):
    code = compile(input_string, "<string>", "eval")
    for name in code.co_names:
        if name not in info:
            raise NameError(f"Use of {name} not allowed")
    rv = eval(code, {"__builtins__": {}}, info)
    logging.info("eval '%s' for %s == %s", input_string, info, rv)
    return rv


class Volumes:
    def __init__(self, mvs_directory: pathlib.Path):
        self.dasd_files = {}
        self.shadow_files = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self.datasets = {}

        self.logger.info("mvs directory: %s", mvs_directory)
        for level1 in mvs_directory.iterdir():
            if level1.is_dir():
                if level1.stem.startswith("dasd") or level1.stem.startswith("shadow"):
                    for level2 in level1.iterdir():
                        if level2.is_file():
                            sx = level2.suffix
                            if sx == '.sf':
                                shadow_stem = level2.stem.lower()
                                volname, _ = shadow_stem.split("-", 2)
                                self.shadow_files[volname] = level2
                            else:
                                volname = level2.stem.lower()
                                self.dasd_files[volname] = level2

    def datasets_on_volume(self, volume_name: str):
        rv = self.datasets.get(volume_name.lower())
        if rv is None:
            self.datasets[volume_name.lower()] = rv = {}
            cmdline = [
                "/home/wegscd/hyperion-4.9/bin/dasdls",
                "-hdr",
                "-info",
            ]

            cmdline.extend(self.cmd_line(volume_name))
            cp = subprocess.run(cmdline, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True)
            logging.info("args: %s", cp.args)

            into_dsns = False
            for l in cp.stdout.splitlines():
                if l.strip() == '':
                    continue
                logging.debug("-- %s", l)
                if l.startswith("Dsname"):
                    into_dsns = True
                    continue
                if into_dsns:
                    if l.startswith("End of dasdls"):
                        into_dsns = False
                        continue
                    dsn, _, dsorg, recfm, lrecl, _ = l.split(None, 5)
                    info = { "dsorg": dsorg, "recfm": recfm }
                    if 'F' in recfm:
                        info['lrecl'] = int(lrecl)
                    else:
                        info['lrecl'] = 0
                    self.logger.debug("^^ %s", info)
                    rv[dsn.lower()] = info

        return rv

    def filtered_datasets_on_volume(self, volume_name: str, spec: str):
        rv = {}
        dss = self.datasets_on_volume(volume_name)
        p = re.compile(spec)
        for dsn, info in dss.items():
            m = p.fullmatch(dsn)
            self.logger.info ("match result for %s %s: %s", spec, dsn, m)
            if m:
                rv[dsn] = info
        return rv

    def cmd_line(self, volume_name: str):
        rv = []

        volume_path = self.dasd_files.get(volume_name.lower())
        assert volume_path is not None, f"Cannot find the DASD for volume {volume_name}"
        rv.append(str(volume_path))

        sf_path = self.shadow_files.get(volume_name.lower())
        if sf_path is not None:
            rv.append(f'sf={str(sf_path)}')

        return rv

def main(argv):
    # Set up the parser
    parser = argparse.ArgumentParser(description="Unload datasets from Hercules DASD")
    parser.add_argument("--mvs", help="path of MVS directory", required=True)
    parser.add_argument("--output", help="path of output directory", required=True)
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("description", help="file of volser:dsn")

    # Parse arguments passed from the shell script wrapper
    try:
        args = parser.parse_args(sys.argv[1:])
    except SystemExit as e:
        # Forward the exit status (e.g. if --help was requested or validation failed)
        return e.code

    if args.verbose:
        logging.getLogger('').setLevel(logging.DEBUG)

    volumes = Volumes(pathlib.Path(args.mvs))
    #print(json.dumps(dasd_files, indent=1, default=str))
    #print(json.dumps(shadow_files, indent=1, default=str))

    with open(args.description, "r") as f:
        for d in f:
            d = d.strip()
            if len(d) == 0:
                continue
            if d.startswith('*'):
                continue
            volume_name, dsn_spec = d.split(':')
            volume_name = volume_name.lower()
            dsn_spec = dsn_spec.lower()

            all_dsns = volumes.filtered_datasets_on_volume(volume_name, dsn_spec)

            hit = False

            for dsn, info in all_dsns.items():
                eee = eval_expression("dsorg == 'PO' and 'F' in recfm and lrecl == 80", info)
                if info['dsorg'] == 'PO' and 'F' in info['recfm'] and info['lrecl'] == 80:
                    hit = True
                    logging.info("processing PDS %s:%s", volume_name, dsn)

                    output_directory_path = pathlib.Path(args.output) / volume_name / dsn
                    output_directory_path.mkdir(parents=True, exist_ok=True)

                    cmdline = [
                        "/home/wegscd/hyperion-4.9/bin/dasdpdsu",
                    ]

                    cmdline.extend(volumes.cmd_line(volume_name))

                    cmdline.extend([
                        dsn.upper(),
                        'ASCII',
                        str(output_directory_path) + "/",
                    ])
                    logging.debug("%s", cmdline)
                    cp = subprocess.run(cmdline, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True)
                    logging.info("args: %s", cp.args)
                    for l in cp.stdout.splitlines():
                        logging.debug("-- %s", l)

                else:
                    logging.info("%s %s matched, but flunked attribute filter", dsn, info)
                    continue

            if not hit:
                logging.warning("no hits for DSN %s on volume %s", dsn_spec, volume_name)

    # print(json.dumps(volumes.datasets, indent=1))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rc = main(sys.argv[1:])
    sys.exit(rc)
