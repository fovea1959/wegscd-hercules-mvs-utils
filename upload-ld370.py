#!/usr/bin/env python

import argparse
import logging
import pathlib
import sys

def add_lines(f, content_lines):
    if isinstance(content_lines, str):
        content_lines = content_lines.splitlines()
    for s in content_lines:
        if len(s) > 0:
            assert len(s) <= 80
            s = s.rstrip().ljust(80)
            ebcdic_bytes = s.encode("cp037")
            f.write(ebcdic_bytes)


def main(argv):
    # Set up the parser
    parser = argparse.ArgumentParser(description="load ld370 .xmit file to MVS")
    parser.add_argument("-j", "--job", help="name of job", default="IEBUPDTE")
    parser.add_argument("-d", "--dsn", help="name of LOADLIB", required=True)
    parser.add_argument("-o", "--output", type=pathlib.Path, help="output file", required=True)
    parser.add_argument("-x", "--xmit", type=pathlib.Path, help="xmit file", required=True)
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    try:
        args = parser.parse_args(sys.argv[1:])
    except SystemExit as e:
        return e.code

    if args.verbose:
        logging.getLogger('').setLevel(logging.DEBUG)

    logging.info("args: %s", args)

    with open(args.output, 'wb') as f:
        add_lines(f, f"""
//{args.job.upper():<8} JOB (ACCT),'CREATE MEMBER',CLASS=A,MSGCLASS=X
//*-----------------------------------------------------------------*
//RECV370 EXEC RECV370
//XMITIN    DD *
""")

        with open(args.xmit, 'rb') as x:
            while chunk := x.read(80):
                assert len(chunk) == 80
                f.write(chunk)

        add_lines(f, f"""
/*
//XMITOUT   DD DSN=&&XMITOUT,UNIT=SYSDA,DISP=(NEW,PASS),
//             SPACE=(TRK,(30,30,2),RLSE)
//*-----------------------------------------------------------------*
//IEBCOPY EXEC PGM=IEBCOPY
//SYSPRINT  DD SYSOUT=*
//FROM      DD DSN=&&XMITOUT,DISP=(OLD,PASS)
//TO        DD DISP=SHR,
// DSN={args.dsn.upper()}
//SYSUT3    DD UNIT=SYSDA,SPACE=(TRK,(5,5))
//SYSUT4    DD UNIT=SYSDA,SPACE=(TRK,(5,5))
//SYSIN     DD *
  COPY INDD=((FROM,R)),OUTDD=TO
//
""")
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    rc = main(sys.argv[1:])
    sys.exit(rc)
