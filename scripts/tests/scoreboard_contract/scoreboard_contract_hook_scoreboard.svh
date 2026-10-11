class scoreboard_contract_hook_scoreboard extends
    uvmf_out_of_order_race_scoreboard #(scoreboard_contract_item);
  int unsigned hook_calls;
  bit inject_actual;

  `uvm_component_utils(scoreboard_contract_hook_scoreboard)

  // Explicit constructors keep the fixture independent of dv_macros.svh.
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction : new

  virtual function void compare_or_store_entry(input scoreboard_contract_item t);
    hook_calls++;
    if (inject_actual) begin
      inject_actual = 0;
      write_actual(scoreboard_contract_item::make(t.key, t.payload));
    end
    super.compare_or_store_entry(t);
  endfunction : compare_or_store_entry
endclass : scoreboard_contract_hook_scoreboard
