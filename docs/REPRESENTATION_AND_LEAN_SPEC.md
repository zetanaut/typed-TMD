# A small representation-preservation specification

**Status:** mathematical design and elementary derivations for the next formal milestone. No new Lean implementation or kernel-checked proof is claimed for the external adapter. Its representation hooks are runtime records. Background references are [CompCert's semantic-preservation methodology](https://compcert.org/man/manual001.html) and [Lean's distinction between elaboration, kernel checking and compilation](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/). These references do not establish correctness of this implementation.

## 1. Scientific object versus numerical realization

Fix a context Gamma containing operator/presentation declarations, kinematic domain, units/measures, parameter domain Theta, primitive identities, and external-input identities. A source expression denotes a function of theta (and of specified kinematic inputs). A numerical plan contains finite sums, values and operations chosen to approximate or realize that expression. The architecture must distinguish:

1. analytical scientific expressions and identities;
2. the discretization/input-approximation step and its error claims;
3. exact algebraic transformations of the chosen finite plan;
4. serialization, concrete evaluation and floating-point errors;
5. fit/inference consequences and empirical evidence.

The first formal target concerns level 3 and the source finite representation from which it is compiled. It does not prove level 2, QCD factorization or IEEE execution. A value from LHAPDF can be an immutable input to this theorem while its interpolation and scientific appropriateness remain separately assessed.

## 2. A bounded typed source language

Start with scalar/vector expressions built from exact constants, symbolic parameters, named immutable inputs, addition, multiplication, pure elementary-function application, and finite indexed sums. The admitted indices and vector sizes are explicit. High-level nodes for Transport, Boundary, FlavorProduct and Observation elaborate into this finite language only through audited, separately identified rules. Do not grant a high-level node a theorem merely by attaching its name.

For a numerical coefficient obtained in binary64, record its exact bit pattern and interpret it in the idealized-plan theorem as the corresponding dyadic real. Evaluating exp on that real and a native floating-point exp are distinct interpretations. An initial proof may treat a pure unary function symbol uniformly without using exp algebra; transformations that split exponentials require the actual law exp(x+y)=exp(x)exp(y) in the real semantics.

Primitive external calls are never assumed parameter independent by default. A backend call that closes over a current NP vector is `NativeCall(id,args,parameter_environment)`, not `Input(id)` merely because it returns a float. Lowering it to frozen input values either quantifies over a fixed parameter environment or is an explicit model restriction. A mutable global backend makes this distinction particularly important.

A term judgement has the form Gamma |- e : T. T carries necessary value shape and observation meaning. A runtime declaration that a term is well typed checks admissible assembly; it does not establish the asserted operator factorization or honesty of an external adapter. The adapter claim is supported by source inspection and numerical comparison with the pinned native interface.

## 3. Dependency soundness

Define a conservative finite set Dep(e) of parameter identifiers:

- constants and genuinely immutable inputs: empty;
- parameter k: {k};
- addition/multiplication: union of child dependencies;
- pure function application: dependency of its argument(s);
- finite sum: union over summands, with any parameter-dependent bounds also included or disallowed in the first language;
- primitive calls: dependencies of all explicit parameter arguments plus a registry-specified closure dependency set validated at binding.

This analysis is conservative: cancellation such as g-g need not remove g. It must never falsely remove a real dependency. A caller-supplied empty set for an opaque function is not evidence of independence.

