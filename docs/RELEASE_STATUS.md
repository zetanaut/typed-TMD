# Release and accepted-results status

**v0.3.0 is published and the bounded results are accepted.** The software is
available at [zetanaut/typed-TMD](https://github.com/zetanaut/typed-TMD) and the
[v0.3.0 release](https://github.com/zetanaut/typed-TMD/releases/tag/v0.3.0). The release was published on 2026-10-21 at
01:32:54 UTC; its annotated tag resolves to commit
`fcf6d80a01dbb474af62f0929624a8dd92e6d698`.

The author accepted the completed results on 2026-10-21 UTC. This acceptance
covers the experiment and limitations reported in [RESULTS.md](RESULTS.md)
and [CLAIM_EVIDENCE.md](CLAIM_EVIDENCE.md). The subsequent documentation update
records that outcome. It does not extend the numerical or formal claims.

## Release identity and verification

All three assets were anonymously downloaded again on 2026-10-21 and matched
their recorded byte counts and SHA-256 hashes:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| [typed-TMD-0.3.0.manifest.json](https://github.com/zetanaut/typed-TMD/releases/download/v0.3.0/typed-TMD-0.3.0.manifest.json) | 18,376 | `ea363d30c233a0b41ac719bc86b7bdb12d44684f1d0fcab5b5e0903dbbc268dd` |
| [typed-TMD-0.3.0.validation.json](https://github.com/zetanaut/typed-TMD/releases/download/v0.3.0/typed-TMD-0.3.0.validation.json) | 5,495 | `403e86070f316bf36e239ed29365f81a479ad0248f7397a3f66200afe5636028` |
| [typed-TMD-0.3.0.zip](https://github.com/zetanaut/typed-TMD/releases/download/v0.3.0/typed-TMD-0.3.0.zip) | 430,579 | `cc5770572e50d165d46e80e839c2d0b06d6899eb241e03cbb2d5069dd600da64` |

The release archive and the tag identify the validated scientific snapshot.
`main` also contains later documentation and publication-status updates. Those
updates preserve the release tag/assets, scientific code, inputs and numerical
evidence. [RELEASE_STATUS.json](https://github.com/zetanaut/typed-TMD/blob/main/RELEASE_STATUS.json) records the publication
check and its timestamp; [SOURCE_MAP.json](https://github.com/zetanaut/typed-TMD/blob/main/SOURCE_MAP.json) maps the current
publication tree to working source identities.

## Validation completed

The exact release export was installed in an independently built native
environment. All 66 public tests, twelve analytic closure checks and saved-array
coverage replay passed. The complete four-fit native campaign reproduced all
scientific values, including optimizer histories, exactly in binary64 except
elapsed times. The downloaded tag-source archive was also installed and its
core/closure/coverage commands passed. The [validation asset](https://github.com/zetanaut/typed-TMD/releases/download/v0.3.0/typed-TMD-0.3.0.validation.json)
contains the scoped release receipt.

[GitHub core CI](https://github.com/zetanaut/typed-TMD/actions/workflows/core.yml)
passed for the release and the subsequent README update. It executes Python
core and analytic fixtures plus the saved coverage replay on Ubuntu; it does
not build the optional native engine. Native reproduction was performed
separately on macOS arm64. The Lean 4.21.0 abstract seed build passed; no
concrete dependency/translation checker or Python/native/QCD proof is claimed.

The README and release notes follow the requested project-first section
layout, with citation metadata and licensing at the end. DOI archiving is
explicitly deferred and no software DOI has been assigned. Main manuscript
and submission work remain separate future tasks.

## License

The original software uses [MIT](../LICENSE). Author metadata remains in
[CITATION.cff](../CITATION.cff); upstream terms are recorded in
[third-party notices](THIRD_PARTY_NOTICES.md).
