# Program summary

| Field | Factual entry |
|---|---|
| Program title | typed-TMD |
| Software version | 0.3.0 |
| Author | Dustin Keller |
| Project contact | https://github.com/zetanaut/typed-TMD/issues |
| Original-code license | MIT; upstream terms are separate |
| Persistent identifier | No software DOI assigned |
| Languages/interfaces | Python 3.11 package and command-line scripts; optional arTeMiDe Fortran via f2py and native LHAPDF C++; existing Lean seed |
| Operating system tested in this execution | macOS 26.6.2, arm64 |
| Numerical dependencies | NumPy 1.26.4, SciPy 1.14.1; native backend/model/PDF locks included |
| Native toolchain tested | GNU Fortran 16.2.0; serial optimized build; LHAPDF 6.5.5 built in an isolated prefix |
| Nature of problem | Scientific responses with matching dimensions/units can represent different observations; mutable parameter state can invalidate reuse |
| Solution | Explicit immutable observation contexts and parameter-dependent response plans, checked at composition boundaries, with native and independent-integration evidence |
| Supported external case | Seven absolute-spectrum bins from published ATLAS 8-TeV geometry; pinned SV19 settings; one free c0 parameter; two held-out bins |
| Data in inference experiment | Controlled synthetic native means and one fixed PCG64 realization; no experimental extraction |
| Validation | Exact same-call comparison; separately refined observation quadrature sharing the native kernel; bounded synthetic fits; retained coverage replay; existing Lean seed only |
| Restrictions | One audited backend/process/measure bridge, explicit local parameter domain, exclusive process ownership; no large-qT matching, generic operator maps, full compiler proof or independent QCD engine |
| Representative runtime | Four five-start fits took about 217 seconds in total, excluding native startup and generation of means; native bin validation adds substantial work; timing report separates workloads |
| Memory | Peak memory not measured; no per-call memory saving is claimed |

The planned publication route is a CPC methods paper. The live journal guide
could not be retrieved in this session (HTTP 403), so this factual summary is
not claimed to be a verified current submission template. Check the
[official guide](https://www.sciencedirect.com/journal/computer-physics-communications/publish/guide-for-authors)
at submission.
