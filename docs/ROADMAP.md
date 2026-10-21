# Typed hadronic computation: scientific and formal-development roadmap

## Purpose and scope

The long-term aim is AI-assisted multidimensional parton extraction and constructive derivation/proof of factorization for specified families of processes, using a physically realized axiomatic/homotopical organization of hadronic physics. This is a discovery program: it seeks construction and extension principles that can establish new physical results, not just a taxonomy of known calculations. It does not assume that every process admits a chosen factorization.

The immediate publication remains a pragmatic CPC methods paper. Category theory and Lean stay, and may expand when they establish a useful property of the executed computation. They are not automatically removed to make the paper simpler. What should shrink is unsupported abstract framing and any suggestion that a generic composition lemma proves a numerical TMD calculation.

## Current state, precisely

- Core regression: typed records/expressions, synthetic controls, a finite-window QCD-input diagnostic, two-parameter closure/coverage and independent scalar assembly. These are regression fixtures, not a full experimental/global extraction. The current fresh execution is on macOS arm64; older platform receipts retain their own scope.
- Reporting repair: structured and flat gate statuses are recognized, with failure precedence and explicit missing checks. Package/import versions agree.
- Coverage diagnostic: executed on the exact saved noise/Jacobian arrays; the elevated empirical quantile also occurs in the exactly linear rank-two control. This is post-hoc diagnostic evidence, not calibration.
- Lean 4.21.0 seed: conditional transformation/composition statements, with no proved correspondence to the Python compiler, external backend or floating-point arithmetic.
- External comparison: the pinned SV19 adapter, independent observation integration, rejection and bounded fit are implemented. Measured validation and release states are recorded separately in the results report.
- Concrete translation checker, dependency theorem, categorical realization and higher structures: specifications/research tasks, not completed proofs.

## Parallel responsibilities

| Track | Implementation and evidence | Mathematical specification and review |
|---|---|---|
| External comparison | Pin/build backend and fit inputs; inspect source semantics; implement native/typed/bin-integration routes; measure correction | Fix observation maps, admissibility and numerical/statistical claim boundaries; review external evidence |
| Extraction diagnostics | Preserve/replay coverage; run the bounded wrong/correct model comparison; retain failures and arrays | Derive and interpret tangent/likelihood diagnostics; distinguish numerical closure from misspecification |
| Performance/release | Same-backend timings, dependency locks, CI, docs, public export, release/DOI with author decisions | Define fair measurement, review claims and manuscript structure |
| Representation | Record source expressions, candidate plans, parameter dependencies, backend/input identity and evidence | Specify typed syntax/semantics, safe transformations, preservation theorem and trust boundary |
| Lean | Preserve toolchain; implement the concrete approved checker/proofs in a separate milestone | Supply theorem statements, induction structure, invariant requirements and review false proofs |
| Categorical/homotopical program | Maintain explicit construction/witness data before adding general machinery | Define physically meaningful categories, realization/extension hypotheses, coherence and remainder structures |

This division does not make theoretical choices the coding agent's improvisation. Missing equations or semantics are explicit obligations. Conversely, implementation evidence may reveal a necessary revision of a mathematical specification.

## Milestone R0 — external applicability

**Question:** can one declared comparison language prevent and explain a consequential misuse in a real public TMD workflow?

Deliver a pinned backend and published settings; native versus typed validation; independent observation integration; point/bin or another source-justified mismatch rejected before fitting; measured repair consequence; a fair overhead report; and a clean reader-facing release. Complete the coverage diagnostic and evidence brief. A small effect is not falsified by repeating seeds/bins. Any unresolved significance remains visible.

Exit: inspectable numerical evidence and reproducible code for the bounded external case. Publication status is separate from technical completion. R0 does not prove a general factorization theorem or a compiler-preservation theorem.

## Milestone R1 — explicit representation and dependency-preserving plans

**Question:** can the exact parameterized scientific construction survive translation into a reusable evaluation plan?

Define a small source language and a finite numerical-plan language, with explicit values, types, domains, input identities, fitted/nuisance parameters, and observation operators. Preserve source-to-plan links, primitive identities and ordered transformation traces. Use dependency-aware caching; do not mistake an external call with hidden parameter dependence for an immutable constant.

First concrete counterexample: cache a fitted-kernel evolution factor at g_star. It matches the correct expression at g_star for every kinematic probe but has the wrong g sensitivity. The checker must reject caching it as parameter independent, or explicitly identify fixing g as a model restriction. Valid parameter-independent factoring must be accepted.

Exit: a defined grammar, denotation, dependency rules, positive/negative transformation corpus and serialized source/plan format, plus ordinary runtime enforcement. Runtime enforcement is not yet Lean-verified soundness.

## Milestone R2 — concrete Lean-checked translation

**Question:** can we establish soundness of the actual checker used to accept a finite plan?

