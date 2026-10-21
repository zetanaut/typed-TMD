# Third-party inputs

Original typed-TMD software and separately obtained scientific inputs retain
their own authorship and terms. The public software export contains no native
binary, upstream source checkout, PDF grid or raw experimental CSV.

| Input | Pin/origin | Treatment |
|---|---|---|
| arTeMiDe, SV19 model and constants | official repository commit `ea0af1a75e21e316c1ac4ece51933988836a6650` | Upstream CC BY-NC-SA 4.0; fetch separately, never relicense as original project code |
| arTeMiDe DataProcessor geometry | official repository commit `18967d1c52dabf93e17a640405b548071904cfcc` | No explicit license located at that pin; fetch separately; export only selected factual geometry and calculated results |
| LHAPDF | official 6.5.5 source archive | Upstream GPL library; fetched and built separately; source digest and size recorded |
| NNPDF31_nnlo_as_0118_1000 member 0 | official CERN LHAPDF set server | Info and central grid fetched with exact digests; grids excluded from export |
| NumPy, SciPy and build tools | pinned environment requirements | Installed as dependencies under their upstream terms |
| Saved coverage inputs | original controlled synthetic calculation | Consumed-field projection preserves all 200 binary64 noise vectors and the original Jacobian/statistics; source identities recorded |

Scientific references:

- I. Scimemi and A. Vladimirov, [SV19 analysis](https://arxiv.org/abs/1912.06532).
- A. Buckley et al., [LHAPDF6](https://arxiv.org/abs/1412.7420).
- ATLAS, [8-TeV dilepton transverse-momentum measurement](https://arxiv.org/abs/1512.02192), the geometry source; no experimental measurements are fitted here.

The external calculation shares the published physics engine and model.
Adapter and observation checks are not additional authorship of that engine,
an independent QCD calculation, or a new reproduction of the global SV19 fit.
