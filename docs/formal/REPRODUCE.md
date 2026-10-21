# Reproduce from a public source checkout

Use the v0.4.0 tagged checkout or release source ZIP. Python 3.11 is tested.
Commands below run from its root. Installation is a **source-checkout workflow**:
scripts, formal sources and fixtures remain in that checkout; installing the
Python wheel alone does not install these reproduction assets. No private
editable package, provider archive, LHAPDF grid or native engine is needed for
the first two routes.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt -r requirements-numerics.txt
.venv/bin/python -m pip install .
```

## Runtime route

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python examples/algebraic_closure.py --output results/closure.json
.venv/bin/python scripts/replay_coverage.py --inputs evidence/coverage/inputs.json --output results/coverage.json
.venv/bin/python examples/formal/cache_and_composition.py
.venv/bin/python scripts/replay_finite_plans.py --output results/finite-replay.json
```

The optional `DenseKernelCertificateTests` integration test is explicitly
skipped when the pinned library has not been built. All remaining tests,
12 analytic closure checks, saved 200-draw coverage replay and finite-plan
numerical replay run without Lean. This route makes no new kernel claim.
The tutorial and finite-plan replay also work from another directory when the
script is addressed by its checkout path; default fixtures resolve beside the
script, and output paths are chosen by the caller.

## Full formal route

Install the official Lean 4.21.0 toolchain using the
[Lean release](https://github.com/leanprover/lean4/releases/tag/v4.21.0) or an
existing elan installation, and put its `lake` on PATH. The project pin selects
that version; no global default change is required.

```sh
.venv/bin/python scripts/check_formal.py --output-dir results/formal-check
.venv/bin/python -m unittest discover -s tests -v
```

This route requires all 24 theorem reports, four full selected positive roots,
one negative root, eight selected-plan evaluations and the dense regression.
The regression must execute without a skip. The command also repeats all 100
full-snapshot scalar comparisons. `PORTABLE.json`, literal certificates,
statement/axiom logs and runtime comparisons are written to the new directory.
The [shipped execution evidence](../../evidence/formal/verification) records
an actual clean source replay; it is not a substitute for a fresh run.

## Optional upstream regeneration

[`run_formal_007.py`](../../scripts/run_formal_007.py) can independently rebuild
the analytic real-geometry wire from `configs/external/observation_contract.json`:

```sh
.venv/bin/python scripts/run_formal_007.py --output-dir results/geometry-regenerated
```

This command explicitly reports the finite-window provider bridge
`not_requested`. It is not the full formal route. Rebuilding the original
finite-window coefficients additionally requires the separately retained
provider companion `typed_tmd_provider_inputs_003_07a9631f0188.zip`, SHA-256
`bd45cfca6831f5ad6da8fe09ca0fb5797c29fab05210489eb829df20c379f397`, containing
`provider_inspection.json`, `provider_query_plan.json.gz` and
`provider_snapshot.json.gz`. Supply their directory with `--h004-provider-dir`.
That 111-MiB companion is not a release dependency and is not distributed here;
without it, full upstream regeneration is **blocked**, not passed. Shipped
finite coefficients make the ordinary numerical and formal routes complete.
Newly generated wires have their own byte identities and must not overwrite
accepted fixtures or be substituted into existing certificate receipts.

## External physics route

Follow [INSTALL_EXTERNAL.md](../INSTALL_EXTERNAL.md) for the pinned backend,
PDF data and native build. The saved native benchmark is historical evidence
from v0.3.0, preserved byte for byte. Version 0.4.0 does not rerun the native
campaign, alter fits/covariance/seeds or claim a new physical calculation.
The previous native release and the new finite-plan proof have separate scopes.
