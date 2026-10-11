//----------------------------------------------------------------------
//   Copyright 2013-2021 Siemens Corporation
//   Digital Industries Software
//   Siemens EDA
//   All Rights Reserved Worldwide

//   Licensed under the Apache License, Version 2.0 (the
//   "License"); you may not use this file except in
//   compliance with the License.  You may obtain a copy of
//   the License at

//       http://www.apache.org/licenses/LICENSE-2.0

//   Unless required by applicable law or agreed to in
//   writing, software distributed under the License is
//   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
//   CONDITIONS OF ANY KIND, either express or implied.  See
//   the License for the specific language governing
//   permissions and limitations under the License.
//----------------------------------------------------------------------
//                   Mentor Graphics Inc
//----------------------------------------------------------------------
// Project         : UVM Framework
// Unit            : Out of order race scoreboard
// File            : uvmf_out_of_order_race_scoreboard.svh
//----------------------------------------------------------------------
// Creation Date   : 07.06.2022
//----------------------------------------------------------------------

// CLASS: uvmf_out_of_order_race_scoreboard
// This class defines an out of order race scoreboard that is based on the uvmf_out_of_order_scoreboard class.
// This scoreboard is a generic scoreboard that will compare two objects of type T. Class T
// must be an extension of <uvmf_transaction_base>. Class T must have the following interfaces:
// - compare() which takes an object of class T as an argument and returns a bit result
//             with 1 representing a successful compare.
// - get_key() which returns an integer which is used as a key for the associative array
//             within the scoreboard.
// Different keys may arrive in any order. Repeated entries for the same key are
// matched in FIFO order within each source. Either stream may arrive first;
// comparisons are initiated by arrivals through the write interface.


// PARAMETERS:
//    T    - Specifies the type of transactions to be compared.
//           Must be derived from uvmf_transaction_base.

