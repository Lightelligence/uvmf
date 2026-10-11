# Scoreboard contract fixture

This standalone UVM regression compiles the real scoreboard source headers. It
checks both arrival orders, repeated keys on each source, the reviewed same-side
false match, remaining-entry reports, disabled controls, remove/flush behavior,
nested virtual-hook callbacks, delayed predictor drain and a custom `BASE_T`.
The success marker is `SCOREBOARD_CONTRACT_PASS`; also require zero unexpected
UVM errors/fatals and a successful simulator exit. Three deliberate nonempty
reports are caught and asserted inside the test; other errors remain visible.

From the repository root, on an authorized licensed compute node:

```sh
vcs -full64 -sverilog -ntb_opts uvm-1.2 \
  +incdir+uvmf_base_pkg/src +incdir+scripts/tests/scoreboard_contract \
  scripts/tests/scoreboard_contract/scoreboard_contract_pkg.sv \
  scripts/tests/scoreboard_contract/tb.sv -o simv
./simv +UVM_TESTNAME=scoreboard_contract_test
```

```sh
xrun -64bit -sv -uvm \
  +incdir+uvmf_base_pkg/src +incdir+scripts/tests/scoreboard_contract \
  scripts/tests/scoreboard_contract/scoreboard_contract_pkg.sv \
  scripts/tests/scoreboard_contract/tb.sv +UVM_TESTNAME=scoreboard_contract_test
```

Submit compilation and simulation through the project's ETX/LSF workflow.
Python source guard checks alone do not establish runtime correctness.
