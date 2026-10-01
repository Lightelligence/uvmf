#! /usr/bin/env python3

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(REPO_ROOT / "templates" / "python"))
sys.path.insert(0,str(REPO_ROOT / "templates" / "python" / "python3"))

from uvmf_gen import UserError
from uvmf_yaml.unmarked import migrate_unmarked


def slot(label,content=""):
  return "// pragma uvmf custom {} begin\n{}// pragma uvmf custom {} end\n".format(label,content,label)


class UnmarkedMigrationTest(unittest.TestCase):
  def test_migration_retains_position_on_either_side_of_existing_content(self):
    new = "generated_before;\n"+slot("build_phase_components")+"generated_after;\n"
    for side in ("before","after"):
      with self.subTest(side=side):
        old_slot = slot("build_phase_components","existing();\n")
        inserted = "// project addition\nadded();\n"
        old = "generated_before;\n"+(inserted+old_slot if side == "before" else old_slot+inserted)+"generated_after;\n"
        self.assertEqual(migrate_unmarked(old,new,"env.sv"),{
          "build_phase_components": {side: inserted, "after" if side == "before" else "before": ""},
        })

  def test_new_constructor_and_member_slots_accept_legacy_additions(self):
    for label in ("new_pre_config","class_item_before_sequencer"):
      with self.subTest(label=label):
        new = "generated_before;\n"+slot(label)+"generated_after;\n"
        old = "generated_before;\nproject_addition;\ngenerated_after;\n"
        self.assertEqual(migrate_unmarked(old,new,"env.sv")[label]["before"],"project_addition;\n")

  def test_custom_block_changes_are_not_scaffold_edits(self):
    new = "class cfg;\n"+slot("new","default();\n")+"endclass\n"
    old = "class cfg;\n"+slot("new","// 注释 ‘UTF-8’\ncustom();\n")+"endclass\n"
    self.assertEqual(migrate_unmarked(old,new,"cfg.sv"),{})

  def test_unsupported_additions_replacements_and_deletions_fail_closed(self):
    new = "first;\nsecond;\n"+slot("new_pre_config")+"third;\n"
    for old in (
      new.replace("first;\n","first;\nunmarked();\n"),
      new.replace("second;","changed;"),
      new.replace("second;\n",""),
    ):
      with self.subTest(old=old),self.assertRaisesRegex(UserError,"Cannot safely migrate"):
        migrate_unmarked(old,new,"cfg.sv")

  def test_ambiguous_same_position_slots_fail_closed(self):
    new = "first;\n"+slot("build_phase_components")+slot("new_pre_config")+"second;\n"
    old = new.replace("first;\n","first;\naddition();\n")
    with self.assertRaisesRegex(UserError,"Cannot safely migrate"):
      migrate_unmarked(old,new,"cfg.sv")

  def test_additions_on_both_sides_of_a_block_are_not_collapsed(self):
    new = "first;\n"+slot("build_phase_components")+"second;\n"
    old = "first;\na();\n"+slot("build_phase_components","existing();\n")+"b();\nsecond;\n"
    with self.assertRaisesRegex(UserError,"Ambiguous unmarked"):
      migrate_unmarked(old,new,"env.sv")

  def test_new_slot_cannot_reorder_additions_across_existing_custom_code(self):
    new = "first;\n"+slot("build_phase_components")+slot("reg_model_build_phase")+"second;\n"
    old = "first;\n"+slot("reg_model_build_phase","existing();\n")+"addition();\nsecond;\n"
    with self.assertRaisesRegex(UserError,"reorder code across custom block"):
      migrate_unmarked(old,new,"env.sv")


if __name__ == "__main__":
  unittest.main()
