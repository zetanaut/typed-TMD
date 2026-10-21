# Exact finite plans and checked caching

A fit evaluates a family of responses. Reusing a value is safe only when its
source expression is independent of every coordinate that the fit may vary.
A cache that happens to agree at one reference point can change that family.
The [runtime tutorial](../../examples/formal/cache_and_composition.py) shows
this failure and the corresponding refusal before any primitive is called.

```text
scientific definitions, input provider, discretization
        | audited lowering and separate numerical comparisons
        v
finite source expression + explicit parameter interface
        | untrusted cache proposal
        v
candidate plan -- erasure/dependency checker --> accepted literal certificate
        |                                           |
        |               fixed pure interpretation  | Lean preservation theorem
        +------------------- same sealed plan ------+
                                |
                                v
                    numerical evaluation and tests
```

For a fixed pure interpretation `Model`, the checker computes both source
erasure and dependencies. If it accepts and the environment agrees with the
reference on all fixed coordinates, the exact plan and source interpretations
are equal for **every** admitted environment. This is
[`TypedTMDPlan.check_sound`](../../formal/007/TypedTMDPlan/Core.lean), not an
assumed semantic-equality field or an inference from numerical probes.

Start with the [examples](EXAMPLES.md), then [representation](REPRESENTATION.md)
and [category](CATEGORY.md). [Reproduce](REPRODUCE.md) gives commands for a clean
source checkout. [Lean](LEAN.md) explains actual theorem and literal evidence;
[trust and scope](TRUST_AND_SCOPE.md) separates mathematical, software and physics
obligations. The [machine claim index](../../CLAIM_EVIDENCE.json) links claims
to exact sources and artifact hashes.

The delivered language is finite and single-sorted, with parameter-indexed
variables, immutable atoms, unary and binary operations. Units, process,
measure and perturbative inventories are carried by surrounding scientific
contracts; they are not all encoded as Lean value types. The theorem does not
verify QCD, quadrature, Python, the wire decoder or IEEE arithmetic.
