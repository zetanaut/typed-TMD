# Sample output

These files show test-run output from the unchanged examples in version 0.4.1:

- `cache_and_composition.json`: runtime tutorial showing unsafe cache refusal,
  a fixed-parameter restriction and transported-reference composition.
- `closure.json`: the `results/closure.json` produced by the analytic Gaussian
  closure example, including all 12 checks and their declared tolerances.

From an installed source checkout, reproduce them with:

```sh
mkdir -p results
.venv/bin/python examples/formal/cache_and_composition.py > results/tutorial.json
.venv/bin/python examples/algebraic_closure.py --output results/closure.json
```

The supplied files were generated with Python 3.11.17, NumPy 1.26.4 and SciPy
1.14.1 on macOS/arm64. Numerical results on another platform should be assessed
with the tolerances reported by the closure checks rather than requiring
identical JSON bytes.

The tutorial is Python runtime evidence; run `scripts/check_formal.py` for
kernel-checked proof evidence. The Gaussian example is an exact analytic
fixture, not physical LL/NLL evolution, realistic data or an extraction.
