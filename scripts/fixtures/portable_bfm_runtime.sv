// Bounded simulator regression for existing struct/object APIs and callbacks.
module portable_bfm_runtime;
  timeunit 1ns;
  timeprecision 1ps;
  import uvm_pkg::*;
  import uvmf_base_pkg::*;
  import struct_bus_pkg::*;
  import object_bus_pkg::*;

  bit clk = 0;
  bit rst = 0;
  always #5ns clk = ~clk;
  struct_bus_if struct_bus(clk, rst);
  object_bus_if object_bus(clk, rst);
  struct_bus_driver_bfm struct_drv_bfm(struct_bus);
  struct_bus_monitor_bfm struct_mon_bfm(struct_bus);
  object_bus_driver_bfm object_drv_bfm(object_bus);
  object_bus_monitor_bfm object_mon_bfm(object_bus);

  initial begin : contracts
    struct_bus_transaction st, st_copy;
    object_bus_transaction ot;
    struct_bus_configuration sc;
    object_bus_configuration oc;
    struct_bus_driver sd;
    object_bus_driver od;
    struct_bus_monitor sm;
    object_bus_monitor om;
    st = new("st");
    st_copy = new("st_copy");
    ot = new("ot");
    sc = new("sc");
    oc = new("oc");
    sd = new("sd", null);
    od = new("od", null);
    sm = new("sm", null);
    om = new("om", null);

    st.data = 8'hc3;
    st_copy.from_monitor_struct(st.to_monitor_struct());
    if (st_copy.data != st.data) $fatal(1, "monitor struct roundtrip failed");
    st_copy.from_initiator_struct(st.to_initiator_struct());
    if (st_copy.data != st.data) $fatal(1, "initiator struct roundtrip failed");
    st_copy.from_responder_struct(st.to_responder_struct());
    if (st_copy.data != st.data) $fatal(1, "responder struct roundtrip failed");
    sc.active_passive = ACTIVE;
    sc.initiator_responder = INITIATOR;
    oc.active_passive = ACTIVE;
    oc.initiator_responder = INITIATOR;
    sc.mode = 8'h5a;
    oc.mode = 8'ha5;
    sd.bfm = struct_drv_bfm;
    sm.bfm = struct_mon_bfm;
    od.bfm = object_drv_bfm;
    om.bfm = object_mon_bfm;
    sd.configure(sc);
    sm.configure(sc);
    od.configure(oc);
    om.configure(oc);
    if (struct_drv_bfm.mode != sc.mode || struct_mon_bfm.mode != sc.mode) $fatal(1, "struct configure failed");
    if (object_drv_bfm.mode != oc.mode || object_mon_bfm.mode != oc.mode) $fatal(1, "object configure failed");
    sd.set_bfm_proxy_handle();
    sm.set_bfm_proxy_handle();
    od.set_bfm_proxy_handle();
    om.set_bfm_proxy_handle();
    if (struct_drv_bfm.proxy != sd || struct_mon_bfm.proxy != sm) $fatal(1, "struct proxy binding failed");
    if (object_drv_bfm.proxy != od || object_mon_bfm.proxy != om) $fatal(1, "object proxy binding failed");
    sm.build_phase(null);
    om.build_phase(null);
    // analyze() uses the configuration's optional viewing hook and analysis port.
    sm.configuration = sc;
    om.configuration = oc;
    sm.notify_transaction(st.to_monitor_struct());
    ot.data = 8'h3c;
    om.notify_transaction(ot);
    if (sm.trans.data != st.data || om.trans != ot) $fatal(1, "monitor callback failed");
    st.add_to_wave(0);
    $display("PORTABLE_BFM_PASS: struct/object configuration, proxy binding, roundtrips, monitor callbacks, viewing hook");
    $finish;
  end
endmodule : portable_bfm_runtime
