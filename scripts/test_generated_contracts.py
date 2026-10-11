#!/usr/bin/env python3
"""License-free generation contracts; simulator checks live in tests/dpi_contract."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


def contract_yaml(struct_mode=True, parameterized=True):
  parameters = "      parameters:\n        - {name: WIDTH, type: int, value: '8'}\n" if parameterized else ""
  data_type = "bit [WIDTH-1:0]" if parameterized else "bit [15:0]"
  agent_params = "[{name: WIDTH, value: '16'}]" if parameterized else "[]"
  return f"""uvmf:
  interfaces:
    bus:
      use_dpi_link: true
      use_struct_bfm: {str(struct_mode).lower()}
      clock: clk
      reset: rst
{parameters}      config_vars:
        - {{name: flag, type: 'bit [7:0]', isrand: false, value: "'0"}}
      transaction_vars:
        - {{name: data, type: '{data_type}', isrand: false, iscompare: true}}
  environments:
    ip:
      agents:
        - {{name: agent0, type: bus, parameters: {agent_params}}}
    soc:
      parameters:
        - {{name: WIDTH, type: int, value: '8'}}
      subenvs:
        - {{name: ip0, type: ip, count: 2, array: true}}
  benches:
    soc:
      top_env: soc
      top_env_params:
        - {{name: WIDTH, value: '16'}}
      active_passive:
        - {{path: environment.ip0_0.agent0, value: PASSIVE}}
        - {{path: environment.ip0_1.agent0, value: PASSIVE}}
