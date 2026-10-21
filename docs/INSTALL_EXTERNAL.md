# Native build and reproduction

The tested platform is macOS arm64, Python 3.11.17, NumPy 1.26.4,
SciPy 1.14.1, GNU Fortran 16.2.0 and LHAPDF 6.5.5. The selected native
build is serial (`-O2 -fPIC -fallow-argument-mismatch`, no OpenMP).
Other platforms are not covered by this native execution receipt.

Use a project-specific environment. The native extension uses NumPy's
legacy f2py build path, so Python/NumPy/build-tool versions matter.
Do not use an unrelated PyPI package named `harpy`.

```sh
conda create -y -p .conda-external --file environment-external-osx-arm64.lock
.conda-external/bin/python -m pip install .
.conda-external/bin/python scripts/build_lhapdf_006.py --work native/lhapdf-build --prefix native/lhapdf
.conda-external/bin/python scripts/prepare_external_006.py --cache native/cache --env-prefix .conda-external --fortran .conda-external/bin/arm64-apple-darwin20.0.0-gfortran --lhapdf-prefix native/lhapdf --output results/build
```

The compiler path shown is the tested conda-forge macOS arm64 executable.
The explicit environment lock includes package URLs and SHA-256 digests.
Pass the actual Fortran executable on another platform; that is a new build
requiring validation. The LHAPDF helper downloads its exact official source
archive and installs only in the requested fresh prefix, without Python
bindings. The external preparation script downloads pinned source commits,
selects the bundled SV19 model and verifies the two central PDF input files.
It preserves the upstream license and makes no physics-kernel patch.

Run the frozen experiment and its validation with fresh output directories:

```sh
.conda-external/bin/python scripts/run_external_006.py --build results/build --plan configs/external --stage campaign --output results/experiment
.conda-external/bin/python scripts/run_external_006.py --build results/build --plan configs/external --stage validate --previous results/experiment --output results/validation
.conda-external/bin/python scripts/run_external_006.py --build results/build --plan configs/external --stage refine_selected --previous results/validation --output results/refinement
.conda-external/bin/python scripts/run_external_006.py --build results/build --plan configs/external --stage timing --output results/timing
```

The campaign produces a constructor rejection with zero backend/optimizer
calls at the invalid boundary, generating means, one fixed noise vector,
four five-start fits and held-out predictions. The validation stages compare
independent observation quadrature with native bin integration at every
selected fit, refine each coordinate, and test additivity and convention
transport. The timing stage must run while no other experiment/build is
competing for CPU; it records 30 alternating paired blocks per workload.

The native bin API is considerably slower than the independent point-kernel
quadrature used in the fits. Full validation can take tens of minutes; the
runtime report gives measured workloads rather than a universal promise.
The timing comparison uses identical numerical algorithms and native calls
on both sides, including full NP-vector rebinding.

The source lock is portable. `runtime.json` is a local build receipt and is
created afresh; it is not an input to copy from another machine. The frozen
plan must match the built source, model, constants and numerical input hashes.
Saved-array replay and an analytic test-suite pass are not substitutes for
executing this native pipeline.

Compare a fresh campaign to the retained scientific evidence:

```sh
.conda-external/bin/python scripts/verify_external_replay_006.py --reference evidence/experiment --replay results/experiment --output results/replay_comparison.json
```

This command requires exact binary64 agreement, including optimizer histories,
and excludes only elapsed wall-clock fields. Exact replay passed on the tested
macOS arm64 stack. Other platforms may need a separately justified numerical
comparison; a failure is retained rather than silently relaxing this check.

Regenerate the figures from saved arrays without rerunning fits:

```sh
.venv/bin/python -m pip install -r requirements-plots.txt
.venv/bin/python scripts/plot_external_006.py --campaign evidence/experiment --plan configs/external --timing evidence/timing --output results/figures
```