Formalize the supported syntax, denotation and translation certificates. Prove dependency soundness and preservation for a closed list of implemented transformations. The target has the form:

    check(Gamma,e,p,certificate)=accept
      implies for every admitted theta, denote(p,theta)=denote(e,theta).

The conclusion must be derived from local rules and their concrete checker, not assumed as a field. Arbitrary program equivalence need not be decidable; the checker may reject unsupported transformations. Specify the relationship among JSON decoding, Lean terms, checked plans and Python evaluation. Kernel-checked theorem, executed checker and float evaluator have distinct trust scopes.

Begin with exact semantics of finite plans over frozen numerical coefficients. Numerical quadrature/PDF approximation, Float64 nonassociativity, exp evaluation and QCD factorization remain separate obligations. Keep Lean 4.21.0 unless a justified, separately isolated toolchain change is approved. A mathlib pin must be compatible and explicit; do not silently upgrade the user's global installation.

Exit: successful build with an axiom/sorry audit, tests exercising actual Python-exported expressions and accepted plans, a numerical evaluator bound to the checked representation, and an honest correspondence/trust ledger. A theorem about a mock expression absent from the run is insufficient.

## Milestone R3 — categorical composition with practical scope

**Question:** do locally established compatibilities support larger assembled calculations without a new bespoke end-to-end proof each time?

Define contexts and admitted operations with their domains/codomains. Provide source-language and numerical-plan interpretations as the appropriate functors. Presentation comparisons satisfy naturality for supported generators, extending to their composites. Observation integration is an information-losing map, not generally invertible; products, linear sums and integration have distinct laws. Make those distinctions affect admissibility and compilation.

Retain the actual transformation/witness data even when normalizing an expression for evaluation. Do not quotient away derivation paths that later coherence questions require. Statistical likelihood comparison is a consequence of preserved responses with the full data/covariance context. Priors and restricted candidate families need additional transport.

Exit: concrete compositional results demonstrated on supported scientific operations, with a small category whose objects/maps have specified physical meaning. Yoneda provides characterization of already constructed representable profiles; finite response arrays are not automatically such profiles.

## Milestone R4 — numerical and approximation contracts

**Question:** what controlled statements survive approximate transformations and numerical realization?

Separate exact idealized-plan identities from floating-point implementation and quadrature error. Define certified or empirically assessed remainders with the applicable norms/domains. For compositions, use actual stability/Lipschitz or operator estimates to propagate errors. A raw 'within epsilon' relation is not transitive and cannot simply define categorical equality. Fixed-order quotient constructions require a genuine composition-stable ideal; logarithmic resummation requires an appropriate accuracy filtration, not a casual polynomial-order label.

Exit: explicit, useful error propagation to observable/likelihood scales with precisely identified analytic versus numerical evidence. Avoid implying an infinite-transform tail bound from finite endpoint sensitivity alone.

## Milestone R5 — multidimensional and AI-driven inference

Expand from fixed low-dimensional families to flexible reference functions, fitted kernels, fragmentation and coupled datasets. Represent candidate model families, nuisance parameters, constraints and priors as declared objects. Separate external-data information from model restrictions; test identifiable functionals and stability rather than proclaiming a whole function unique from finite data.

An AI proposer may suggest expressions, model changes, optimization plans or proof scripts. An independent checker enforces supported rules and reports unresolved obligations. Numerical and empirical validation remain independent. Preserve trial history to avoid accepting favorable seeds or hidden model selection. A passed checker establishes a scoped construction property, not truth of the empirical model.

## Milestone R6 — constructive process families and homotopical realization

Develop physically motivated axioms, regional/interface objects, admissible composition and extension principles indexed by process, observable, kinematics and perturbative prescription. Supply physical realization/comparison theorems connecting the abstract construction to QCD amplitudes or observables with controlled remainders. Test against known positive and factorization-obstructed cases; the desired physical conclusion must not be smuggled into an axiom and then advertised as derived.

Higher cells may represent chosen comparisons among derivations and their coherences when a concrete need appears. In Lean, represent such paths/witnesses as mathematical data if their differences matter; do not equate them with multiple proofs of Lean propositional equality. Constructible/stratified and interface-algebra ideas remain available, with existing mathematics reused wherever applicable. Formalizing broader homotopical machinery is a research objective, not a prerequisite to finish R0.

Exit: actual construction/extension or obstruction results for specified process families. AI proof search can help discover candidates; checked mathematical and analytic obligations establish the result. This stage preserves the ambition of new factorization derivation rather than limiting the program to bookkeeping.

## Paper-one decision gate

R0 improves external significance. R1/R2 can justify an expanded formal section only when their properties are established for executed plans. The author should decide whether that result belongs in the first CPC submission or a linked follow-on after reviewing the bounded effort and evidence; this roadmap does not silently abandon it or force an unbounded delay. Until then, make the achieved guarantees explicit and keep unsupported formal claims out of the abstract.
