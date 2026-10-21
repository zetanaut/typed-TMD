# Lean build and proof evidence

The active project is [`formal/007`](../../formal/007), pinned to Lean **4.21.0**,
Std only, without mathlib. Its lake component version **0.1.0** is distinct from
the software release **0.4.0**. The four theorem source files and three build
files are preserved byte for byte from the accepted formal implementation.
The older [`lean/`](../../lean) project is a historical abstract seed; it does
not supply the concrete checker guarantee below.

From the source checkout, with pinned `lake` on PATH:

```sh
.venv/bin/python scripts/check_formal.py --output-dir results/formal-check
```

Use a new output directory per run. This command calls the accepted build and
certificate runner, runs `lake clean` and `lake build` only in `formal/007`,
prints the actual statements and axioms of all 24 library theorems, and checks
four positive literal roots plus the frozen-kernel negative root. It then
checks the 512-term dense certificate regression without allowing a skip,
evaluates the same sealed positive plans at reference/off-reference points,
and replays the full numerical snapshot targets. A missing dependency or proof
failure returns nonzero and retains a failure receipt.

The theorem inventory consists of 11 core, 8 category and 5 example declarations.
See the [actual statement/axiom output](../../evidence/formal/verification/theorem_inventory.log),
[generated audit source](../../evidence/formal/verification/TheoremInventory.lean),
and [machine inventory](../../evidence/formal/verification/PORTABLE.json).
`Expr.dependency_sound`, `cacheable_sound`, `Plan.safe_sound` and `check_sound`
establish the concrete dependency/cache result. `Arrow.checked_composition`
requires the transported second reference. The exact hypotheses are printed,
not replaced by prose descriptions.

The reported logical dependencies are **propext and Quot.sound**, not
axiom-free proofs. No `sorryAx`, native reduction oracle, added axiom,
`implemented_by` or skipped kernel checking is accepted. Positive certificates
use ordinary `by decide` acceptance followed by `check_sound`. The negative
certificate kernel-reduces the concrete checker to false, and its own axiom
report is retained.

The default thread stack failed on a full finite-window certificate during
implementation. The retained mechanical repair is **`--tstack=65536`** for
each relevant Lean process. No theorem, coefficient or accepted root was
weakened. Generated files and logs record the actual invocation and version.
The public portable receipt uses relative links; local raw receipts may contain
the executing checkout's absolute paths. Source existence, statement printing,
axiom auditing and numerical agreement are each distinct from completed
kernel checking.

CI has a separate mandatory formal job. It downloads the official Linux
4.21.0 binary and verifies its pinned SHA-256, rebuilds the library, and runs
the same command. It does not accept cached `.olean` files as proof evidence.
