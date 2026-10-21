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

Original code remains MIT, with software authorship recorded in CITATION.cff.
DOI archiving is explicitly deferred. No software DOI, manuscript change or
research-note revision is part of this release.