**Lemma (environment agreement).** For terms in the supported language and a fixed admissible immutable-input environment iota, if theta and theta' agree on Dep(e), then

    denote(e,theta,iota) = denote(e,theta',iota).

**Proof structure.** Induct on e. Parameter leaves use the agreement hypothesis; immutable leaves are fixed. The union rule restricts environment agreement to each child, so induction gives equal child values. Applying the same pure operation to equal children preserves equality. The finite-sum case follows pointwise and then by finite summation. Opaque primitives require the registered dependency semantics as an explicit primitive obligation; without it the lemma does not apply to them.

**Safe cache corollary.** Let P be the parameters allowed to vary within a fit. If Dep(e) is disjoint from P and all remaining environment/input values are fixed and identified, evaluating e once and reusing that value preserves the idealized plan throughout the fit. The cache identity must also include the fixed parameter values, primitive definitions, provider/input hashes, domain, numerical plan and any mutable-state token relevant to the primitive. Independence from fitted parameters alone does not justify reuse after a provider or precision change.

The Lean proof target is this theorem for the concrete grammar and concrete dependency function, not a predicate whose 'soundness' is assumed by the caller.

## 4. Counterexample: fitted evolution cached at a reference parameter

Let g be a fitted Collins–Soper parameter and let a denote the other fitted inputs. For a fixed b and scales QA,Q, a supported model has

    U(b;g) = exp(R(b) - g b² log(Q/QA)).

Consider F_good = U(b;g) F_A(b;a,g) and F_bad = U(b;g_star) F_A(b;a,g). They agree at g=g_star for all b and other kinematics in the chosen domain. Their derivative difference there is

    partial_g F_good - partial_g F_bad
      = -b² log(Q/QA) F_good(g_star).

**Derivation.** Product differentiation gives a common U times partial_g F_A, which cancels. The missing derivative of U is the displayed term. At Q=QA the term vanishes; a useful regression must include unequal scales and nonzero b. Zero amplitudes must not be the only probes.

Thus a forward-value closure suite at g_star can pass while the optimizer is given the wrong sensitivity. A designed derivative/off-truth unit test can catch this; no superiority to all possible unit testing is claimed. The reusable guarantee is that an accepted cache transformation preserves the function for every admitted theta, not only the chosen probes. Dep(U) contains g, so caching U as parameter independent is refused. Fixing g legitimately constructs a different model, which can be admitted under an explicit restriction rather than certified equivalent.

H004 already kept this dependency explicit. The example is a fault-injection target for the future checker, not a discovered H004 bug.

## 5. Translation checking rather than trusting a generator

Let compile propose a plan p and a certificate c for a finite source expression e. The proposer can be Python, another compiler, or an AI agent. A small checker validates each step from a closed list of transformations: substituting fixed independent constants; factoring declared parameter-independent subexpressions; reindexing a finite sum bijectively; composing supported transports; and exact chart substitutions with their domains. Add rules one at a time with soundness proofs.

The target theorem is:

    check(Gamma,e,p,c)=accept
    => forall theta in Theta_Gamma,
         denote_plan(p,theta,iota)=denote_source(e,theta,iota).

Here check is actual executable code over actual syntax/certificates. It must not receive the desired equality as a postulated field or call an untrusted equality oracle. It may reject unsupported but mathematically valid expressions; completeness is unnecessary. Malformed or ill-typed inputs produce explicit errors.

**Composition argument.** Each accepted local rewrite has a theorem preserving the denotation under its verified side conditions. Induction on the certificate trace composes equalities, yielding the whole-plan result. The dependency lemma justifies constant factoring. A parameter chart must map the entire admitted domain and transport all dependent terms; a renamed parameter does not suffice.

Do not use distributivity/associativity over actual IEEE floats as exact identities. The theorem is over the specified idealized semantics. Floating-point roundoff introduced by regrouping needs a separate bound or measured numerical comparison. A checker of exact finite algebra is useful even with that explicit limitation.

## 6. Category-theoretic formulation with operational content

Objects are interfaces for declared parameterized constructions and observations; arrows are admitted operations with the appropriate source/target. The source expression category can be built from generators subject to proved equations. Interpretation sends expressions to their mathematical maps; a plan interpretation sends accepted plans to maps in the same target category. Compatibility of compilation is preservation of denotation on supported arrows, not merely agreement of plotted points.

For two presentation interpretations I_A,I_B and chosen comparison maps Z_X, a primitive f:X->Y satisfies

    Z_Y o I_A(f) = I_B(f) o Z_X.

Given identity/composition laws, this naturality condition propagates to composites: substitute the identities for f and g in Z_Z o I_A(g) o I_A(f), then reassociate to I_B(g) o I_B(f) o Z_X. No new physics follows unless the primitive interpretations and their compatibility were actually established.

Boundary-coordinate changes can be isomorphisms; bin integration generally is not. Integrating a linear combination is allowed under its stated conditions; turning an integral of a product into a product of integrals generally is not. These distinctions must affect the syntax/rules. A family of contexts requires explicit reindexing maps or partial admissible transitions; it is not created just by listing metadata.

The existing affine response diagram remains a regression. The stronger contribution would be local-to-global preservation of a supported family of constructions, including safe extraction of reusable coefficients and parameter dependencies.

Yoneda motivates characterization through complete compatible map profiles. A finite observed vector is not such a profile, and neither this checker nor an optimizer supplies a general identifiability theorem. Keep naturality, semantic preservation and observation/inference claims distinct.

## 7. Decoder, execution and trust boundary

Use a versioned, canonical exchange representation with explicit node tags, parameter/input IDs, types, numeric encodings and topological order. Reject cycles, duplicate IDs, unbound variables, unsupported operations, unknown units, nonfinite inputs when not allowed, and mismatched vector sizes. A serialization hash identifies bytes; it does not prove that both decoders assign them the same syntax or meaning.

A future implementation must:

1. relate the parsed exchange format to the Lean terms accepted by the checker;
2. ensure the Python evaluator consumes exactly the accepted plan, not a reconstructed substitute;
3. bind source, plan, certificate, input identities and checker version in the receipt;
4. document primitive semantic assumptions and evaluator/FFI trust;
5. distinguish kernel-checked statements from the behavior of a compiled checker executable.

Positive/negative cross-language fixtures are useful interface evidence, not a decoder proof. A compiled checker is a program produced by Lean's compiler, while proof terms are checked by its kernel [S6]. A runtime Bool alone is not a certificate of a kernel-checked equality. The selected architecture should either produce appropriately checked evidence or make the remaining trusted components explicit.

## 8. Numerical error and inference consequences

Suppose an exact model response is mu and a numerical plan has response error delta_mu. With fixed positive-definite covariance Sigma, let r=Sigma^(-1/2)(mu-y) and e=Sigma^(-1/2)delta_mu. Then

    | ||r+e||² - ||r||² | <= 2||r||||e|| + ||e||².

**Proof.** Expand the square and apply Cauchy–Schwarz. It translates a response-error estimate into an objective-error estimate. An observed refinement difference is not automatically a rigorous bound on e; label the source of the estimate.

If g is L-Lipschitz on the relevant image, then replacing f by f_tilde and g by g_tilde yields a composition error bounded by L||f-f_tilde|| plus the appropriate g-versus-g_tilde error. Actual domains/norms and a stability hypothesis are required. Numerical agreement within epsilon is not generally transitive; do not call it categorical equality or a homotopy without further construction.

For an admitted exact parameter bijection Psi preserving the response, the common data/covariance imply chi_A² = chi_B² o Psi and transport of minimizer sets. This is standard mathematical content supporting the software contract. Bayesian priors require pushforward of the measure, including the Jacobian for densities; the determinant-one affine H004 map is not a demonstration of a nonconstant missing Jacobian.

## 9. Preserving the larger research possibility

Store original expressions, all selected transformation maps, primitive obligations, chosen witnesses and derivation paths separately from optimized normal forms. Later higher-categorical questions may concern comparisons among these derivations and coherence of those comparisons. Distinct witnesses need to be data rather than distinctions between Lean equality proofs if they are to carry mathematical information.

Axiomatic/homotopical factorization discovery must supply physical realization theorems, analytic hypotheses, remainder control and admissible extensions. The first checker is a stepping stone because it separates a proposer from a verifier and retains the derivation. It is not itself a factorization derivation or a theorem that every process factorizes.
