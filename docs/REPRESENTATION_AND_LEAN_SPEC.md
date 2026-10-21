# Concrete representation and Lean status

The finite representation and dependency-preserving checker are implemented.
The current authoritative pages are [representation](formal/REPRESENTATION.md),
[category](formal/CATEGORY.md), [Lean evidence](formal/LEAN.md), and
[trust/scope](formal/TRUST_AND_SCOPE.md). The earlier abstract seed in `lean/`
remains historical; it is not the implementation of this guarantee.

Version 0.4.0 supports variable/atom/unary/binary terms, source-preserving
cache plans, conservative dependencies, fixed-coordinate/context guards,
source substitution and transported-reference staged evaluation. The exact
checker has no semantic-equality oracle. Formal source and scientific
conventions remain separate, with decoder/IEEE/quadrature/QCD obligations
explicit. The [roadmap](ROADMAP.md) identifies the wider unfinished program.
