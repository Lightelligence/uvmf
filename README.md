This is the UVMF 2023.4_2 which is used to generate verification IPs and environments.

## Red Hat Linux workflow

Generator output targets VCS, Xcelium, and Synopsys VIP. It omits Questa,
legacy VIP configurator output, generated Makefiles, IDE metadata, legacy file
lists, and unused bench output. Generated source defaults to `.sv`; only
header-like files such as macros and typedefs remain `.svh`.

```bash
python3 scripts/yaml2uvmf.py <yaml-files>
python3 scripts/yaml2uvmf.py --simulator xcelium <yaml-files>
python3 scripts/yaml2uvmf.py --check -d <existing-dv-dir> <yaml-files>
python3 scripts/run_verible_lint.py
```

The generated Bazel profile defaults to `--simulator vcs`. Select
`--simulator xcelium` to emit Xcelium simulator settings and the
`@vip_xcelium_svt_pkg//:pkg` dependency instead of VCS-only options and
`@vip_vcs_svt_pkg//:pkg`.

`--check` validates all YAML references and reports obsolete generated output
without writing or deleting anything.

## Selecting a top-level sequence

The generated top-level environment sequence base is parameterized, so it
does not have a stable factory string name for `+uvm_set_type_override`.
Select a registered derived sequence directly instead:

```python
verilog_dv_test_cfg(
    name = "sys_spi_apb_test",
    inherits = [":spi_base"],
    sim_opts = {
        "+UVMF_TOP_LEVEL_SEQUENCE=": "sys_env_pkg::spi_apb_seq_c",
    },
)
```

The value must match the factory name registered by the sequence's
`` `uvm_object_utils `` macro. The selected class must derive from the
generated top-level environment sequence specialization. Simulation stops
with a fatal message if the name is not registered or the type is
incompatible.

## Synopsys VIP integration

Synopsys VIP environments use the same hierarchy as any other reusable IP
environment. Define them as existing environments and instantiate them through
`subenvs`:

```yaml
uvmf:
  environments:
    svt_apb:
      existing_library_component: true
    soc:
      subenvs:
        - name: ucie_apb_env
          type: svt_apb
          count: 6
```

An `existing_library_component` does not create a local Bazel package. Its
SystemVerilog package import is preserved, while a generated local Bazel
dependency is emitted only when that package's `BUILD` file already exists.
Add any external VIP library dependency in the generated BUILD custom block.

## Array-backed counted sub-environments

Counted UVMF sub-environments remain independent instances by default. To
generate configuration and environment handles as arrays, opt in on the
counted sub-environment:

```yaml
    soc:
      subenvs:
        - name: ucie_apb_env
          type: svt_apb
          count: 5
          array: true
```

This generates `ucie_apb_env_config[5]` and `ucie_apb_env[5]`, while keeping
the UVM component names `ucie_apb_env_0` through `ucie_apb_env_4`. Register
model names and base addresses must still use `{index}` when supplied.
YAML TLM paths retain those UVM instance names (for example `ucie_apb_env_0.out`);
generated SystemVerilog connections use indexed members (`ucie_apb_env[0].out`),
including nested arrays. Archived YAML retains the original instance paths.

## Register model hierarchy

Select only the IP register models needed by the parent and provide their SoC
address mapping. Counted instances use `{index}` where names or addresses must
be unique:

```yaml
    soc:
      subenvs:
        - name: ucie
          type: ucie
          count: 2
          use_register_model: true
          reg_block_instance_name: ucie_{index}_rm
          base_address: UCIE_BASE + {index} * UCIE_STRIDE
      register_model:
        use_adapter: false
        use_explicit_prediction: false
```

The generated parent block calls `default_map.add_submap()` for each selected
IP register block.

## Shared project defines

Project-specific macros and constants are expected to be hand-maintained in
project files such as `tb/testbench/tb_defines.svh`, not generated from YAML.
The generated `tb/testbench/BUILD` exports `*.svh`, so an environment BUILD can
pull the macro file into its file list through the preserved custom block:

```python
in_flist = [
    # pragma uvmf custom in_flist_prepend begin
    "//hw/dv/project_benches/sys/tb/testbench:tb_defines.svh",
    # pragma uvmf custom in_flist_prepend end
    "src/sys_env_typedefs.svh",
] + glob([
    "*_pkg.sv",
]) + glob([
    "src/*_intf.sv",
])
```

Keep `tb/parameters` available for existing bench-local package code, but do
not depend on it from reusable environment packages.

Install Verible's `verible-verilog-lint` on `PATH` before running lint. An
alternate installation can be selected with `VERIBLE_LINT` or
`--verible-lint`. Lint includes SystemVerilog and Verilog generated under
`uvmf_template_output`.

When regenerating an existing project, omit `--overwrite` for a non-destructive
refresh or use `--merge_source` to preserve UVMF custom blocks. Merge always
creates a backup before updating the existing project. The `--clean` option
removes only obsolete files that carry a UVMF generator signature, have no
custom-block content, and match an approved legacy output kind. Unsigned files
and entire directories are retained because their names alone do not prove
generator ownership.

Bazel `BUILD` files under useful environment and bench directories contain
minimal `verilog_dv_library`, `verilog_dv_tb`, and `verilog_dv_test_cfg`
targets. Project RTL, VIP, simulator options, waivers, and test configurations
belong in the provided `pragma uvmf custom` blocks so merge preserves them.
The `--check` and `--clean` paths do not modify these files.

Direct `-o/--overwrite` generation is rejected when the destination is not
empty. Upgrade an existing generated tree with `--merge_source=<existing-dv-dir>`;
the merge creates a complete backup before changing files and preserves all
`pragma uvmf custom` blocks. Hand edits outside those blocks remain in the
backup and must be reviewed and ported manually because they cannot be
distinguished safely from obsolete generated code.

For existing projects with local edits, use this flow:

```bash
python3 "$UVMF_HOME/scripts/yaml2uvmf.py" \
  <yaml-files> \
  -d "$PROJ_DIR/hw/dv" \
  --check

