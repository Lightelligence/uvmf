class scoreboard_contract_custom_base extends uvm_scoreboard;
  `uvm_component_utils(scoreboard_contract_custom_base)

  // Explicit constructors keep the fixture independent of dv_macros.svh.
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction : new

  function int unsigned custom_marker();
    return 32'h1234;
  endfunction : custom_marker
endclass : scoreboard_contract_custom_base
