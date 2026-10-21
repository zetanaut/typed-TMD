# External SV19 observation comparison

The H006 case uses one native arTeMiDe engine. Native/typed agreement checks
the adapter, while separate quadrature checks the observation integral using
the same physics kernel. Neither comparison is an independent QCD derivation
or a reproduction of the published global fit. Execution status and measured
results are recorded separately; this document specifies the source bridge.

## Pinned inputs and physics

The backend is arTeMiDe v2.05, commit
`ea0af1a75e21e316c1ac4ece51933988836a6650`, with its bundled SV19 model,
`Models/SV19/constants-files/DY_nnlo/const-NNPDF31_NNLO`, and the mean row
of `Models/SV19/Replicas/DY_nnlo/DY_NNPDF31_nnlo.rep`. The complete native
parameter vector is `(1.86041, 0.029551, 0.253434, 9.04351, 346.999,
2.47992, -5.69988, 0, 0)`. The grid-initialization row is distinct from this
published mean and must not replace it.

DataProcessor commit `18967d1c52dabf93e17a640405b548071904cfcc` supplies
`DataLib/unpolDY/A8-00y04.csv`, referencing ATLAS arXiv:1512.02192, and the
author fit's parameter-domain instructions. No experimental measurement is
fit in this controlled study; only the published bin geometry and conventions
are used to define synthetic observations.

The process code `(1,1,5)` denotes unpolarized proton-proton neutral-current
DY with photon, Z and interference, including the native quark/antiquark sum
through bottom. The spectrum is a low-qT TMD prediction without a matched
large-qT Y term. The existing H004 light-current finite-window benchmark is
a different calculation and remains unchanged.

NNPDF31_nnlo_as_0118_1000 member 0 supplies the PDFs and native LHAPDF
coupling. The native source uses its own momentum-weighted PDF interface;
this external kernel is not substituted into the core `f_i(x,Q)` provider.
Set and member, native library, grid hashes, source/model hashes, actual
compiler and linked-library receipts must accompany an execution.

The source interprets the configuration label `NNLO` as cusp coefficients
through order 3, noncusp and rapidity coefficients through order 2, resummed
rapidity and zeta-line orders 2, and hard/matching coefficients through
alpha_s squared. External PDF evolution and alpha_s running retain the PDF
set's conventions. Evolution solution type 3 uses the native zeta-prescription
model. The mu and rapidity scale construction, flavor thresholds,
electroweak constants, exact-x kinematic option and disabled pi-squared
resummation are retained from the pinned constants and source, not inferred
from an order label alone.

The SV19 evolution model has

```
b_star = b / sqrt(1 + b^2/B^2)
D_NP(mu,b) = D_resum(mu,b_star) + c0*b*b_star
```

Only `c0` is varied in the proposed local study; it has units GeV², while B
has units GeV⁻¹. The remaining eight values stay fixed. The local domain
`[0.001,0.1] GeV²` lies within the author's broader `[0.001,5.0]` search
domain. This is an explicitly restricted one-parameter synthetic study, not
an identification of c0 with H004's g2. Rank is measured before interpreting
fit displacements.

The native Fourier-Bessel normalization and electroweak prefactors remain
inside the pinned kernel. The observation adapter applies only the audited
2q and 2Q measure factors and source rapidity multiplier; it adds no Fourier
or azimuthal factor. The point output includes those physics conventions.

## Observation map and source audit

For the selected native interface,

```
h(q,Q,y;theta) = d sigma / (dq^2 dQ^2 dy), in pb/GeV^4
S_i(theta) = integral_Bi 4*q*Q*h(q,Q,y;theta) dq dQ dy, in pb
mu_i(theta) = 2*S_i(theta)/(q_plus-q_minus), in pb/GeV
```

The factor 2 in the last line combines the symmetric positive/negative
rapidity bins; it is already encoded in the dataset's theory factor. It is
not an azimuthal 2*pi factor. There is no division by the mass or rapidity
interval: those variables are integrated, while only qT is averaged.

The geometry-only selection retains all source-ordered bins satisfying
`qT_upper/Q_lower <= 0.25`. For A8-00y04 this gives seven bins, qT from 0
to 16 GeV, Q from 66 to 116 GeV and y from 0 to 0.4. The native fiducial
cuts are pT(lepton) > 20 GeV and eta in [-2.4,2.4]. The final two bins are
held out according to the handoff rule for fewer than nine bins.

