# Source, wire and cached plan

The implementation is [`finite_plan.py`](../../src/typed_tmd/finite_plan.py).
`Expr` has variable, atom, unary and binary constructors. `Plan` has live and
cache leaves retaining exact source subtrees, and unary/binary constructors.
A finite sum is an explicitly ordered tree. The wire contains topologically
ordered expression/plan nodes, roots, canonical hexadecimal binary64 atoms,
parameter names, variation mask, reference, operation-symbol registries and
scientific context. `encode`, `decode`, `canonical` and `digest` identify that
representation; decoding rejects unknown fields, cycles/forward references,
invalid arities, nonfinite numbers and noncanonical atom encodings.

`dependencies` and `cacheable` conservatively follow syntax. Algebraic
cancellation does not remove a dependency. `erase` must recover the exact
source; `safe` forbids caching a subtree using a varying coordinate. `check`
combines both obligations. `propose` is an untrusted convenience: acceptance
does not depend on the proposer. Unsupported rearrangements can be rejected
even when some external mathematics would prove them equivalent.

No floating-point reassociation, exp identity, changed quadrature, arbitrary
numeric cache table or continuum transformation is authorized by this checker.
The finite source tree is the object preserved. The separate numerical bridge
compares its balanced sum to the original NumPy reduction under explicit
budgets; that comparison is not an exact-arithmetic theorem about reductions.

`PreparedPlan` checks source/plan and binding scope before cache initialization,
retains a reference environment, and rejects changes of fixed coordinates or
context identity. `prepare_wire` labels its receipt `runtime_checked_only`.
`prepare_certified` seals a canonical snapshot, invokes fresh Lean checking,
then binds and executes the same decoded source and plans. Missing Lean fails;
there is no successful fallback from a proof request to runtime-only evidence.
Function purity remains an obligation: names and hashes do not prove that an
arbitrary Python callback or mutable external process implements the intended
fixed primitive.

The [fixture manifest](../../evidence/formal/fixtures/MANIFEST.json) records
compressed-file hashes, canonical full-wire digests, parent archive/payloads,
root lists, bindings and numerical targets. The [proof receipt](../../evidence/formal/verification/PORTABLE.json)
adds selected-output digests, certificate hashes and exact theorem-source
hashes. These are different identities. Selecting output 0 preserves the full
subtree and records its parent wire; it is not a small proxy example.