// Keep the public class, type parameter and method names for UVMF API compatibility.
class uvmf_out_of_order_race_scoreboard #(
    type T = uvmf_transaction_base,
    type BASE_T = uvmf_out_of_order_scoreboard #(T)
) extends BASE_T;

  // expected_hash remains the oldest expected entry for each key, as in the base class.
  // Extra expected entries and early actual entries must retain their source and order.
  typedef T transaction_queue_t[$];
  protected transaction_queue_t expected_pending[int unsigned];
  protected transaction_queue_t actual_pending[int unsigned];
  protected bit entry_is_expected = 0;

  `uvm_component_param_utils(uvmf_out_of_order_race_scoreboard #(T, BASE_T))

  // Explicit constructors avoid a dependency on lowRISC-specific dv_macros.svh.
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction : new

  virtual function void write_expected(input T t);
    bit previous_source;
    if (!scoreboard_enabled || !enable_expected_port) begin
      return;
    end
    transaction_count++;
    previous_source = entry_is_expected;
    entry_is_expected = 1;
    compare_or_store_entry(t);
    entry_is_expected = previous_source;
    ->entry_received;
  endfunction : write_expected

  virtual function void write_actual(input T t);
    bit previous_source;
    if (!scoreboard_enabled || !enable_actual_port) begin
      return;
    end
    previous_source = entry_is_expected;
    entry_is_expected = 0;
    compare_or_store_entry(t);
    entry_is_expected = previous_source;
    ->entry_received;
  endfunction : write_actual

  // Retain the one-argument virtual hook for existing overrides. Direct calls are
  // actual-side writes; write_* save and restore context for nested callbacks.
  virtual function void compare_or_store_entry(input T t);
    T other_item;
    int unsigned key;
    if (!scoreboard_enabled) begin
      return;
    end
    key = t.get_key();
    if (entry_is_expected) begin
      if (actual_pending.exists(key)) begin
        other_item = actual_pending[key].pop_front();
        if (actual_pending[key].size() == 0) begin
          actual_pending.delete(key);
        end
        compare_entries(t, other_item);
      end else if (expected_hash.exists(key)) begin
        expected_pending[key].push_back(t);
      end else begin
        expected_hash[key] = t;
      end
    end else if (expected_hash.exists(key)) begin
      other_item = expected_hash[key];
      if (expected_pending.exists(key)) begin
        expected_hash[key] = expected_pending[key].pop_front();
        if (expected_pending[key].size() == 0) begin
          expected_pending.delete(key);
        end
      end else begin
        expected_hash.delete(key);
      end
      compare_entries(other_item, t);
    end else begin
      actual_pending[key].push_back(t);
    end
  endfunction : compare_or_store_entry

  virtual function void compare_entries(T expected, T actual);
    if (disable_entry_compare) begin
      `uvm_warning("SCBD", "COMPARISONS DISABLED")
      return;
    end
    last_expected = expected;
    last_actual = actual;
    if (actual.compare(expected)) begin
      match_count++;
      last_mismatched = 0;
      `uvm_info("SCBD", compare_message("MATCH! - ", expected, actual), UVM_MEDIUM)
    end else begin
      mismatch_count++;
      last_mismatched = 1;
      `uvm_error("SCBD", compare_message("MISMATCH! - ", expected, actual))
    end
  endfunction : compare_entries

  virtual function void flush_scoreboard();
    super.flush_scoreboard();
    expected_pending.delete();
    actual_pending.delete();
    ->entry_received;
  endfunction : flush_scoreboard

  // Remove the oldest unmatched entry for this key from whichever side owns it.
  virtual function void remove_entry(int unsigned key = 0);
    T removed_item;
    if (expected_hash.exists(key)) begin
      if (expected_pending.exists(key)) begin
        expected_hash[key] = expected_pending[key].pop_front();
        if (expected_pending[key].size() == 0) begin
          expected_pending.delete(key);
        end
      end else begin
        expected_hash.delete(key);
      end
    end else if (actual_pending.exists(key)) begin
      removed_item = actual_pending[key].pop_front();
      if (actual_pending[key].size() == 0) begin
        actual_pending.delete(key);
      end
    end
    ->entry_received;
  endfunction : remove_entry

  virtual task wait_for_scoreboard_drain();
    while ((expected_hash.num() != 0) || (expected_pending.num() != 0) ||
           (actual_pending.num() != 0)) begin
      @entry_received;
    end
  endtask : wait_for_scoreboard_drain

  virtual function void check_phase(uvm_phase phase);
    T item;
    int unsigned printed = 0;
    // The inherited check covers expected_hash and the expected-side activity count.
    super.check_phase(phase);
    if (!end_of_test_empty_check) begin
      return;
    end
    if (expected_pending.num() != 0) begin
      foreach (expected_pending[key]) begin
        while ((expected_pending[key].size() != 0) &&
               (printed < max_remaining_transaction_print)) begin
          item = expected_pending[key].pop_front();
          `uvm_info("SCBD", $sformatf("Expected entry %0d:%s", printed++,
                                   item.convert2string()), UVM_MEDIUM)
        end
        if (expected_pending[key].size() == 0) begin
          expected_pending.delete(key);
        end
      end
      `uvm_error("SCBD", "EXPECTED SCOREBOARD NOT EMPTY")
    end
    if (actual_pending.num() != 0) begin
      printed = 0;
      foreach (actual_pending[key]) begin
        while ((actual_pending[key].size() != 0) &&
               (printed < max_remaining_transaction_print)) begin
          item = actual_pending[key].pop_front();
          `uvm_info("SCBD", $sformatf("Actual entry %0d:%s", printed++,
                                   item.convert2string()), UVM_MEDIUM)
        end
        if (actual_pending[key].size() == 0) begin
          actual_pending.delete(key);
        end
      end
      `uvm_error("SCBD", "ACTUAL SCOREBOARD NOT EMPTY")
    end
  endfunction : check_phase

endclass : uvmf_out_of_order_race_scoreboard
