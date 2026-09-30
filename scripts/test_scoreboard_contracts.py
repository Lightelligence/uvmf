#! /usr/bin/env python3
"""Static guard-order checks, not a substitute for licensed UVM simulation."""

from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parent.parent / "uvmf_base_pkg" / "src"


def function(text,name):
  match = re.search(r'function void '+name+r'\(.*?endfunction',text,re.DOTALL)
  if not match:
    raise AssertionError("Missing function: "+name)
  return match.group()


class ScoreboardContractTest(unittest.TestCase):
  def test_array_invalid_keys_return_before_activity_and_indexing(self):
    for filename in ("uvmf_in_order_scoreboard_array.svh","uvmf_in_order_race_scoreboard_array.svh"):
      text = (SOURCE / filename).read_text(encoding="utf-8")
      for port in ("expected","actual"):
        with self.subTest(filename=filename,port=port):
          body = function(text,"write_"+port)
          check = re.search(r'if \([^\n]*>= ARRAY_DEPTH\) begin.*?end : '+port+r'_key_check',body,re.DOTALL)
          self.assertIsNotNone(check)
          self.assertIn("return;",check.group())
          self.assertLess(check.end(),body.index("super.write_"+port))
          first_index = re.search(r'(?:expected|actual)_results_q\[',body)
          self.assertLess(check.end(),first_index.start())
          self.assertIn("scoreboard_enabled && enable_"+port+"_port",body[:check.start()])

  def test_race_disabled_ports_return_before_counters_events_or_storage(self):
    text = (SOURCE / "uvmf_out_of_order_race_scoreboard.svh").read_text(encoding="utf-8")
    for port in ("expected","actual"):
      with self.subTest(port=port):
        body = function(text,"write_"+port)
        guard = "if (!scoreboard_enabled || !enable_"+port+"_port) return;"
        self.assertIn(guard,body)
        for operation in ("->entry_received;","compare_or_store_entry(t);"):
          self.assertLess(body.index(guard),body.index(operation))
        if port == "expected":
          self.assertLess(body.index(guard),body.index("transaction_count++;"))


if __name__ == "__main__":
  unittest.main()
