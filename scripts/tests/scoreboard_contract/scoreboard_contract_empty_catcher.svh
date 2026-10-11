class scoreboard_contract_empty_catcher extends uvm_report_catcher;
  bit capture_empty_errors;
  int unsigned empty_errors;

  `uvm_object_utils(scoreboard_contract_empty_catcher)

  // Explicit constructors keep the fixture independent of dv_macros.svh.
  function new(string name = "");
    super.new(name);
  endfunction : new

  virtual function action_e catch();
    if (capture_empty_errors && (get_severity() == UVM_ERROR) && (get_id() == "SCBD") &&
        uvm_is_match("*SCOREBOARD NOT EMPTY*", get_message())) begin
      empty_errors++;
      return CAUGHT;
    end
    return THROW;
  endfunction : catch
endclass : scoreboard_contract_empty_catcher
