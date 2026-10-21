# typed-TMD

Typed scientific contexts and observation maps for a small, auditable TMD
workflow. The external example uses a pinned arTeMiDe SV19 Drell–Yan
calculation and checks a concrete mistake: substituting a point density for
a finite-bin average, even when units and array shapes match.

The software keeps the observation operation, input/model identity,
parameter dependencies and construction history explicit. A mismatched
observation is rejected when the fit problem is constructed. The controlled
experiment measures what that correction changes using synthetic data,
one native parameter and a fixed held-out set. It does not reproduce the
published global extraction or compare two independent QCD engines.

## Quick start

Use Python 3.11 in a project environment:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt -r requirements-numerics.txt
.venv/bin/python -m pip install .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python examples/algebraic_closure.py --output results/closure.json
.venv/bin/python scripts/replay_coverage.py --inputs evidence/coverage/inputs.json --output results/coverage.json
```

The closure is an exact synthetic Gaussian fixture, with twelve checks. It
is not physical LL/NLL evolution. The coverage command replays the same 200
saved noise vectors and Jacobian; it does not redraw noise, run the external
backend or refit. The linear and nonlinear controls both give 184/200 nominal
95% inclusion. This post-hoc observation does not establish calibration.

For native execution, use [the build and reproduction instructions](docs/INSTALL_EXTERNAL.md).
The optional engine, source models and PDF grids are fetched from pinned
origins with digests, rather than included in this software tree.

## Examples and evidence

- [Observation semantics and source audit](docs/EXTERNAL_SV19.md)
- [Construction, refusal and repair](docs/EXAMPLES.md)
- [Measured comparison, fits and timing](docs/RESULTS.md)
- [Claim/evidence map](docs/CLAIM_EVIDENCE.md) and [retained failures and corrections](docs/ATTEMPT_HISTORY.md)
- [Program summary](docs/PROGRAM_SUMMARY.md)
- [Development roadmap](docs/ROADMAP.md) and [next concrete formal specification](docs/REPRESENTATION_AND_LEAN_SPEC.md)

All numerical results include machine-readable arrays and scoped execution
receipts. Analytic test doubles exercise the adapter without executing the
external engine; CI reports that scope explicitly. The existing Lean 4.21.0
seed concerns abstract composition. It proves neither Python/native execution
nor QCD factorization, and the new observation checks remain runtime checks.

The native backend is process-global. Use one owning session per process;
out-of-band harpy/FFI mutation is outside the adapter's supported contract.
Only parameter-independent quadrature geometry is cached. A model/provider
change requires a new identity and an isolated native process.

## Attribution and release state

SV19 is the calculation of I. Scimemi and A. Vladimirov,
[JHEP 06 (2020) 137](https://doi.org/10.1007/JHEP06%282020%29137).
See [third-party notices](docs/THIRD_PARTY_NOTICES.md) for the separate
upstream code and data terms. The original software is by Dustin Keller and
is available under the [MIT license](LICENSE). Use [CITATION.cff](CITATION.cff)
for software attribution and the repository issues for project contact.
No software DOI has been assigned; a GitHub release does not itself assign one.