python3 "$UVMF_HOME/scripts/yaml2uvmf.py" \
  <yaml-files> \
  -d "$PROJ_DIR/hw/dv" \
  --merge_source="$PROJ_DIR/hw/dv"
```

This preserves:

- all content inside matching `pragma uvmf custom` blocks;
- project-owned files that are not regenerated at the same path, such as hand
  written `tb/testbench/*.svh` files;
- a complete `<existing-dv-dir>_bak_N` copy before any update.

It cannot automatically preserve arbitrary edits made in generated-file regions
outside `pragma uvmf custom` blocks. Review the backup for those edits and move
them into a custom block or a project-owned include file before relying on future
regeneration.

For legacy SV additions immediately adjacent to known customization positions,
`--merge_migrate_unmarked` can bootstrap the move into custom blocks:

```bash
python3 "$UVMF_HOME/scripts/yaml2uvmf.py" \
  <yaml-files> -g <top-component> \
  --merge_source="$PROJ_DIR/hw/dv" \
  --merge_migrate_unmarked
```

This opt-in option accepts insertion-only changes at four positions:

- `package_item_after_configuration`: package items after the configuration
  include and before virtual sequencer/environment types;
- `class_item_before_sequencer`: environment members before the virtual
  sequencer typedef;
- `build_phase_components`: construction after generated child components,
  before register-model and virtual-sequencer construction;
- `new_pre_config`: configuration initialization immediately after `super.new`,
  before child configuration construction.

The remaining nonblank generated SV/SVH scaffold must match, and migration
must not reorder code across existing custom blocks. Unsupported additions,
replacements or deletions abort the entire merge without changing the project.
Use this option before changing YAML or upgrading an unrelated template; port
ambiguous edits manually using the complete backup. Non-SV files retain normal
custom-block merge behavior. Default merge behavior is unchanged. Destination
file/directory symlinks are rejected so merge cannot overwrite their targets.

Run the regeneration safety regression with:

```bash
python3 scripts/run_smoke_checks.py
```

For a SoC with many sub-VIP YAML dependencies, place one YAML path per line in
`soc_uvmf_inputs.list`. The `-F` option resolves relative paths from the list
file location. Parse all dependencies but generate only `soc`:

```bash
set -euo pipefail

python3 "$UVMF_HOME/scripts/yaml2uvmf.py" \
  -F soc_uvmf_inputs.list \
  -g soc \
  -m "$PROJ_DIR/hw/dv"
```

Existing wrappers that use `--merge_debug` and remove their debug output after
the generator exits remain supported. Without `--merge_debug`, the generator
creates and removes its own uniquely named merge scratch directory.

The legacy `-g soc` selector remains supported. Type-qualified selectors such
as `-g environment:soc` and `-g bench:soc` avoid ambiguity when component names
overlap. Bench `active_passive` and `interface_params` entries may use a stable
hierarchical selector such as `path: environment.spi0.apb_agent`; legacy
`bfm_name` selectors remain supported.

Verible lint is independent of generation and can be run by GitLab CI over the
complete DV source tree:

```bash
python3 "$UVMF_HOME/scripts/run_verible_lint.py" "$PROJ_DIR/hw/dv"
```

## Continuous integration

GitHub Actions runs `Smoke checks` for every pull request targeting `main`.
Same-repository branches also run `Red Hat Bazel` on a self-hosted runner with
the `self-hosted`, `linux`, `x64`, and `redhat` labels. The Red Hat runner must
run Actions Runner 2.329.0 or newer and provide Python 3, Bazel, Git, SSH, and
non-interactive SSH access to the `rules_verilog` repository configured in
`WORKSPACE`.

Protect `main` with a GitHub ruleset that requires a pull request and the
`Smoke checks` and `Red Hat Bazel` status checks. Also require the branch to be
up to date and block force pushes. Fork pull requests intentionally do not run
on the self-hosted runner.
