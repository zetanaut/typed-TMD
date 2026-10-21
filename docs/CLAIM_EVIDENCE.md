# Claims and executable evidence

Paths below are relative to the public repository root. All inference outputs
are synthetic; the observed-data input supplies geometry and cuts only.

| Claim | Evidence | Boundary of the claim |
|---|---|---|
| Wrong point/bin observation is refused before evaluation | `evidence/experiment/rejection.json`; `tests/test_observations.py` | Runtime constructor check; no proof of arbitrary caller metadata |
| Native and typed routes make the same requests and agree exactly | `evidence/pilots/nominal/native_typed_requests_and_results.json` | Same backend, not independent physics |
| Independent observation quadrature agrees with native integration | `evidence/validation/selected_validation_checks.json`, arrays; `evidence/refinement/` | Same point physics kernel, independent integration; empirical convergence |
| Midpoint misuse shifts the fitted c0 | `evidence/experiment/data.json`, `fits.json`, `consequences.json`; `docs/figures/external/fit_table.csv` | One frozen parameter, covariance and noise draw; local sensitivity units, not calibrated confidence |
| Fit consequences exceed the declared numerical budget | `evidence/numerical_resolution.json` | Empirical response budget and objective perturbation inequality; no rigorous universal integration bound |
| Saved coverage deficit also occurs in the linear control | `evidence/coverage/inputs.json`, manifest and projection verification; `scripts/replay_coverage.py` | Exact 200 saved draws; post-hoc diagnosis, no refitting or general recalibration |
| Checking overhead measured with equal native work | `evidence/timing/timings.json` | 30 alternating paired blocks, one tested platform and serial backend; no universal speed claim |
| Clean environment reproduces the external calculation | `evidence/fresh_install.json`, `evidence/fresh_replay_comparison.json`; final release validation asset | Independently fetched/built backend and grid; all scientific campaign fields compared exactly except elapsed time |
| Analytic/core checks and retained regression pass | `evidence/core_validation.json`; CI and tests | Public CI runs analytic fixtures and coverage, not the native engine |
| Existing Lean seed builds | `lean/lean-toolchain`, Lean files, core validation receipt | Abstract composition only; no Python/Fortran/QCD proof |
| Dependency-preserving runtime records exist | `src/typed_tmd/observations.py`, adapter, response plans | Runtime scientific metadata and the concrete finite-plan checker have separate scopes; see `docs/formal/` |

`SOURCE_MAP.json` maps copied payloads to their private source identities.
`configs/external/FREEZE.json` preserves the prospective experiment statement
and scientific-file hashes. Each release manifest identifies that version’s immutable public bytes. The v0.3.0 native evidence is preserved in v0.4.0.
[Release status](RELEASE_STATUS.md) records the accepted scope, asset hashes
and publication verification. Public and private trees have different inventories.

## Finite-plan evidence added in v0.4.0

The machine-readable [CLAIM_EVIDENCE.json](../CLAIM_EVIDENCE.json) records stable
claim IDs, actual theorem declarations, hypotheses, commands, artifact hashes
and explicit status. Its proof inventory links every selected root to the
parent wire and generated certificate.

| Claim | Public implementation/evidence | Scope |
|---|---|---|
| Accepted cache plans preserve the admitted family | `formal/007/TypedTMDPlan/Core.lean`; `evidence/formal/verification/` | Fixed pure Model and fixed-coordinate agreement; exact finite semantics |
| Interfaces/arrows compose by substitution | `formal/007/TypedTMDPlan/Category.lean`; theorem inventory | Concrete source category, not a general plan-syntax category |
| Staged checked plans require a transported reference | `Arrow.checked_composition`; `examples/formal/cache_and_composition.py` | Two local checker acceptances and preserved variation slice |
| Frozen fitted-kernel reuse is refused | `tests/test_finite_plan.py`; runtime tutorial | Reference-value closure alone misses the changed sensitivity |
| Real-sized finite snapshots execute | `evidence/formal/fixtures/`; `scripts/replay_finite_plans.py` | 100 scalar target comparisons; four selected positive roots, not every root certified |
| Analytic callback traverses real geometry | Same fixture/replay and selected bin certificate | No native arTeMiDe proof or new native run |

The full formal command fails on missing Lean and rebuilds from source. The
runtime CI job may skip its explicitly optional dense certificate test; the
mandatory formal job cannot. Historical native execution is not counted as a
new proof or campaign in this release.