The following pinned code supplies the bridge, with file/line ranges as
navigation aids rather than independent verification:

- [`harpy.py`, DY methods](https://github.com/VladimirovAlexey/artemide-public/blob/ea0af1a75e21e316c1ac4ece51933988836a6650/harpy/harpy.py#L849): integrated bins versus BINLESS requests.
- [`TMDX_DY.f90`](https://github.com/VladimirovAlexey/artemide-public/blob/ea0af1a75e21e316c1ac4ece51933988836a6650/src/TMDX_DY.f90#L442): prefactors and pb conversion; Q quadrature multiplies by 2Q (around line 839), qT quadrature by 2qT (around line 918), and BINLESS returns the unintegrated response (around line 1582).
- [`TMDF.f90`](https://github.com/VladimirovAlexey/artemide-public/blob/ea0af1a75e21e316c1ac4ece51933988836a6650/src/TMDF.f90#L318): the photon/Z proton-proton channel and signed flavor legs.
- [`TMDR.f90`](https://github.com/VladimirovAlexey/artemide-public/blob/ea0af1a75e21e316c1ac4ece51933988836a6650/src/TMDR.f90#L190): actual evolution-order inventory.
- [`A8-00y04.csv`](https://github.com/VladimirovAlexey/artemide-DataProcessor/blob/18967d1c52dabf93e17a640405b548071904cfcc/DataLib/unpolDY/A8-00y04.csv): ordered geometry, absolute-spectrum flag, cuts and theory factors.
- [`SV19 fit program`](https://github.com/VladimirovAlexey/artemide-DataProcessor/blob/18967d1c52dabf93e17a640405b548071904cfcc/FittingPrograms/SV19/FitDY_SV19.py): declared original parameter domain.

## Validation and misuse

N1 invokes harpy directly and assembles source theory factors without typed
observation helpers. N2 submits the same requests through the typed adapter,
including off-central parameters and a change/reset sequence. N3 independently
integrates BINLESS using tensor Gauss-Legendre quadrature, with mass segments
around the Z resonance and independent refinement of qT, Q and y. The native
Simpson/bin-integration precision is checked separately.

The first numerical pilot used native minimum qT Simpson count 16 and
Q/y tolerance 1e-6. It missed the componentwise comparison target in the
first bin (maximum relative discrepancy 1.174e-4). Tightening the native
settings to minimum 32 and Q/y tolerance 2e-7 reduced that discrepancy to
8.015e-6 against the finest pilot quadrature. Both pilot receipts are kept.
The native auto rule adds two sections for the two 3-GeV-wide bins, so the
nominal counts are 32 for the first five bins and 34 for the last two.
A further minimum-64, Q/y-1e-7 run checks convergence; it is not a relaxed
acceptance threshold. The Fourier tolerance is 1e-6 in both configurations.

Production fits use the separately implemented finite-bin Gauss-Legendre
integral of the native point kernel, validated against the adaptive native
bin API at the generating and selected fitted parameters. Generating means
come from the native bin API. This reduces cost while preserving the full
declared observation integral and parameter dependence. The overhead study
compares plain and typed execution of the identical point-kernel requests
and Gauss-Legendre map, not different integration algorithms.

The isolated fault harness substitutes the qT-midpoint density after proper
Q² and y integration for the qT-bin average. Both outputs have units pb/GeV;
their observation operations differ. `ObservedFitProblem` rejects this
point-density plan before any backend or optimizer invocation. The corrected
finite-bin integrals and supported average conversions are admitted. Numerical
and inference consequences must be measured only after the case is frozen.

## State, representation and trust

The adapter serializes native calls, binds the complete nonperturbative
vector at every proposal, and caches only parameter-independent quadrature
geometry. Plans preserve source-expression identity, numerical-plan identity,
parameter dependencies and the origin of compatibility checks. Fixed-model
changes have different identities. Provider/configuration changes retire the
session and require a new isolated process.

The native library is process-global and has no trustworthy complete state
getter. Direct out-of-band mutation through harpy or its FFI is unsupported;
metadata cannot prove that such a mutation did not occur. The run exclusively
owns its backend process. A caller forging a response's metadata likewise
lies outside the adapter's audited binding. The checks are runtime evidence,
not Lean-verified compilation or verification of the native physics engine.
