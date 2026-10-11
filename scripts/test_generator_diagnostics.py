#! /usr/bin/env python3

"""Subprocess contracts for generator diagnostics and preflight validation."""

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO_ROOT / "templates" / "python" / "python3"))
import yaml


class GeneratorDiagnosticsTest(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.root = Path(temporary.name)
    self.case_index = 0

  def data(self):
    return {"uvmf":{
      "interfaces":{"bus":{
        "clock":"clk","reset":"rst",
        "parameters":[{"name":"WIDTH","type":"int","value":"8"}],
        "transaction_vars":[{
          "name":"data","type":"bit [WIDTH-1:0]","isrand":False,"iscompare":True,
        }],
      }},
      "environments":{"soc":{"agents":[{"name":"agent0","type":"bus"}]}},
      "benches":{"soc":{"top_env":"soc"}},
    }}

  def run_cli(self,data,*args,output=None):
    self.case_index += 1
    config = self.root / "input{0}.yaml".format(self.case_index)
    if isinstance(data,bytes):
      config.write_bytes(data)
    else:
      text = data if isinstance(data,str) else yaml.safe_dump(data,sort_keys=False)
      config.write_text(text,encoding="utf-8")
    if output is None:
      output = self.root / "output{0}".format(self.case_index)
    result = subprocess.run(
      [sys.executable,"-B",str(REPO_ROOT / "scripts" / "yaml2uvmf.py"),
       "-q","-d",str(output),*args,str(config)],
      cwd=str(self.root),text=True,capture_output=True,check=False,
    )
    return result,output,config

  def assert_error(self,result,*messages):
    self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertIn("ERROR:",result.stderr)
    self.assertNotIn("Traceback",result.stdout+result.stderr)
    for message in messages:
      self.assertIn(message.lower(),result.stderr.lower())

  def assert_success(self,result):
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertNotIn("Traceback",result.stdout+result.stderr)

  def assert_no_output(self,output):
    self.assertFalse(output.exists(),"Validation unexpectedly wrote "+str(output))

  def test_known_user_error_uses_stderr_without_traceback(self):
    data = self.data()
    data["uvmf"]["benches"]["soc"]["top_env"] = "missing_environment"
    result,output,_ = self.run_cli(data)
    self.assert_error(result,"missing_environment")
    self.assert_no_output(output)

  def test_debug_reports_input_stages_and_selected_simulator(self):
    result,output,config = self.run_cli(self.data(),"--debug","--simulator","xcelium")
    self.assert_success(result)
    self.assertTrue(output.is_dir())
    self.assertIn("DEBUG:",result.stderr)
    self.assertIn(str(config.resolve()),result.stderr)
    for stage in ("pars","validat","generat","xcelium"):
      self.assertIn(stage,result.stderr.lower())

  def test_malformed_yaml_reports_source_location_without_output(self):
    result,output,config = self.run_cli("uvmf:\n  environments: [unterminated\n")
    self.assert_error(result,config.name,"line")
    self.assert_no_output(output)

  def test_duplicate_explicit_yaml_keys_report_location(self):
    for text in (
      "uvmf:\n  environments: {}\n  environments: {}\n",
      "uvmf:\n  interfaces:\n    bus:\n      clock: clk\n      clock: other_clk\n",
    ):
      with self.subTest(text=text):
        result,output,config = self.run_cli(text)
        self.assert_error(result,"Duplicate YAML key",config.name,"line")
        self.assert_no_output(output)

  def test_yaml_merge_anchor_allows_explicit_override(self):
    text = """uvmf:
  interfaces:
    bus:
      <<: &defaults
        clock: default_clk
        reset: rst
      clock: clk
      transaction_vars:
        - {name: data, type: bit, isrand: false, iscompare: true}
"""
    result,output,_ = self.run_cli(text,"--check")
    self.assert_success(result)
    self.assert_no_output(output)

  def test_scalar_environment_and_subenvironment_shapes_report_owning_path(self):
    for data,path,shape in (
      ({"uvmf":{"environments":{"soc":"scalar"}}},"environments.soc","mapping"),
      ({"uvmf":{"environments":{"soc":{"subenvs":"scalar"}}}},"environments.soc.subenvs","list"),
      ({"uvmf":{"environments":{"soc":{"subenvs":["scalar"]}}}},"environments.soc.subenvs[0]","mapping"),
    ):
      with self.subTest(path=path):
        result,output,_ = self.run_cli(data,"--check")
        self.assert_error(result,path,shape)
        self.assert_no_output(output)

  def test_unknown_option_fails_before_creating_output(self):
    result,output,_ = self.run_cli(self.data(),"--simulatr","vcs")
    self.assert_error(result,"--simulatr","option")
    self.assert_no_output(output)

  def test_merge_only_flags_require_merge_source(self):
    for option in ("--merge_debug","--merge_verbose","--merge_skip_missing_blocks"):
      with self.subTest(option=option):
        result,output,_ = self.run_cli(self.data(),option)
        self.assert_error(result,option,"requires --merge_source")
        self.assert_no_output(output)

  def test_missing_merge_source_fails_before_creating_output(self):
    output = self.root / "missing_merge_source"
    result,_,_ = self.run_cli(self.data(),"--merge_source",str(output),output=output)
    self.assert_error(result,"merge_source","exist")
    self.assert_no_output(output)
    self.assertFalse(list(self.root.glob(output.name+"_bak_*")))

  def test_check_and_clean_cannot_be_combined(self):
    result,output,_ = self.run_cli(self.data(),"--check","--clean")
    self.assert_error(result,"cannot combine","--check","--clean")
    self.assert_no_output(output)

  def test_interface_boolean_typos_fail_without_output(self):
    for field in ("use_dpi_link","gen_inbound_streaming_driver"):
      with self.subTest(field=field):
        data = self.data()
        data["uvmf"]["interfaces"]["bus"][field] = "ture"
        result,output,_ = self.run_cli(data,"--check")
        self.assert_error(result,field)
        self.assert_no_output(output)

  def test_interface_boolean_native_and_string_spellings_are_accepted(self):
    for value in (True,False,"True","False"):
      with self.subTest(value=value):
        data = self.data()
        data["uvmf"]["interfaces"]["bus"].update({
          "use_dpi_link":value,"gen_inbound_streaming_driver":value,
        })
        result,output,_ = self.run_cli(data,"--check")
        self.assert_success(result)
        self.assert_no_output(output)

  def tlm_data(self,validate):
    data = self.data()
    env = data["uvmf"]["environments"]["soc"]
    env["scoreboards"] = [{
      "name":"sb","sb_type":"uvmf_in_order_scoreboard","trans_type":"bus_transaction",
    }]
    env["tlm_connections"] = [{
      "driver":"agent0.monitored_ap","receiver":"sb.expected_analysis_export",
      "validate":validate,
    }]
    return data

  def test_tlm_validate_boolean_typo_is_rejected(self):
    result,output,_ = self.run_cli(self.tlm_data("Flase"),"--check")
    self.assert_error(result,"validate")
    self.assert_no_output(output)

  def test_tlm_validate_native_and_string_spellings_are_accepted(self):
    for value in (True,False,"True","False"):
      with self.subTest(value=value):
        result,output,_ = self.run_cli(self.tlm_data(value),"--check")
        self.assert_success(result)
        self.assert_no_output(output)

  def test_duplicate_named_fields_and_parameters_report_list_path(self):
    for field in ("transaction_vars","parameters"):
      with self.subTest(field=field):
        data = self.data()
        entries = data["uvmf"]["interfaces"]["bus"][field]
        entries.append(copy.deepcopy(entries[0]))
        result,output,_ = self.run_cli(data,"--check")
        self.assert_error(result,"Duplicate name","interfaces.bus."+field)
        self.assert_no_output(output)

  def test_check_rejects_undefined_analysis_component_without_output(self):
    data = self.data()
    data["uvmf"]["environments"]["soc"]["analysis_components"] = [{
      "name":"predictor0","type":"missing_predictor",
    }]
    result,output,_ = self.run_cli(data,"--check")
    self.assert_error(result,"missing_predictor")
    self.assert_no_output(output)

  def test_check_rejects_invalid_tlm_endpoint_without_output(self):
    data = self.tlm_data(True)
    data["uvmf"]["environments"]["soc"]["tlm_connections"][0]["driver"] = "agent0.not_a_port"
    result,output,_ = self.run_cli(data,"--check")
    self.assert_error(result,"agent0.not_a_port")
    self.assert_no_output(output)

  def test_check_rejects_unknown_bench_interface_parameter_without_output(self):
    data = self.data()
    data["uvmf"]["benches"]["soc"]["interface_params"] = [{
      "path":"environment.agent0","value":[{"name":"WIDHT","value":"16"}],
    }]
    result,output,_ = self.run_cli(data,"--check")
    self.assert_error(result,"WIDHT")
    self.assert_no_output(output)

  def test_extdef_and_explicit_disabled_tlm_validation_remain_legal(self):
    data = self.tlm_data(False)
    env = data["uvmf"]["environments"]["soc"]
    env["analysis_components"] = [{"name":"external0","type":"external_predictor","extdef":True}]
    env["tlm_connections"][0]["driver"] = "external0.project_specific_port"
    result,output,_ = self.run_cli(data,"--check")
    self.assert_success(result)
    self.assert_no_output(output)

  def test_nonempty_output_warning_survives_quiet_and_preserves_existing_bytes(self):
    result,output,_ = self.run_cli(self.data())
    self.assert_success(result)
    source = output / "verification_ip/environment_packages/soc_env_pkg/src/soc_environment.sv"
    marker = "  // pragma uvmf custom class_item_additional end"
    content = source.read_text(encoding="utf-8")
    self.assertIn(marker,content)
    source.write_text(content.replace(marker,"  int user_preserved = 42;\n"+marker),encoding="utf-8")
    user_file = output / "user_notes.txt"
    user_file.write_bytes(b"user bytes\x00\xff")
    before = {path.relative_to(output):path.read_bytes() for path in output.rglob("*") if path.is_file()}
    result,_,_ = self.run_cli(self.data(),output=output)
    self.assert_success(result)
    self.assertIn("WARNING:",result.stdout+result.stderr)
    after = {path.relative_to(output):path.read_bytes() for path in output.rglob("*") if path.is_file()}
    self.assertEqual(before,after)

  def test_skip_missing_merge_warning_survives_quiet_and_backup_preserves_custom_blocks(self):
    data = {"uvmf":{"environments":{"soc":{}}}}
    result,output,_ = self.run_cli(data)
    self.assert_success(result)
    relative = Path("verification_ip/environment_packages/soc_env_pkg/src/soc_environment.sv")
    source = output / relative
    with source.open("a",encoding="utf-8") as handle:
      handle.write("\n// pragma uvmf custom removed_user_slot begin\n"
                   "int retained_only_in_backup = 123;\n"
                   "// pragma uvmf custom removed_user_slot end\n")
    original = source.read_bytes()
    result,_,_ = self.run_cli(data,"--merge_source",str(output),
                            "--merge_skip_missing_blocks",output=output)
    self.assert_success(result)
    self.assertIn("WARNING:",result.stdout+result.stderr)
    self.assertIn("removed_user_slot",result.stdout+result.stderr)
    backups = list(self.root.glob(output.name+"_bak_*"))
    self.assertEqual(len(backups),1)
    self.assertEqual((backups[0] / relative).read_bytes(),original)

  def test_invalid_utf8_is_a_contextual_error(self):
    result,output,config = self.run_cli(b"uvmf:\n  environments:\n    bad: \xff\n")
    self.assert_error(result,"UTF-8",config.name)
    self.assert_no_output(output)

  def test_recursive_alias_reports_configuration_path(self):
    result,output,_ = self.run_cli("uvmf:\n  environments:\n    soc: &soc\n      register_model: *soc\n","--check")
    self.assert_error(result,"Recursive YAML alias","environments.soc.register_model")
    self.assert_no_output(output)

  def test_duplicate_instance_names_across_categories_fail(self):
    data = self.data()
    data["uvmf"]["environments"]["soc"]["analysis_components"] = [{
      "name":"agent0","type":"external_observer","extdef":True,
    }]
    result,output,_ = self.run_cli(data,"--check")
    self.assert_error(result,"Duplicate instance name","agent0","soc")
    self.assert_no_output(output)

  def test_duplicate_bench_parameter_override_is_not_silently_replaced(self):
    data = self.data()
    data["uvmf"]["benches"]["soc"]["interface_params"] = [{
      "bfm_name":"agent0","value":[
        {"name":"WIDTH","value":"8"},{"name":"WIDTH","value":"16"},
      ],
    }]
    result,output,_ = self.run_cli(data,"--check")
    self.assert_error(result,"Duplicate name","WIDTH","interface_params[0].value")
    self.assert_no_output(output)

  def test_debug_error_includes_python_traceback(self):
    data = self.data()
    data["uvmf"]["interfaces"]["bus"]["use_dpi_link"] = "typo"
    result,output,_ = self.run_cli(data,"--debug","--check")
    self.assertNotEqual(result.returncode,0)
    self.assertIn("ERROR:",result.stderr)
    self.assertIn("Traceback",result.stderr)
    self.assert_no_output(output)

  def test_empty_template_directory_has_actionable_error(self):
    templates = self.root / "empty_templates"
    templates.mkdir()
    result,_,_ = self.run_cli(self.data(),"--template_dir",str(templates))
    self.assert_error(result,"No templates found",str(templates),"UVMF_TEMPLATE_PATH")
    self.assertNotIn("NameError",result.stderr)

  def test_custom_template_syntax_error_names_the_template_and_line(self):
    templates = self.root / "custom_templates"
    environments = templates / "environment_templates"
    environments.mkdir(parents=True)
    broken = environments / "broken.TMPL"
    broken.write_text("{% if %}\n",encoding="utf-8")
    result,_,_ = self.run_cli({"uvmf":{"environments":{"soc":{}}}},"--template_dir",str(templates))
    self.assert_error(result,"broken.TMPL","line")

  def test_check_existing_output_preserves_all_bytes_and_creates_no_backup(self):
    result,output,_ = self.run_cli(self.data())
    self.assert_success(result)
    before = {p.relative_to(output):p.read_bytes() for p in output.rglob("*") if p.is_file()}
    result,_,_ = self.run_cli(self.data(),"--check","--merge_source",str(output),output=output)
    self.assert_success(result)
    self.assertEqual(before,{p.relative_to(output):p.read_bytes() for p in output.rglob("*") if p.is_file()})
    self.assertFalse(list(self.root.glob(output.name+"_bak_*")))
    self.assertFalse(list(self.root.glob(".uvmf_merge_*")))

  def test_merge_debug_uses_separate_output_and_preserves_custom_code(self):
    data = {"uvmf":{"environments":{"soc":{}}}}
    result,output,_ = self.run_cli(data)
    self.assert_success(result)
    relative = Path("verification_ip/environment_packages/soc_env_pkg/src/soc_environment.sv")
    source = output / relative
    marker = "  // pragma uvmf custom class_item_additional end"
    content = source.read_text(encoding="utf-8")
    source.write_text(content.replace(marker,"  int keep_debug_merge = 42;\n"+marker),encoding="utf-8")
    original = source.read_bytes()
    result,_,_ = self.run_cli(data,"--merge_debug","--merge_source",str(output),output=output)
    self.assert_success(result)
    self.assertIn(b"int keep_debug_merge = 42;",source.read_bytes())
    intermediate = Path(str(output)+"_tmp") / relative
    self.assertTrue(intermediate.is_file())
    self.assertNotIn(b"keep_debug_merge",intermediate.read_bytes())
    backups = list(self.root.glob(output.name+"_bak_*"))
    self.assertEqual(len(backups),1)
    self.assertEqual((backups[0] / relative).read_bytes(),original)

  def test_merge_debug_rejects_nested_output_before_writes(self):
    source = self.root / "existing_source"
    source.mkdir()
    user_file = source / "user.bin"
    user_file.write_bytes(b"keep\x00\xff")
    result,output,_ = self.run_cli(self.data(),"--merge_debug","--merge_source",str(source),output=source / "debug")
    self.assert_error(result,"outside --merge_source")
    self.assert_no_output(output)
    self.assertEqual(user_file.read_bytes(),b"keep\x00\xff")
    self.assertFalse(list(self.root.glob(source.name+"_bak_*")))

  def test_quiet_debug_keeps_parameter_elaboration_details(self):
    for explicit in (False,True):
      with self.subTest(explicit=explicit):
        data = self.data()
        data["uvmf"]["global"] = {"elaborate_bfm_parameters":True}
        if explicit:
          data["uvmf"]["benches"]["soc"]["interface_params"] = [{
            "bfm_name":"agent0","value":[{"name":"WIDTH","value":"16"}],
          }]
        result,output,_ = self.run_cli(data,"--check","--debug")
        self.assert_success(result)
        self.assertIn("Found explicit parameters" if explicit else "Resolved unspecified BFM parameter",result.stderr)
        self.assertIn("agent0",result.stderr)
        self.assert_no_output(output)

  def test_array_subenvironment_member_name_collision_fails(self):
    data = self.data()
    data["uvmf"]["environments"]["leaf"] = {}
    soc = data["uvmf"]["environments"]["soc"]
    soc["agents"][0]["name"] = "child"
    soc["subenvs"] = [{"name":"child","type":"leaf","array":True,"count":2}]
    result,output,_ = self.run_cli(data,"--check")
    self.assert_error(result,"Duplicate instance name","child","soc")
    self.assert_no_output(output)

  def test_merge_debug_rejects_stale_output_and_keeps_both_trees(self):
    result,source,_ = self.run_cli(self.data())
    self.assert_success(result)
    before = {p.relative_to(source):p.read_bytes() for p in source.rglob("*") if p.is_file()}
    debug = self.root / "stale_debug"
    debug.mkdir()
    marker = debug / "user.bin"
    marker.write_bytes(b"do not overwrite\x00\xff")
    result,_,_ = self.run_cli(self.data(),"--merge_debug","--merge_source",str(source),output=debug)
    self.assert_error(result,"not empty","stale")
    self.assertEqual(marker.read_bytes(),b"do not overwrite\x00\xff")
    self.assertEqual(before,{p.relative_to(source):p.read_bytes() for p in source.rglob("*") if p.is_file()})
    self.assertFalse(list(self.root.glob(source.name+"_bak_*")))


if __name__ == "__main__":
  unittest.main()
