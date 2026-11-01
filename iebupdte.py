#!/usr/bin/env python

import argparse
import logging
import pathlib
import sys

class IEBUPDTEJob:
  def __init__(self, job_name : str, pds_name : str):
    self.jcl = []
    # 1. Job Card
    self.jcl.append(f"//{job_name.upper():<8} JOB (ACCT),'CREATE MEMBER',CLASS=A,MSGCLASS=X")
    
    # 2. Execute IEBUPDTE Step
    # PARM=NEW indicates we are creating/updating members
    self.jcl.append(f"//UPDATE   EXEC PGM=IEBUPDTE,PARM=NEW")
    
    # 3. Define DD Statements
    self.jcl.append(f"//SYSPRINT DD SYSOUT=*")
    self.jcl.append(f"//SYSUT2   DD DSN={pds_name.upper()},DISP=SHR")
    
    # 4. SYSIN Control Statements
    self.jcl.append(f"//SYSIN    DD DATA,DLM='><'")
    
  def add_lines(self, member_name, content_lines):
    self.jcl.append(f"./       ADD   NAME={member_name[:8].upper()}")
    
    # 5. Insert Member Content
    for line in content_lines:
      # Mainframe standard text lines are usually 80 characters max
      self.jcl.append(line[:80])
      
  def add_file(self, member_name, filename):
    with open(filename, 'r') as f:
      self.add_lines(member_name, [line.rstrip() for line in f]
)
      
  def write_jcl(self, filename):
    # 6. End of Data Delimiter
    self.jcl.append("./       ENDUP")
    self.jcl.append("><")
    self.jcl.append("//")
    with open(filename, 'w') as f:
      f.write("\n".join(self.jcl))
      
def main(argv):
  # Set up the parser
  parser = argparse.ArgumentParser(description="dump SMF tape")
  parser.add_argument("-j", "--job", help="name of job", default="IEBUPDTE")
  parser.add_argument("-d", "--dsn", help="name of DSN", required=True)
  parser.add_argument("-m", "--member", type=pathlib.Path, nargs='+', help="members to send")
  parser.add_argument("-o", "--output", type=pathlib.Path, help="output file", required=True)
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

  try:
    args = parser.parse_args(sys.argv[1:])
  except SystemExit as e:
    return e.code

  if args.verbose:
    logging.getLogger('').setLevel(logging.DEBUG)

  logging.info("args: %s", args)

  i = IEBUPDTEJob(job_name = args.job, pds_name = args.dsn)
  for fn in args.member:
    logging.info("Processing %s", fn)
    # need to figure out the member name
    member = fn.stem
    i.add_file(member, fn)
  i.write_jcl(args.output)
  return 0
  
if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  rc = main(sys.argv[1:])
  sys.exit(rc)
