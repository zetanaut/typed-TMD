# Program summary

The fields below follow the order used in the companion CPC paper.

| Field | Factual entry |
|---|---|
| Program title | typed-TMD |
| Version | 0.4.1; [GitHub release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.4.1) |
| Persistent identifier | [Concept DOI: 10.5281/zenodo.23546799](https://doi.org/10.5281/zenodo.23546799); use the version record's DOI when citing an exact release |
| Repository | https://github.com/zetanaut/typed-TMD |
| Licensing provisions | MIT for original code; separately obtained upstream software and inputs retain their own terms |
| Programming languages | Python and Lean 4.21.0; the optional external backend uses Fortran, f2py and LHAPDF C++ |
| Requirements | Python 3.11, NumPy and SciPy for numerical replay (recorded local versions: NumPy 1.26.4, SciPy 1.14.1). Formal replay additionally requires pinned Lean 4.21.0/Std, without mathlib. Native Drell-Yan reproduction requires separately pinned arTeMiDe, LHAPDF and PDF inputs; recorded native toolchain: GNU Fortran 16.2.0 and LHAPDF 6.5.5 |
| Tested platforms | macOS 26.6.2/arm64 for recorded local runtime, formal and native checks; Linux/Ubuntu 24.04 for the separate runtime and mandatory Lean CI workflows. The Linux CI does not run the native backend |
| Nature of problem | Interface-compatible numerical arrays may represent different observations; caching a fitted dependency can change the function being optimized while preserving reference-point values |
| Solution method | Immutable scientific contexts, checked observation operators, explicit finite expressions and variation masks, a Lean-proved cache validator, and compositional reference transport |
| Restrictions | One audited external process/interface and a finite-expression caching language. The external study uses seven absolute-spectrum bins from published ATLAS 8-TeV geometry, pinned SV19 settings, one free c0 parameter and two held-out bins. Its inputs are controlled synthetic native means and a fixed PCG64 realization, not an experimental extraction. Numerical accuracy, native primitive semantics and physical factorization remain separately assessed; no large-qT matching, generic operator maps or full compiler proof is claimed |
| Representative running time | About 217 seconds for four five-start, one-parameter external fits in the recorded Mac run, excluding native startup and mean generation. Native bin validation and one-time formal checking are separate workloads. Peak memory was not measured |

Validation comprises same-call comparisons, separately refined observation
quadrature sharing the native kernel, bounded synthetic fits, retained coverage
replay, 24 Lean statements, selected full-root certificates and runtime replay.
The [release status](RELEASE_STATUS.md) distinguishes historical evidence from
the current release's verification receipt.

The [sample output](../sample_output/README.md) provides JSON from the runtime
tutorial and analytic Gaussian closure example, with commands to reproduce it.
Software authorship is recorded in CITATION.cff; project contact is the
[issue tracker](https://github.com/zetanaut/typed-TMD/issues).
