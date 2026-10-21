# Release identity and evidence

Version **0.4.0** publishes the concrete finite-plan checker, category/Lean
implementation, reader examples, portable fixtures and reproducibility evidence.
Use the [GitHub release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.4.0)
for the immutable tag and source ZIP, file SHA-256 manifest and the separately
attached `typed-TMD-0.4.0.validation.json` publication receipt. That receipt records
the actual tag/commit, anonymous downloads, retrieved-source checks and remote
CI outcomes after publication. It avoids embedding a self-referential commit
hash or archive checksum in the source tree. A local build is not evidence that
remote publication or CI has occurred; consult that receipt and Actions.

The [source map](../SOURCE_MAP.json), [claim index](../CLAIM_EVIDENCE.json) and
[portable proof receipt](../evidence/formal/verification/PORTABLE.json) identify
the delivered implementation and its evidence. The formal component retains
its own 0.1.0 lake version and Lean 4.21.0 pin. Source-checkout reproduction is
supported; the wheel alone does not install the proof/fixture assets.

The prior [v0.3.0 release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.3.0)
and its tag/assets are unchanged. Its accepted external physics campaign,
fits, noise/covariance, refinements and timing arrays are historical evidence
preserved in this tree. The original publication receipt is retained at
[evidence/releases/v0.3.0.json](../evidence/releases/v0.3.0.json).
No new native campaign or fit is claimed for v0.4.0.

The existing release was archived on Zenodo on 2026-10-21. Cite version 0.4.0 with
[10.5281/zenodo.23546800](https://doi.org/10.5281/zenodo.23546800); the
[concept DOI](https://doi.org/10.5281/zenodo.23546799) identifies all versions.
The [archive verification receipt](../evidence/releases/zenodo-v0.4.0.json)
records anonymous downloads of all three assets, matching SHA-256 values and
successful resolution of both DOIs. The archived commit is
`a5142e7a342aa6b8fb109ca1d0c65d90130da9a7`.

The tag, source ZIP, manifest and original validation receipt remain unchanged.
Their DOI-deferred statements record the earlier publication-time decision;
this later archival receipt supersedes that status. Citation updates on `main`
do not change the archived software or its scientific/proof evidence.

Original code remains MIT, with software authorship recorded in CITATION.cff.
No manuscript or research-note revision accompanies this archival follow-up.
