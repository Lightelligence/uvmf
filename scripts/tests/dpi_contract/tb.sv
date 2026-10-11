// Generated UVMF API regression. Existing UVMF public API spellings are preserved.
module tb;
  timeunit 1ns;
  timeprecision 1ps;
  import uvm_pkg::*;
  import uvmf_base_pkg::*;
  import bus_pkg::*;
  import soc_env_pkg::*;
  import soc_tests_pkg::*;
  `include "uvm_macros.svh"

  bit clk = 0;
  bit rst = 1;
  always #5ns clk = ~clk;
  bus_if #(.WIDTH(16)) bus0(clk, rst);
  bus_if #(.WIDTH(16)) bus1(clk, rst);
  bus_driver_bfm #(.WIDTH(16)) bus0_drv_bfm(bus0);
  bus_monitor_bfm #(.WIDTH(16)) bus0_mon_bfm(bus0);
  bus_driver_bfm #(.WIDTH(16)) bus1_drv_bfm(bus1);
  bus_monitor_bfm #(.WIDTH(16)) bus1_mon_bfm(bus1);

  initial begin : run_contract
    soc_env_configuration_t cfg;
    bus_driver #(.WIDTH(16)) driver;
    bus_monitor #(.WIDTH(16)) monitor;
    bus_transaction #(.WIDTH(16)) txn;
    soc_environment_t env;
    soc_virtual_sequencer #(.CONFIG_T(soc_env_configuration_t), .WIDTH(16)) vsqr;
    soc_env_sequence_base_t seq;
    uvm_tlm_analysis_fifo #(bus_transaction #(.WIDTH(16))) fifo;
    string names[] = '{"tb.bus0", "tb.bus1"};
    uvmf_active_passive_t activities[] = '{ACTIVE, PASSIVE};

    // Let the generated BFM initial monitor threads reach their start event waits.
    #1ns;
    cfg = soc_env_configuration_t::type_id::create("cfg");
    cfg.initialize(BLOCK, "environment", names);
    if (cfg.ip0_config[0].agent0_config.active_passive != ACTIVE ||
        cfg.ip0_config[1].agent0_config.active_passive != ACTIVE) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: omitted activity defaults");
    end
    cfg.initialize(BLOCK, "environment", names, null, activities);
    if (cfg.ip0_config[0].agent0_config.interface_name != "tb.bus0" ||
        cfg.ip0_config[1].agent0_config.interface_name != "tb.bus1" ||
        cfg.ip0_config[0].agent0_config.active_passive != ACTIVE ||
        cfg.ip0_config[1].agent0_config.active_passive != PASSIVE) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: array configuration element ordering");
    end

    env = soc_environment_t::type_id::create("env", null);
    vsqr = soc_virtual_sequencer#(soc_env_configuration_t, 16)::type_id::create("vsqr", null);
    vsqr.set_config(cfg);
    vsqr.set_env(env);
    seq = soc_env_sequence_base_t::type_id::create("seq");
    seq.start(vsqr);

    driver = bus_driver#(16)::type_id::create("driver", null);
    driver.configuration = cfg.ip0_config[0].agent0_config;
    driver.configuration.flag = 8'hb6;
    driver.bfm = driver.configuration.driver_bfm;
    driver.configure(driver.configuration);
    if (bus0_drv_bfm.flag != 8'hb6 || bus0_drv_bfm.initiator_responder != INITIATOR) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: driver configuration propagation");
    end
    txn = bus_transaction#(16)::type_id::create("txn");
    txn.data = 16'h9234;
    driver.access(txn);
    if (txn.data != (16'h9234 ^ 16'h5a5a)) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: initiator round trip");
    end
    driver.configuration.initiator_responder = RESPONDER;
    driver.configure(driver.configuration);
    txn.data = 16'ha321;
    driver.access(txn);
    if (txn.data != (16'ha321 ^ 16'ha5a5) ||
        bus0_drv_bfm.initiator_responder != RESPONDER) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: responder round trip");
    end

    monitor = bus_monitor#(16)::type_id::create("monitor", null);
    monitor.configuration = cfg.ip0_config[0].agent0_config;
    monitor.bfm = monitor.configuration.monitor_bfm;
    monitor.build_phase(null);
    fifo = new("fifo", null);
    monitor.monitored_ap.connect(fifo.analysis_export);
    monitor.monitored_ap.resolve_bindings();
    monitor.set_bfm_proxy_handle();
    monitor.configure(monitor.configuration);
    if (bus0_mon_bfm.flag != 8'hb6 || bus0_mon_bfm.initiator_responder != RESPONDER) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: monitor configuration propagation");
    end
    monitor.bfm.wait_for_reset();
    monitor.bfm.wait_for_num_clocks(2);
    monitor.bfm.start_monitoring();
    fifo.get(txn);
    if (txn.data != 16'hc35a) begin
      $fatal(1, "GENERATED_CONTRACT_FAIL: monitor callback specialization");
    end
    $display("GENERATED_CONTRACT_PASS");
    $finish;
  end

  initial begin : watchdog
    #1us;
    $fatal(1, "GENERATED_CONTRACT_FAIL: watchdog");
  end
endmodule
