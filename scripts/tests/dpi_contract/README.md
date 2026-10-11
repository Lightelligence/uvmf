# Generated API regression

`prepare.py <new-output-directory> --mode struct|object [--unparameterized]`
generates a fresh fixture from the same YAML used by `test_generated_contracts.py`.
It replaces only the generated protocol customization blocks with deterministic,
clocked test behavior. Production transport adapters, configuration code, monitor
callbacks, sub-environment arrays and top sequence typedefs remain generated code.

The fixture requires real UVM and DPI C++ linkage. `metadata.json` lists the C++
translation units and include directories; `sources.f` lists SV inputs and include
paths. Generate `dpiheader.h` with the selected simulator from these exact SV
inputs. Do not use an empty or manually invented DPI header. Compile C++ with
`-Werror=return-type` to check the bridge task return contract.

Use `scripts/run_contract_checks.py` on an authorized Red Hat compute node through
the project's `dv-etx-workflow` and `bsub` requirements. The fixture checks both
arrival directions through the driver, configuration propagation to BFMs, monitor
callback dispatch with a nondefault parameter, nested array element ordering,
omitted activity defaults, and starting the generated top sequence on its typed
virtual sequencer. Completion requires `GENERATED_CONTRACT_PASS`, a zero process
exit and no UVM errors or fatals. The test protocol validates API transport; it does
not establish correctness of any user's protocol implementation.