"""


def generate(root, struct_mode=True, parameterized=True):
  root.mkdir(parents=True, exist_ok=True)
  config = root / "contract.yaml"
  config.write_text(contract_yaml(struct_mode, parameterized), encoding="utf-8")
  output = root / "generated"
  result = subprocess.run([
    sys.executable, str(REPO_ROOT / "scripts/yaml2uvmf.py"), "-q", "-d", str(output),
    str(config)
  ], text=True, capture_output=True, check=False)
  if result.returncode:
    raise AssertionError(result.stdout + result.stderr)
  return output


class GeneratedContractTest(unittest.TestCase):
  def assert_function_end_labels(self, text):
    # Inspect complete declarations: return types can span multiple lines and
    # contain parameter argument lists before the function's own argument list.
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)
    functions = list(re.finditer(
      r"(?ms)^\s*(?:virtual\s+)?function\b(?P<signature>.*?);"
      r".*?^\s*endfunction\s*:\s*(?P<label>[A-Za-z_]\w*)", code))
    declaration_count = len(re.findall(r"(?m)^\s*(?:virtual\s+)?function\b", code))
    self.assertGreater(declaration_count, 0)
    self.assertEqual(len(functions), declaration_count)
    for function in functions:
      names = re.findall(r"([A-Za-z_]\w*)\s*\(", function["signature"])
      self.assertTrue(names, function["signature"])
      self.assertEqual(function["label"], names[-1], function["signature"])

  def test_dpi_driver_monitor_contracts_in_all_modes(self):
    for struct_mode in (False, True):
      for parameterized in (False, True):
        with self.subTest(struct_mode=struct_mode, parameterized=parameterized):
          with tempfile.TemporaryDirectory() as tmp:
            output = generate(Path(tmp), struct_mode, parameterized)
            package = output / "verification_ip/interface_packages/bus_pkg"
            source = lambda name: (package / "src" / name).read_text(encoding="utf-8")
            self.assert_function_end_labels(source("bus_configuration.sv"))
            callback = source("bus_tc.cpp")
            self.assertNotIn("extern void bus_pkg_notify_transaction", callback)
            self.assertIn("bus_dpi_notify_input<decltype(&bus_pkg_notify_transaction)>::type bit_vec_in", callback)
            driver_proxy = source("bus_driver_proxy.sv")
            driver_bfm = source("bus_driver_bfm.sv")
            monitor_proxy = source("bus_monitor_proxy.sv")
            monitor_bfm = source("bus_monitor_bfm.sv")
            for method in ("initiate_and_get_response", "respond_and_wait_for_next_transfer"):
              self.assertIn("task " + method, driver_proxy)
              self.assertIn("bfm." + method, source("bus_driver.sv"))
            for method in ("bfm_access", "response"):
              self.assertIn("task automatic " + method, driver_bfm)
            self.assertIn("function automatic void do_response_ready", driver_bfm)
            self.assertIn("bfm.configure(cfg.active_passive, cfg.initiator_responder,", source("bus_driver.sv"))
            self.assertIn("bfm.configure(cfg.active_passive, cfg.initiator_responder,", source("bus_monitor.sv"))
            for bfm in (driver_bfm, monitor_bfm):
              self.assertIn("{act_pass, initiator_responder, flag}", bfm)
              self.assertNotIn("bit [7:0] flag;\n    {act_pass", bfm)
            pkg_text = (package / "bus_pkg.sv").read_text(encoding="utf-8")
            self.assertIn("bus_monitor_proxy_base proxy_h", pkg_text)
            self.assertIn("$cast(proxy_h, pool_h.get(path))", pkg_text)
            self.assertNotIn("bus_monitor_proxy#()::get", pkg_text)
            if parameterized:
              self.assertIn("uvm_object_param_utils(bus_driver_proxy", driver_proxy)
            else:
              self.assertIn("`uvm_object_utils(bus_driver_proxy)", driver_proxy)
            if struct_mode:
              self.assertIn("notify_transaction(monitored)", monitor_proxy)
              self.assertIn("C_bus_notify_transaction(bus_monitor_struct)", monitor_bfm)
            else:
              self.assertIn("monitored.data", monitor_proxy)
              self.assertIn("monitored_trans.data", monitor_bfm)

  def test_dpi_imports_declare_named_vector_arguments(self):
    imports = (REPO_ROOT / "common/dpi_link_pkg/dpi_link_uvmf_imports.svh").read_text(
      encoding="utf-8")
    declarations = re.findall(
      r'import "DPI-C" context (?:function void|task) (\w+)\((.*?)\);',
      imports, flags=re.S)
    expected_vectors = {"C_configure": "input", "C_do_response_ready": "input",
                        "C_access": "inout", "C_response": "inout",
                        "C_wait_for_num_clocks": "input"}
    self.assertEqual(len(declarations), 8)
    for name, arguments in declarations:
      arguments = [argument.strip() for argument in arguments.split(",")]
      self.assertEqual(arguments[0], "input string path", name)
      if name in expected_vectors:
        self.assertEqual(len(arguments), 2, name)
        self.assertRegex(arguments[1], r"^" + expected_vectors[name] +
                         r"\s+c_bit_array_t\s+[A-Za-z_]\w*$", name)
      else:
        self.assertEqual(len(arguments), 1, name)

  def test_dpi_task_bridge_retains_simulator_header_return_abi(self):
    bridge = (REPO_ROOT / "common/dpi_link_pkg/uvmf_tc.cpp").read_text(encoding="utf-8")
    self.assertIn('#include "dpiheader.h"', bridge)
    self.assertNotRegex(bridge, r"\bextern\s+(?:int|void)\s+\w+\s*\(")
    # Captured VCS exports use const inputs and void task results; captured
    # Xcelium exports use mutable inputs and int results. Keep the selected
    # simulator's declarations authoritative rather than selecting an ABI here.
    for exported in ("configure", "do_response_ready", "wait_for_num_clocks"):
      self.assertIn("DpiInput<decltype(&" + exported + ")>::type bit_vec", bridge)
    self.assertNotIn("const_cast", bridge)
    for exported, arguments in (("bfm_access", "bit_vec, bit_vec"),
                                ("response", "bit_vec, bit_vec"),
                                ("wait_for_reset", ""),
                                ("wait_for_num_clocks", "bit_vec")):
      call = exported + "(" + arguments + ")"
      self.assertIn("decltype(" + call + ")", bridge)
      self.assertIn("return " + call + ";", bridge)

  def test_array_subenvironment_copies_elements_and_top_sequence_parameters(self):
    with tempfile.TemporaryDirectory() as tmp:
      output = generate(Path(tmp))
      package = output / "verification_ip/environment_packages/soc_env_pkg/src"
      config = (package / "soc_env_configuration.sv").read_text(encoding="utf-8")
      self.assertIn("for (int j = 0; j < 1; j++) begin", config)
      self.assertIn("interface_names[0 + i * 1 + j]", config)
      self.assertIn("interface_activity[0 + i * 1 + j]", config)
      self.assertNotRegex(config, r"interface_names\[[^]\n]*i[^]\n]*:")
      test = (output / "project_benches/soc/tb/tests/src/test_top.sv").read_text(encoding="utf-8")
      sequence = test[test.index("typedef soc_env_sequence_base"):test.index("soc_env_sequence_base_t;")]
      self.assertIn(".WIDTH(16)", sequence)


if __name__ == "__main__":
  unittest.main()
