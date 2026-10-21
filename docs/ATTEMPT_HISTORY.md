# Relevant corrections and retained failures

The frozen experiment keeps its selected bins, one free parameter, covariance,
noise seed, five starts, bounds and tolerances unchanged after impact inspection.
The private experiment freeze was committed before any midpoint impact or fit
was evaluated. The public source map records the original freeze digest and
the exact scientific-file identities; only evidence-location strings change
in the public freeze envelope.

Before that freeze, a native integration minimum of 16 qT sections failed the
component comparison: maximum relative discrepancy 1.174e-4 against a 1e-4
target, although the whitened norm passed. Increasing the minimum to 32 and
tightening Q/y precision yielded agreement with independent quadrature.
The 16-to-32 comparison itself remains a failed historical check; the final
32-to-64 refinement passes the unchanged budgets. The initial failed arrays
are retained under `evidence/pilots/initial_failed/`.

The pinned upstream Python wrapper's optional `Num` branch has an argument
mismatch. The working default native API and explicit constants-file minima
were used without patching the upstream physics code. This portability issue
is separate from the deliberately injected midpoint/bin mismatch.

The first native extension import lacked the LHAPDF runtime search path.
Explicit linking repaired it. LHAPDF was then built from its verified source
archive in a project prefix, and built independently again for the clean
installation. The published workflow requires no developer base library.

After the freeze, a shared process lock replaced per-session locks so two
adapter owners cannot race the native global state. A regression test checks
serialization. Validation scheduling was split into independent native
processes without changing numerical inputs. Symmetric native call counters
were added to both timing routes; their equality is checked outside timing.
These engineering corrections and their source hashes are recorded. The
complete independently built campaign reproduced the original numerical
results exactly, including optimizer histories.

The first public candidate omitted the quick-start benchmark configuration.
Its tests passed but its closure command failed. The export now includes that
fixture; the subsequent clean install passes both commands and the full
external four-fit campaign. A passing unit suite alone was not treated as
fresh-install acceptance. Full operational logs remain in the private return;
this public account retains the scientifically and operationally relevant
failures without machine-local paths.

## Concrete finite-plan publication

The full accepted finite-window certificate originally exceeded Lean's default
thread stack. The mechanical repair uses `--tstack=65536`; theorem sources,
coefficients and root coverage were unchanged. Both failed and successful
attempts remain in the private provenance record.

The first publication wrapper inventory mishandled a dotted Lean namespace
and requested five nonexistent short theorem names. The library and selected
root checks had passed; the wrapper correctly returned failure for the missing
inventory. Namespace parsing was repaired and a regression added. The final
inventory prints all 24 actual declarations and their axioms. This packaging
repair changes no accepted theorem or finite-plan implementation.
