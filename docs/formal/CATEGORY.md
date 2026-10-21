# Interfaces, substitution and cache-reference transport

[`Category.lean`](../../formal/007/TypedTMDPlan/Category.lean) defines a concrete
category without mathlib. `Interface` has a finite coordinate count and a
Boolean variation mask. `Category.Arrow X Y` contains one source expression
per target coordinate and a proof that each target-fixed coordinate depends
only on source-fixed coordinates. The Python counterpart of this side
condition is `respects_variation` in
[`finite_plan.py`](../../src/typed_tmd/finite_plan.py).

Identity is the tuple of source variables. Composition `Arrow.comp g f` is
actual substitution, g after f. `Arrow.id_comp`, `Arrow.comp_id` and
`Arrow.comp_assoc` establish the laws using the concrete syntax.
`Expr.subst_vars`, `Expr.subst_comp` and `Expr.eval_subst` support these results.
For a fixed pure `Model M`, `Arrow.interpret` maps arrows to functions on finite
environments; `Arrow.interpret_id` and `Arrow.interpret_comp` give its functor
laws. `Expr.interpretation_unique` says that recursive evaluation is the unique
homomorphic extension of the variable and primitive interpretations.

The interpretation is held fixed throughout. Changing a provider, primitive
binding or hidden native state is not automatically a morphism in this category.
There is no implemented general category composition operation on plan syntax;
the staged-plan theorem uses separately checked plans for the two source arrows.

For f then g, the second cache must use the transported reference:

\[
\eta_0=\llbracket f\rrbracket_M(\theta_0),\qquad
\operatorname{eval}(p_g,\eta_0,\operatorname{eval}(p_f,\theta_0,\theta))
=\llbracket g\circ f\rrbracket_M(\theta).
\]

`Arrow.fixed_slice_preserved` proves that f sends the admitted source slice to
the correct target slice. `Arrow.checked_composition` then proves the displayed
identity from the two actual checker acceptances. An unrelated second reference
is not covered by that theorem.

The [runnable example](../../examples/formal/cache_and_composition.py) uses
f(x,y)=(x+2,y²), g(u,v)=uv, with x varying and y fixed. At reference (0.2,0.3),
the second reference is (2.2,0.09). At (0.4,0.3), both composed routes give
0.216. Initializing the second stage at (0.2,0.3) instead causes
`fixed_parameter_changed` before evaluation. Fixing the reference means
transporting the actual model boundary, not reusing the same parameter names.

This establishes a category of supported finite expressions and interfaces.
It is not a full category of physical TMDs. Yoneda and representability remain
background research motivations; no new Yoneda theorem, physical reconstruction
or identifiability theorem follows from the finite response arrays.
