#! /usr/bin/env python3

"""CLI regressions for YAML metadata, DPI declarations and parameter scopes."""

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO_ROOT / "templates" / "python" / "python3"))
import yaml


class GeneratorInputsTest(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.root = Path(temporary.name)
    self.case_index = 0

  def generate(self,data,*args):
    self.case_index += 1
    config = self.root / ("input{0}.yaml".format(self.case_index))
    output = self.root / ("output{0}".format(self.case_index))
    config.write_text(yaml.safe_dump({"uvmf":data},sort_keys=False),encoding="utf-8")
    result = subprocess.run(
      [sys.executable,str(REPO_ROOT / "scripts" / "yaml2uvmf.py"),
       "-q","-d",str(output),*args,str(config)],
      text=True,capture_output=True,check=False,
    )
    return result,output

  def generated(self,data,*args):
    result,output = self.generate(data,*args)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    return output

  def mixed_components(self):
    utilities = {}
    for name in ("A","B"):
      utilities[name] = {
        "type":"predictor",
        "analysis_ports":[{"name":"out"+name,"type":"uvm_sequence_item"}],
        "analysis_exports":[{"name":"in"+name,"type":"uvm_sequence_item"}],
      }
    return {
      "util_components":utilities,
      "environments":{"e":{
        "analysis_components":[
          {"name":"a1","type":"A"},
          {"name":"b1","type":"B"},
          {"name":"a2","type":"A","extdef":False},
        ],
        "analysis_ports":[{
          "name":"out","trans_type":"uvm_sequence_item","connected_to":"a2.outA",
        }],
        "analysis_exports":[{
          "name":"in","trans_type":"uvm_sequence_item","connected_to":"a2.inA",
        }],
      }},
    }

  def test_repeated_component_uses_its_own_port_and_export_definitions(self):
    output = self.generated(self.mixed_components())
    source = (output / "verification_ip/environment_packages/e_env_pkg/src/e_environment.sv").read_text(encoding="utf-8")
    self.assertIn("a2.outA.connect(out);",source)
    self.assertIn("in.connect(a2.inA);",source)

  def test_repeated_component_rejects_another_types_port_and_export(self):
    for field,endpoint in (("analysis_ports","a2.outB"),("analysis_exports","a2.inB")):
      with self.subTest(field=field):
        data = self.mixed_components()
        data["environments"]["e"][field][0]["connected_to"] = endpoint
        result,_ = self.generate(data)
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn("not a valid TLM",result.stderr)

  def dpi_definition(self):
    return {
      "name":"dpi_test","files":[],"exports":["tick_export"],
      "imports":[
        {"name":"first_no_args","c_return_type":"void","sv_return_type":"void"},
        {"name":"second_explicit_args","c_return_type":"void","sv_return_type":"void",
         "c_args":"int value", "sv_args":[{"name":"value","type":"int","dir":"input"}]},
      ],
    }

  def test_environment_dpi_exports_and_optional_import_arguments(self):
    for with_agent in (False,True):
      with self.subTest(with_agent=with_agent):
        data = {"environments":{"e":{"dpi_define":self.dpi_definition()}}}
        if with_agent:
          data["interfaces"] = {"bus":{
            "clock":"clk","reset":"rst",
            "transaction_vars":[{"name":"data","type":"bit","isrand":False,"iscompare":True}],
          }}
          data["environments"]["e"]["agents"] = [{"name":"agent0","type":"bus"}]
        output = self.generated(data)
        archive = output / "verification_ip/environment_packages/e_env_pkg/yaml/e_environment.yaml"
        dpi = yaml.safe_load(archive.read_text(encoding="utf-8"))["uvmf"]["environments"]["e"]["dpi_define"]
        self.assertEqual(dpi["exports"],["tick_export"])
        self.assertEqual([item["name"] for item in dpi["imports"]],
                         ["first_no_args","second_explicit_args"])
        self.assertEqual(dpi["imports"][0]["c_args"],"")
        sources = "\n".join(path.read_text(encoding="utf-8") for path in output.rglob("*.sv"))
        for name in ("first_no_args","second_explicit_args"):
          self.assertIn(name,sources)

  def test_interface_dpi_optional_import_arguments_preserve_later_imports(self):
    output = self.generated({"interfaces":{"bus":{
      "clock":"clk","reset":"rst","dpi_define":self.dpi_definition(),
      "transaction_vars":[{"name":"data","type":"bit","isrand":False,"iscompare":True}],
    }}})
    archive = output / "verification_ip/interface_packages/bus_pkg/yaml/bus_interface.yaml"
    dpi = yaml.safe_load(archive.read_text(encoding="utf-8"))["uvmf"]["interfaces"]["bus"]["dpi_define"]
    self.assertEqual([item["name"] for item in dpi["imports"]],
                     ["first_no_args","second_explicit_args"])
    self.assertEqual(dpi["imports"][0]["c_args"],"")
    source = (output / "verification_ip/interface_packages/bus_pkg/bus_pkg.sv").read_text(encoding="utf-8")
    for name in ("first_no_args","second_explicit_args"):
      self.assertIn(name,source)

  def parameter_input(self,parent_parameters,value,parameter_type="int"):
    return {
      "global":{"elaborate_bfm_parameters":True},
      "interfaces":{"bus":{
        "clock":"clk","reset":"rst",
        "parameters":[{"name":"VALUE","type":parameter_type,"value":"1"}],
        "transaction_vars":[{"name":"data","type":"bit","isrand":False,"iscompare":True}],
      }},
      "environments":{"soc":{
        "parameters":[{"name":name,"type":"int","value":expression}
                      for name,expression in parent_parameters],
        "agents":[{"name":"agent0","type":"bus","parameters":[{"name":"VALUE","value":value}]}],
      }},
      "benches":{"soc":{"top_env":"soc"}},
    }

  def parameter_overrides(self,data):
    output = self.generated(data)
    source = (output / "project_benches/soc/tb/testbench/hdl_top.sv").read_text(encoding="utf-8")
    return re.findall(r"\.VALUE\((.*)\)",source)

  def test_parameter_identifier_overlap_is_not_a_substring_replacement(self):
    values = self.parameter_overrides(self.parameter_input(
      [("WIDTH","8"),("ADDR_WIDTH","32")],"ADDR_WIDTH"))
    self.assertTrue(values)
    self.assertEqual(set(values),{"32"})

  def test_parameter_expressions_keep_precedence_and_resolve_dependencies(self):
    for parameters in (
        [("WIDTH","ADDR_WIDTH + 1"),("ADDR_WIDTH","3")],
        [("ADDR_WIDTH","3"),("WIDTH","ADDR_WIDTH + 1")]):
      with self.subTest(parameters=parameters):
        values = self.parameter_overrides(self.parameter_input(parameters,"2 * WIDTH"))
        self.assertTrue(values)
        self.assertEqual(set(values),{"2 * (3 + 1)"})

  def test_parameter_substitution_preserves_strings_literals_and_qualified_names(self):
    for expression in ('"WIDTH"',"32'hdead", "pkg::WIDTH", "WIDTH_MEMBER", "`WIDTH", r"\WIDTH "):
      with self.subTest(expression=expression):
        values = self.parameter_overrides(self.parameter_input(
          [("WIDTH","8"),("dead","9")],expression))
        self.assertTrue(values)
        self.assertEqual(set(values),{expression})

  def test_type_parameter_override_retains_type_syntax(self):
    data = self.parameter_input([("T","bit")],"T",parameter_type="type")
    data["environments"]["soc"]["parameters"][0]["type"] = "type"
    data["benches"]["soc"]["top_env_params"] = [{"name":"T","value":"int unsigned"}]
    values = self.parameter_overrides(data)
    self.assertTrue(values)
    self.assertEqual(set(values),{"int unsigned"})

  def test_parameter_cycle_reports_a_user_error(self):
    result,_ = self.generate(self.parameter_input(
      [("WIDTH","ADDR_WIDTH"),("ADDR_WIDTH","WIDTH")],"WIDTH"))
    self.assertNotEqual(result.returncode,0)
    self.assertIn("Cyclic parameter reference",result.stderr)

  def test_external_analysis_component_archive_roundtrips(self):
    output = self.generated({"environments":{"e":{"analysis_components":[{
      "name":"observer","type":"external_observer","extdef":True,
    }]}}})
    archive = output / "verification_ip/environment_packages/e_env_pkg/yaml/e_environment.yaml"
    component = yaml.safe_load(archive.read_text(encoding="utf-8"))["uvmf"]["environments"]["e"]["analysis_components"][0]
    self.assertIs(component["extdef"],True)
    roundtrip = self.root / "roundtrip"
    result = subprocess.run(
      [sys.executable,str(REPO_ROOT / "scripts/yaml2uvmf.py"),"-q",
       "--build_existing_components","-d",str(roundtrip),str(archive)],
      text=True,capture_output=True,check=False,
    )
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    generated = roundtrip / "verification_ip/environment_packages/e_env_pkg/src/e_environment.sv"
    source = generated.read_text(encoding="utf-8")
    self.assertIn("typedef external_observer #(",source)
    self.assertIn("observer_t observer;",source)


if __name__ == "__main__":
  unittest.main()
