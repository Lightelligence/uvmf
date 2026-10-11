#!/usr/bin/env python3
"""Compile and run focused UVM regressions with VCS and Xcelium.

Run on an authorized licensed host, through the project's execution workflow.
The license-free generator regressions are part of run_smoke_checks.py.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent


class ContractRunner:
  def __init__(self, work_dir, runmod=None):
    self.work_dir = work_dir.resolve()
    self.work_dir.mkdir(parents=True, exist_ok=False)
    self.runmod = runmod
    self.records = []

  def command(self, tool, args):
    return ([self.runmod, tool, "--"] if self.runmod else []) + [tool] + args

  def record(self, record):
    self.records.append(record)
    (self.work_dir / "summary.json").write_text(
      json.dumps(self.records, indent=2), encoding="utf-8")

  def run(self, name, command, cwd, timeout=300):
    log = self.work_dir / (name + ".log")
    try:
      with log.open("w", encoding="utf-8") as handle:
        result = subprocess.run(command, cwd=cwd, stdout=handle,
                                stderr=subprocess.STDOUT, timeout=timeout)
      rc = result.returncode
    except subprocess.TimeoutExpired:
      rc = 124
    except OSError as error:
      log.write_text(str(error), encoding="utf-8")
      rc = 127
    self.record({"name": name, "argv": command, "rc": rc, "log": str(log)})
    print("{}: rc={}".format(name, rc), flush=True)
    return rc, log

  def verdict(self, name, rc, log, marker):
    text = log.read_text(encoding="utf-8", errors="replace")
    errors = [int(n) for n in re.findall(
      r"(?m)^\s*UVM_(?:ERROR|FATAL)\s*:\s*(\d+)\s*$", text)]
    raw_error = re.search(r"(?m)^\s*UVM_(?:ERROR|FATAL)[^\S\n]+[^:\s]", text)
    failed = (rc != 0 or marker not in text or any(errors) or raw_error is not None
              or "CONTRACT_TIMEOUT" in text or "CONTRACT_FAIL" in text)
    self.record({"name": name + "-verdict", "rc": int(failed), "marker": marker,
                 "uvm_error_fatal_counts": errors})
    return not failed

  def simulate(self, name, simulator, sources, includes, top, marker,
               sim_args=(), compile_args=()):
    directory = self.work_dir / name
    directory.mkdir()
    incargs = ["+incdir+" + str(p) for p in includes]
    if simulator == "vcs":
      executable = directory / "simv"
      args = ["-full64", "-sverilog", "-ntb_opts", "uvm-1.2", "-timescale=1ns/1ps",
              "-top", top, *incargs, *(str(p) for p in sources),
              *compile_args, "-o", str(executable)]
      rc, _ = self.run(name + "-compile", self.command("vcs", args), directory)
      if rc:
        return False
      command = ([self.runmod, "vcs", "--"] if self.runmod else [])
      rc, log = self.run(name + "-run", command + [str(executable), *sim_args], directory,
                         timeout=120)
    else:
      args = ["-64bit", "-sv", "-uvm", "-timescale", "1ns/1ps", "-top", top,
              *incargs, *(str(p) for p in sources), *compile_args, *sim_args]
      rc, log = self.run(name + "-run", self.command("xrun", args), directory)
    return self.verdict(name, rc, log, marker)

  def scoreboard(self, simulator):
    fixture = REPO_ROOT / "scripts/tests/scoreboard_contract"
    return self.simulate("scoreboard-" + simulator, simulator,
      [fixture / "scoreboard_contract_pkg.sv", fixture / "tb.sv"],
      [REPO_ROOT / "uvmf_base_pkg/src", fixture], "tb", "SCOREBOARD_CONTRACT_PASS",
      ["+UVM_TESTNAME=scoreboard_contract_test"])

  def generated(self, simulator, mode, parameterized):
    name = "generated-{}-{}-{}".format(mode,
      "parameterized" if parameterized else "plain", simulator)
    fixture = self.work_dir / (name + "-input")
    prepare_args = [sys.executable,
      str(REPO_ROOT / "scripts/tests/dpi_contract/prepare.py"), str(fixture), "--mode", mode]
    if not parameterized:
      prepare_args.append("--unparameterized")
    rc, _ = self.run(name + "-generate", prepare_args, REPO_ROOT)
    if rc:
      return False
    metadata = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    lines = (fixture / "sources.f").read_text(encoding="utf-8").splitlines()
    includes = [Path(line[len("+incdir+"):]) for line in lines if line.startswith("+incdir+")]
    sources = [Path(line) for line in lines if line and not line.startswith("+incdir+")]
    cpp_sources = metadata["cpp_sources"]
    cflags = ["-I" + str(path) for path in metadata["cpp_include_dirs"]]
    cflags.extend(["-std=c++11", "-Werror=return-type"])
    header = fixture / metadata["dpi_header"]
    if simulator == "vcs":
      # VCS emits vc_hdrs.h before compiling C++; retain the bridge's header name
      # through an include of those real simulator-generated declarations.
      generated_header = self.work_dir / name / "vc_hdrs.h"
      header.write_text('#include "' + generated_header.as_posix() + '"\n', encoding="utf-8")
      compile_args = list(cpp_sources)
      # Keep each flag separate: environment launchers may split spaced arguments.
      for flag in cflags:
        compile_args.extend(["-CFLAGS", flag])
      compile_args.extend(["-LDFLAGS", "-lstdc++"])
    else:
      generated_header = header
      compile_args = ["-dpi", "-dpiheader", str(header)]
      compile_args.extend("-Wcxx," + flag for flag in cflags)
      compile_args.extend(["-Wld,-lstdc++", "-cpost", *cpp_sources, "-end"])
    passed = self.simulate(name, simulator, sources, includes, metadata["top"],
                           metadata["pass_sentinel"], compile_args=compile_args)
    header_ok = generated_header.is_file() and generated_header.stat().st_size > 0
    self.record({"name": name + "-dpi-header", "rc": int(not header_ok),
                 "path": str(generated_header)})
    return passed and header_ok


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--work-dir", type=Path, required=True,
                      help="New isolated directory for compiler output and logs")
  parser.add_argument("--runmod", help="Optional project tool-environment launcher")
  parser.add_argument("--simulators", nargs="+", choices=("vcs", "xcelium"),
                      default=["vcs", "xcelium"])
  args = parser.parse_args()
  if args.work_dir.exists():
    parser.error("--work-dir must not already exist")
  runner = ContractRunner(args.work_dir, args.runmod)
  results = []
  for simulator in args.simulators:
    results.append(runner.scoreboard(simulator))
    for mode in ("struct", "object"):
      for parameterized in (True, False):
        results.append(runner.generated(simulator, mode, parameterized))
  return 0 if all(results) else 1


if __name__ == "__main__":
  sys.exit(main())
