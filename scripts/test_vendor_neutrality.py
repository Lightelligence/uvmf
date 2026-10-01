#!/usr/bin/env python3
"""License-free contracts for portable generation, aliases and retired APIs."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_soc_integration import BASE_YAML, REPO_ROOT
from uvmf_gen import UVMFCommandLineParser, UserError
from yaml2uvmf import DataClass


class VendorNeutralityTest(unittest.TestCase):
  def generate(self,root,settings='',bench_settings='',extra='',profile='vcs'):
    config = root / 'input.yaml'
    text = BASE_YAML.replace('    bus:\n','    bus:\n'+settings,1)
    text = text.replace('      top_env: soc\n','      top_env: soc\n'+bench_settings,1)
    config.write_text(text+extra,encoding='utf-8')
    output = root / 'output'
    result = subprocess.run([sys.executable,'-B',str(REPO_ROOT/'scripts/yaml2uvmf.py'),str(config),'-d',str(output),'--simulator',profile],capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stderr+result.stdout)
    return output

  def generated_sources(self,root):
    return {str(p.relative_to(root)):p.read_text(encoding='utf-8') for p in root.rglob('*') if p.is_file() and p.suffix in ('.sv','.svh')}

  def test_legacy_and_new_transport_keys_generate_identical_sources(self):
    for value in ('true','false','"True"','"False"'):
      for profile in ('vcs','xcelium'):
        with self.subTest(value=value,profile=profile),tempfile.TemporaryDirectory() as tmp:
          root = Path(tmp)
          old = root/'old'; old.mkdir()
          new = root/'new'; new.mkdir()
          before = self.generate(old,'      veloce_ready: '+value+'\n',profile=profile)
          after = self.generate(new,'      use_struct_bfm: '+value+'\n',profile=profile)
          self.assertEqual(self.generated_sources(before),self.generated_sources(after))

  def test_default_transport_retains_struct_bfm_api(self):
    with tempfile.TemporaryDirectory() as tmp:
      output = self.generate(Path(tmp))
      pkg = output/'verification_ip/interface_packages/bus_pkg'
      driver = (pkg/'src/bus_driver.sv').read_text(encoding='utf-8')
      monitor = (pkg/'src/bus_monitor.sv').read_text(encoding='utf-8')
      macros = (pkg/'src/bus_macros.svh').read_text(encoding='utf-8')
      self.assertIn('bfm.configure( cfg.to_struct() )',driver)
      self.assertIn('txn.to_initiator_struct()',driver)
      self.assertIn('txn.from_responder_struct(',driver)
      self.assertIn('bus_monitor_s',monitor)
      for token in ('bus_CONFIGURATION_STRUCT','bus_MONITOR_STRUCT','bus_INITIATOR_STRUCT','bus_RESPONDER_STRUCT'):
        self.assertIn(token,macros)

  def test_object_mode_no_longer_requires_bench_emulation_opt_out(self):
    for bench_value in ('','      veloce_ready: true\n','      veloce_ready: false\n'):
      with self.subTest(bench_value=bench_value),tempfile.TemporaryDirectory() as tmp:
        output = self.generate(Path(tmp),'      use_struct_bfm: false\n',bench_value)
        driver = (output/'verification_ip/interface_packages/bus_pkg/src/bus_driver.sv').read_text(encoding='utf-8')
        self.assertIn('bfm.configure( cfg )',driver)
        self.assertIn('bfm.initiate_and_get_response( txn )',driver)
        self.assertNotIn('txn.to_initiator_struct()',driver)

  def test_archive_uses_generic_transport_and_parses_again(self):
    for value in ('true','false'):
      with self.subTest(value=value),tempfile.TemporaryDirectory() as tmp:
        output = self.generate(Path(tmp),'      veloce_ready: '+value+'\n')
        archive = output/'verification_ip/interface_packages/bus_pkg/yaml/bus_interface.yaml'
        self.assertTrue(archive.exists())
        text = archive.read_text(encoding='utf-8')
        self.assertNotIn('veloce_ready',text)
        data = DataClass(UVMFCommandLineParser())
        data.parseFile(str(archive))
        data.validate()
        self.assertEqual(data.data['interfaces']['bus'].get('use_struct_bfm','True'),value.title())

  def test_conflicting_aliases_are_rejected_and_matching_values_allowed(self):
    with tempfile.TemporaryDirectory() as tmp:
      config = Path(tmp)/'input.yaml'
      for new in ('true','false'):
        text = BASE_YAML.replace('    bus:\n','    bus:\n      veloce_ready: false\n      use_struct_bfm: '+new+'\n',1)
        config.write_text(text,encoding='utf-8')
        data = DataClass(UVMFCommandLineParser())
        if new == 'true':
          with self.assertRaisesRegex(UserError,'Conflicting interface settings'):
            data.parseFile(str(config))
        else:
          data.parseFile(str(config)); data.validate()

  def test_struct_mode_keeps_packed_type_constraints(self):
    with tempfile.TemporaryDirectory() as tmp:
      config = Path(tmp)/'input.yaml'
      config.write_text(BASE_YAML.replace('type: bit,','type: bit, unpacked_dimension: "[2]",'),encoding='utf-8')
      result = subprocess.run([sys.executable,'-B',str(REPO_ROOT/'scripts/yaml2uvmf.py'),str(config),'-d',str(Path(tmp)/'output')],capture_output=True,text=True)
      self.assertNotEqual(result.returncode,0)
      self.assertIn('unpacked dimension',result.stderr)

  def test_generic_vip_analysis_exports_do_not_require_mvc(self):
    for kind in ('predictor','coverage','scoreboard'):
      with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        config = root/'input.yaml'
        text = BASE_YAML.replace('  environments:\n','  util_components:\n    vip_observer:\n      type: '+kind+'\n      vip_analysis_exports:\n        - {name: external, type: uvm_sequence_item}\n  environments:\n',1)
        text = text.replace('      top_env: soc\n','      top_env: soc\n',1).replace('    soc:\n      subenvs:','    soc:\n      analysis_components:\n        - {name: observer, type: vip_observer}\n      subenvs:',1)
        config.write_text(text,encoding='utf-8')
        result = subprocess.run([sys.executable,'-B',str(REPO_ROOT/'scripts/yaml2uvmf.py'),str(config),'-d',str(root/'output')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        source = (root/'output/verification_ip/environment_packages/soc_env_pkg/src/vip_observer.sv').read_text(encoding='utf-8')
        self.assertIn('write_external(uvm_sequence_item _t)',source)
        self.assertNotIn('mvc_',source)

  def test_generated_sources_have_no_proprietary_integration(self):
    for profile in ('vcs','xcelium'):
      with self.subTest(profile=profile),tempfile.TemporaryDirectory() as tmp:
        sources = self.generated_sources(self.generate(Path(tmp),profile=profile))
        for path,text in sources.items():
          self.assertNotRegex(text,r'\bmvc_|\bmgc_|\bmti_|`ifn?def\s+(?:QUESTA|XRTL)|partition_|pragma tbx|tbx clkgen',path)

  def test_base_retains_viewing_hook_and_has_no_questa_calls(self):
    text = (REPO_ROOT/'uvmf_base_pkg/src/uvmf_transaction_base.svh').read_text(encoding='utf-8')
    self.assertIn('virtual function void add_to_wave(int transaction_viewing_stream_h)',text)
    for path in (REPO_ROOT/'uvmf_base_pkg').rglob('*.sv*'):
      active = re.sub(r'//[^\n]*|/\*.*?\*/','',path.read_text(encoding='utf-8'),flags=re.S)
      self.assertNotRegex(active,r'`ifn?def\s+QUESTA|\$(?:begin_transaction|create_transaction_stream|add_attribute)|\bmti_',str(path))

  def test_standard_dpi_link_remains_available(self):
    with tempfile.TemporaryDirectory() as tmp:
      output = self.generate(Path(tmp),'      use_dpi_link: true\n')
      pkg = output/'verification_ip/interface_packages/bus_pkg'
      source = (pkg/'bus_pkg.sv').read_text(encoding='utf-8')
      self.assertIn('import dpi_link_pkg::*;',source)
      self.assertTrue((pkg/'src/bus_driver_proxy.sv').exists())
      self.assertTrue((REPO_ROOT/'common/dpi_link_pkg/dpi_link.h').exists())

  def test_struct_and_object_reset_wait_semantics_are_preserved(self):
    for value in ('true','false'):
      with self.subTest(value=value),tempfile.TemporaryDirectory() as tmp:
        output = self.generate(Path(tmp),'      use_struct_bfm: '+value+'\n')
        text = (output/'verification_ip/interface_packages/bus_pkg/src/bus_monitor_bfm.sv').read_text(encoding='utf-8')
        body = re.search(r'task wait_for_reset\(\);(.*?)endtask',text,re.S).group(1)
        active = re.sub(r'//[^\n]*','',body)
        self.assertEqual('@(posedge clk_i)' in active,value == 'false')

  def test_removed_vendor_libraries_have_no_dangling_repo_references(self):
    for relative in ('common/mgc_vip','common/fli_pkg','common/utility_packages/qvip_utils_pkg'):
      self.assertFalse(any(path.is_file() for path in (REPO_ROOT/relative).rglob('*')),relative)
    for root in (REPO_ROOT/'common',REPO_ROOT/'templates/python/template_files'):
      for path in root.rglob('*'):
        if path.is_file() and path.suffix in ('.sv','.svh','.v','.TMPL','.cpp','.h'):
          text = path.read_text(encoding='utf-8')
          self.assertNotRegex(text,r'\b(?:mvc_|mgc_|mti_)|QUESTA_HOME|pragma tbx|partition_interface|partition_module',str(path))


if __name__ == '__main__':
  unittest.main()
