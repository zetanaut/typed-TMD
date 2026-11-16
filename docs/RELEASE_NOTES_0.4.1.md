# Version 0.4.1

This is a documentation and metadata release. It replaces stale DOI-deferred
statements with the existing [concept DOI](https://doi.org/10.5281/zenodo.23546799),
updates the software version and citation metadata, and clarifies the program
summary and package descriptions to include the finite-plan checker and Lean
proofs of exact finite semantics.

The code, tests, formal sources and evidence shipped in v0.4.0 are byte-identical
apart from the package version string in `src/typed_tmd/__init__.py`. Build
metadata in `pyproject.toml` also has the new version and scope description.
The v0.4.0 Zenodo archival receipt subsequently added on `main` is retained
unchanged. The formal component remains version 0.1.0 on Lean 4.21.0.
Historical release notes and statements about when features were introduced
are preserved. Existing Git tags, release assets and Zenodo v0.4.0 are preserved.

The program summary follows the field order used in the companion paper and
distinguishes macOS/arm64 native measurements from Ubuntu 24.04 runtime and
formal CI. `sample_output/` supplies JSON output from the unchanged tutorial
and analytic Gaussian closure example, with reproduction commands. These are
software examples, not new physical results or an experimental extraction.

The source map and external SHA-256 manifest are regenerated. The separate
`typed-TMD-0.4.1.validation.json` asset records this release's actual local and
remote checks, preservation audit and anonymous download verification.
The [GitHub release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.4.1)
and the concept DOI provide publication and version-specific citation links.
The source archive uses the stable concept DOI; the new version DOI is recorded
in the published Zenodo record and GitHub release notes.

No new physics campaign, fit, theorem development or manuscript edit is included.
Exact finite-semantic proofs retain their fixed-interpretation and variation
assumptions; they do not verify Python/JSON, floating-point arithmetic,
quadrature or QCD.

Original software is MIT-licensed; upstream software and inputs retain their
separate terms and attributions.
