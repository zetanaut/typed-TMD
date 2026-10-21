# Observation construction, rejection and repair

The pinned source exposes a point response in `dqT² dQ² dy`. The requested
observable is an average in `dqT`, with mass and rapidity integrated and
native lepton cuts applied. Equal final units (`pb/GeV`) do not establish
equality of these observation maps.

After `initialize` in the native runner has verified the locks and created
an owning `session` and `contract`, construction is explicit:

```python
from typed_tmd.observations import ObservedFitProblem, ObservationMismatch

midpoint = session.plan(contract, operation="qT_point_density")
try:
    ObservedFitProblem(contract, midpoint, data, sigma)
except ObservationMismatch as error:
    print(error.diagnostic)

integrated = session.plan(contract, operation="independent_bin_average")
problem = ObservedFitProblem(contract, integrated, data, sigma)
residual = problem.residuals((0.029551,))
```

The first constructor refuses the observation before any response or
optimizer evaluation. The second integrates the full bin with `4*qT*Q`,
applies the source rapidity factor, and divides by the qT width. It checks
the same input/model identity on subsequent parameter evaluations.

`integrated.record()` preserves the source expression, parameter dependencies,
source and plan digests, quadrature settings, state epoch and origin of the
compatibility check. These are runtime records, not a formal proof certificate.
The adapter supplies the response meaning according to its audited code path;
arbitrary caller-forged metadata is outside that trust boundary.

`convert_averages` supports `dqT` to `dqT²` averages of the **same** integrated
yield and the reverse conversion. A fit must transform data and covariance
with the same diagonal map: `data' = R data`, `covariance' = R covariance R.T`.
The midpoint approximation is not such an exact convention transformation.

The only intentionally unchecked fit path is in the isolated experiment
harness. It retains the true `point_density` label and bypasses the fit
constructor explicitly, so the experiment can measure the consequence.
Production assembly has no silent acceptance option for this mismatch.
