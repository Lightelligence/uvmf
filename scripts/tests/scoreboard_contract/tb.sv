module tb;
  timeunit 1ns;
  timeprecision 1ps;

  import uvm_pkg::*;
  import scoreboard_contract_pkg::*;

  initial begin
    run_test();
  end

  initial begin
    #1us;
    $fatal(1, "SCOREBOARD_CONTRACT_TIMEOUT");
  end
endmodule : tb
