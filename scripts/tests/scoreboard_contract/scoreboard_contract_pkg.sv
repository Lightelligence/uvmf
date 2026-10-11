package scoreboard_contract_pkg;
  timeunit 1ns;
  timeprecision 1ps;

  import uvm_pkg::*;
  `include "uvm_macros.svh"

  `uvm_analysis_imp_decl(_expected)
  `uvm_analysis_imp_decl(_actual)

  // Compile the real UVMF implementations, with no generator or DPI dependencies.
  `include "uvmf_transaction_base.svh"
  `include "uvmf_scoreboard_base.svh"
  `include "uvmf_out_of_order_scoreboard.svh"
  `include "uvmf_out_of_order_race_scoreboard.svh"
  `include "uvmf_in_order_race_scoreboard_array.svh"

  `include "scoreboard_contract_item.svh"
  `include "scoreboard_contract_custom_base.svh"
  `include "scoreboard_contract_hook_scoreboard.svh"
  `include "scoreboard_contract_empty_catcher.svh"
  `include "scoreboard_contract_test.svh"
endpackage : scoreboard_contract_pkg
