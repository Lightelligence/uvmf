class scoreboard_contract_test extends uvm_test;
  typedef uvmf_in_order_race_scoreboard_array #(scoreboard_contract_item, 2) array_scoreboard_t;
  typedef uvmf_scoreboard_base #(scoreboard_contract_item,
                                scoreboard_contract_custom_base) custom_scoreboard_t;
  scoreboard_contract_hook_scoreboard scoreboard;
  array_scoreboard_t array_scoreboard;
  custom_scoreboard_t custom_scoreboard;
  scoreboard_contract_empty_catcher empty_catcher;

  `uvm_component_utils(scoreboard_contract_test)

  // Explicit constructors keep the fixture independent of dv_macros.svh.
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction : new

  virtual function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    scoreboard = scoreboard_contract_hook_scoreboard::type_id::create("scoreboard", this);
    array_scoreboard = array_scoreboard_t::type_id::create("array_scoreboard", this);
    custom_scoreboard = custom_scoreboard_t::type_id::create("custom_scoreboard", this);
    empty_catcher = scoreboard_contract_empty_catcher::type_id::create("empty_catcher");
    uvm_report_cb::add(scoreboard, empty_catcher);
  endfunction : build_phase

  function void require(bit condition, string message);
    if (!condition) begin
      `uvm_fatal("SCOREBOARD_CONTRACT_FAIL", message)
    end
  endfunction : require

  function void check_empty_errors(uvm_phase phase, int unsigned expected_errors);
    int unsigned before_errors;
    before_errors = empty_catcher.empty_errors;
    empty_catcher.capture_empty_errors = 1;
    scoreboard.check_phase(phase);
    empty_catcher.capture_empty_errors = 0;
    require((empty_catcher.empty_errors - before_errors) == expected_errors,
            "Unexpected empty-check report count");
    scoreboard.flush_scoreboard();
  endfunction : check_empty_errors

  function void check_matching();
    scoreboard_contract_item expected;
    scoreboard_contract_item actual;
    scoreboard.write_expected(scoreboard_contract_item::make(7, 10));
    scoreboard.write_actual(scoreboard_contract_item::make(7, 10));
    scoreboard.write_actual(scoreboard_contract_item::make(11, 20));
    scoreboard.write_expected(scoreboard_contract_item::make(11, 20));
    require(scoreboard.match_count == 2, "Both arrival orders must match");

    scoreboard.write_expected(scoreboard_contract_item::make(7, 30));
    scoreboard.write_expected(scoreboard_contract_item::make(7, 40));
    require(scoreboard.match_count == 2, "Expected entries must never match each other");
    scoreboard.write_actual(scoreboard_contract_item::make(7, 30));
    scoreboard.write_actual(scoreboard_contract_item::make(7, 40));
    scoreboard.write_actual(scoreboard_contract_item::make(13, 50));
    actual = scoreboard_contract_item::make(13, 60);
    scoreboard.write_actual(actual);
    require(scoreboard.match_count == 4, "Actual entries must never match each other");
    expected = scoreboard_contract_item::make(13, 50);
    scoreboard.write_expected(expected);
    expected = scoreboard_contract_item::make(13, 60);
    scoreboard.write_expected(expected);
    require(scoreboard.match_count == 6, "Duplicate keys must match in source order");
    require(scoreboard.last_expected == expected, "Expected identity must survive actual-first");
    require(scoreboard.last_actual == actual, "Actual identity must survive actual-first");
    require(scoreboard.transaction_count == 6, "Every enabled expected write must be counted");
    require(scoreboard.hook_calls == 12, "Both write ports must retain the virtual hook");
    require(scoreboard.mismatch_count == 0, "No cross-source payload mismatch is expected");
  endfunction : check_matching

  function void check_duplicates(uvm_phase phase);
    int before_matches;
    before_matches = scoreboard.match_count;
    // Exact reviewed failure: the two final actual entries must remain unmatched.
    scoreboard.write_expected(scoreboard_contract_item::make(7, 10));
    scoreboard.write_actual(scoreboard_contract_item::make(7, 10));
    scoreboard.write_actual(scoreboard_contract_item::make(7, 20));
    scoreboard.write_actual(scoreboard_contract_item::make(7, 20));
    require(scoreboard.match_count == before_matches + 1, "Same-side actual false match");
    check_empty_errors(phase, 1);
    scoreboard.write_expected(scoreboard_contract_item::make(9, 30));
    scoreboard.write_expected(scoreboard_contract_item::make(9, 30));
    require(scoreboard.match_count == before_matches + 1, "Same-side expected false match");
    check_empty_errors(phase, 2);
    check_empty_errors(phase, 0);
  endfunction : check_duplicates

  function void check_controls();
    int before_matches;
    int before_count;
    int unsigned before_hooks;
    before_matches = scoreboard.match_count;
    before_count = scoreboard.transaction_count;
    before_hooks = scoreboard.hook_calls;
    scoreboard.enable_expected_port = 0;
    scoreboard.write_expected(scoreboard_contract_item::make(1, 1));
    scoreboard.enable_expected_port = 1;
    scoreboard.enable_actual_port = 0;
    scoreboard.write_actual(scoreboard_contract_item::make(1, 1));
    scoreboard.enable_actual_port = 1;
    scoreboard.disable_scoreboard();
    scoreboard.write_expected(scoreboard_contract_item::make(1, 1));
    scoreboard.write_actual(scoreboard_contract_item::make(1, 1));
    scoreboard.enable_scoreboard();
    require(scoreboard.transaction_count == before_count, "Disabled write counted activity");
    require(scoreboard.hook_calls == before_hooks, "Disabled write reached the matching hook");

    scoreboard.disable_entry_comparison();
    scoreboard.write_actual(scoreboard_contract_item::make(2, 2));
    scoreboard.write_expected(scoreboard_contract_item::make(2, 99));
    scoreboard.enable_entry_comparison();
    require(scoreboard.match_count == before_matches, "Disabled comparison counted a match");
    require(scoreboard.mismatch_count == 0, "Disabled comparison counted a mismatch");

    scoreboard.write_expected(scoreboard_contract_item::make(3, 30));
    scoreboard.write_expected(scoreboard_contract_item::make(3, 31));
    scoreboard.remove_entry(3);
    scoreboard.write_actual(scoreboard_contract_item::make(3, 31));
    scoreboard.write_actual(scoreboard_contract_item::make(4, 40));
    scoreboard.write_actual(scoreboard_contract_item::make(4, 41));
    scoreboard.remove_entry(4);
    scoreboard.write_expected(scoreboard_contract_item::make(4, 41));
    scoreboard.remove_entry(99);
    require(scoreboard.match_count == before_matches + 2, "remove_entry lost queue order");

    scoreboard.inject_actual = 1;
    scoreboard.write_expected(scoreboard_contract_item::make(5, 50));
    require(scoreboard.match_count == before_matches + 3, "Nested hook lost source context");
    require(scoreboard.last_expected.key == 5, "Nested hook expected identity is incorrect");
    scoreboard.compare_or_store_entry(scoreboard_contract_item::make(6, 60));
    scoreboard.write_expected(scoreboard_contract_item::make(6, 60));
    require(scoreboard.match_count == before_matches + 4, "Direct hook lost actual-side default");
  endfunction : check_controls

  task check_drain();
    bit drained;
    scoreboard.write_actual(scoreboard_contract_item::make(31, 10));
    scoreboard.write_actual(scoreboard_contract_item::make(31, 20));
    fork
      begin
        scoreboard.wait_for_scoreboard_drain();
        drained = 1;
      end
      begin
        #1ns;
        require(!drained, "Race scoreboard drained unmatched actual entries");
        scoreboard.write_expected(scoreboard_contract_item::make(31, 10));
        #1ns;
        require(!drained, "Race scoreboard drained while a duplicate remained");
        scoreboard.write_expected(scoreboard_contract_item::make(31, 20));
        #1ns;
        require(drained, "Race scoreboard did not drain after both matches");
      end
    join

    drained = 0;
    array_scoreboard.write_actual(scoreboard_contract_item::make(1, 70));
    fork
      begin
        array_scoreboard.wait_for_scoreboard_drain();
        drained = 1;
      end
      begin
        #1ns;
        require(!drained, "Array scoreboard drained before delayed expected entry");
        array_scoreboard.write_expected(scoreboard_contract_item::make(1, 70));
        #1ns;
        require(drained, "Array scoreboard failed to drain after the match");
      end
    join
    require(array_scoreboard.match_count == 1, "Delayed predictor match was lost");

    drained = 0;
    scoreboard.write_actual(scoreboard_contract_item::make(32, 10));
    fork
      begin
        scoreboard.wait_for_scoreboard_drain();
        drained = 1;
      end
      begin
        #1ns;
        require(!drained, "Race scoreboard drained before flush");
        scoreboard.flush_scoreboard();
        #1ns;
        require(drained, "Flush did not wake scoreboard drain");
      end
    join

    drained = 0;
    scoreboard.write_expected(scoreboard_contract_item::make(33, 10));
    fork
      begin
        scoreboard.wait_for_scoreboard_drain();
        drained = 1;
      end
      begin
        #1ns;
        require(!drained, "Race scoreboard drained unmatched expected entry");
        scoreboard.remove_entry(33);
        #1ns;
        require(drained, "remove_entry did not wake scoreboard drain");
      end
    join
  endtask : check_drain

  virtual task run_phase(uvm_phase phase);
    super.run_phase(phase);
    phase.raise_objection(this);
    check_matching();
    check_duplicates(phase);
    check_controls();
    scoreboard.disable_end_of_test_empty_check();
    scoreboard.write_actual(scoreboard_contract_item::make(99, 10));
    check_empty_errors(phase, 0);
    scoreboard.enable_end_of_test_empty_check();
    check_drain();
    check_empty_errors(phase, 0);
    // A custom BASE_T must construct both exact-specialization analysis imps.
    custom_scoreboard.expected_analysis_export.write(scoreboard_contract_item::make(0, 1));
    custom_scoreboard.actual_analysis_export.write(scoreboard_contract_item::make(0, 1));
    require(custom_scoreboard.custom_marker() == 32'h1234, "Custom BASE_T was lost");
    require(custom_scoreboard.transaction_count == 1, "Custom BASE_T imp did not dispatch");
    `uvm_info("SCOREBOARD_CONTRACT_PASS", "All scoreboard contracts passed", UVM_NONE)
    phase.drop_objection(this);
  endtask : run_phase
endclass : scoreboard_contract_test
