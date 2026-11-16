# Release identity and evidence

Version **0.4.1** is a documentation and metadata update to v0.4.0.
Use the [GitHub release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.4.1)
for the tagged source ZIP, file SHA-256 manifest and separately attached
`typed-TMD-0.4.1.validation.json` publication receipt. The receipt records the
actual tag/commit, anonymous downloads, retrieved-source checks and remote CI
outcomes after publication. It avoids embedding a self-referential commit hash
or archive checksum in the source tree. Consult the receipt and Actions for
executed publication checks.

The [concept DOI](https://doi.org/10.5281/zenodo.23546799) identifies the software
across archived versions and is included in this release's citation metadata.
The Zenodo version record and GitHub release notes provide the version-specific
DOI after publication. Cite that version DOI when identifying the exact software
used in the paper.

The [source map](../SOURCE_MAP.json), [claim index](../CLAIM_EVIDENCE.json) and
[portable proof receipt](../evidence/formal/verification/PORTABLE.json) identify
the delivered implementation and its historical evidence. The formal component
retains its own 0.1.0 lake version and Lean 4.21.0 pin. Source-checkout reproduction
is supported; the wheel alone does not install the proof/fixture assets.

The code, tests, formal sources and evidence shipped in v0.4.0 are unchanged
except for the Python package version string. Package metadata, current release
documentation and the source map are updated; sample tutorial and analytic
closure JSON outputs are added outside the historical evidence directories.
See [release notes](RELEASE_NOTES_0.4.1.md). No new native campaign or fit is claimed.

The prior [v0.4.0 release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.4.0)
was archived on 2026-10-21 at [Zenodo](https://zenodo.org/records/23546800).
Its tag, three assets and original validation receipt are unchanged. The
[archive verification receipt](../evidence/releases/zenodo-v0.4.0.json) remains
unchanged and describes that earlier archive. DOI-deferred statements in the
historical v0.4.0 release notes describe the publication-time decision.

The [v0.3.0 release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.3.0),
its tag/assets and accepted external physics campaign are also preserved.
Its original publication receipt remains at
[evidence/releases/v0.3.0.json](../evidence/releases/v0.3.0.json).

Original code remains MIT, with authorship recorded in CITATION.cff.
No manuscript or research-note revision accompanies this release.
