#!/usr/bin/env python3
"""Generate an isolated real-UVM/DPI fixture; no simulator is run here."""
from pathlib import Path
import argparse
import json
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from test_generated_contracts import generate


def replace_custom(path, name, body):
  text = path.read_text(encoding="utf-8")
  pattern = r"(// pragma uvmf custom " + name + r" begin\n).*?(// pragma uvmf custom " + name + r" end)"
  text, count = re.subn(pattern, lambda match: match[1] + body + match[2], text, flags=re.S)
  if count != 1:
    raise AssertionError((path, name, count))
  path.write_text(text, encoding="utf-8")


def prepare(destination, struct_mode, parameterized=True):
  output = generate(destination, struct_mode, parameterized)
  package = output / "verification_ip/interface_packages/bus_pkg"
  source = package / "src"
  driver = source / "bus_driver_bfm.sv"
  if struct_mode:
    initiate = """  task initiate_and_get_response(input bus_initiator_s initiated,
      output bus_responder_s responded);
    @(posedge clk_i);
    responded.data = initiated.data ^ 16'h5a5a;
  endtask
"""
    respond = """  task respond_and_wait_for_next_transfer(output bus_initiator_s initiated,
      input bus_responder_s responded);
    @(posedge clk_i);
    initiated.data = responded.data ^ 16'ha5a5;
  endtask
"""
    monitor = """    @(posedge clk_i);
    bus_monitor_struct.data = 16'hc35a;
"""
  else:
    initiate = """  task initiate_and_get_response(bus_transaction#(WIDTH) txn);
    @(posedge clk_i);
    txn.data ^= 16'h5a5a;
  endtask
"""
    respond = """  task respond_and_wait_for_next_transfer(bus_transaction#(WIDTH) txn);
    @(posedge clk_i);
    txn.data ^= 16'ha5a5;
  endtask
"""
    monitor = """    @(posedge clk_i);
    monitored_trans.data = 16'hc35a;
"""
  if not parameterized:
    initiate = initiate.replace("#(WIDTH)", "")
    respond = respond.replace("#(WIDTH)", "")
  replace_custom(driver, "initiate_and_get_response", initiate)
  replace_custom(driver, "respond_and_wait_for_next_transfer", respond)
  replace_custom(source / "bus_monitor_bfm.sv", "do_monitor", monitor)
  tb = Path(__file__).with_name("tb.sv").read_text(encoding="utf-8")
  if not parameterized:
    for name in ("bus_if", "bus_driver_bfm", "bus_monitor_bfm", "bus_driver", "bus_monitor",
                 "bus_transaction"):
      tb = tb.replace(name + " #(.WIDTH(16))", name)
      tb = tb.replace(name + "#(16)", name)
  (destination / "tb.sv").write_text(tb, encoding="utf-8")
  env = output / "verification_ip/environment_packages"
  bench = output / "project_benches/soc/tb"
  sources = [
    REPO_ROOT / "uvmf_base_pkg/uvmf_base_pkg_hdl.sv",
    REPO_ROOT / "uvmf_base_pkg/uvmf_base_pkg.sv",
    REPO_ROOT / "common/dpi_link_pkg/dpi_link_pkg.sv",
    package / "bus_pkg.sv", source / "bus_if.sv", driver, source / "bus_monitor_bfm.sv",
    env / "ip_env_pkg/ip_env_pkg.sv", env / "soc_env_pkg/soc_env_pkg.sv",
    bench / "parameters/soc_parameters_pkg.sv", bench / "tests/soc_tests_pkg.sv",
    destination / "tb.sv",
  ]
  includes = [REPO_ROOT / "uvmf_base_pkg", REPO_ROOT / "common/dpi_link_pkg", package,
              env / "ip_env_pkg", env / "soc_env_pkg", bench / "tests"]
  for path in sources:
    if not path.is_file():
      raise AssertionError(path)
  (destination / "sources.f").write_text("\n".join(
    ["+incdir+" + path.as_posix() for path in includes] + [path.as_posix() for path in sources]
  ) + "\n", encoding="utf-8")
  cpp_sources = [REPO_ROOT / "common/dpi_link_pkg/dpi_link.cpp",
                 REPO_ROOT / "common/dpi_link_pkg/uvmf_tc.cpp", source / "bus_tc.cpp"]
  metadata = {"top": "tb", "pass_sentinel": "GENERATED_CONTRACT_PASS",
              "cpp_sources": [path.as_posix() for path in cpp_sources],
              "cpp_include_dirs": [str(destination.resolve()), str(REPO_ROOT / "common/dpi_link_pkg")],
              "dpi_header": "dpiheader.h", "struct_mode": struct_mode,
              "parameterized": parameterized}
  (destination / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
  return metadata


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("destination", type=Path)
  parser.add_argument("--mode", choices=("struct", "object"), required=True)
  parser.add_argument("--unparameterized", action="store_true")
  args = parser.parse_args()
  print(json.dumps(prepare(args.destination.resolve(), args.mode == "struct", not args.unparameterized), indent=2))
