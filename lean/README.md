# Lean seed: scope and build status

**Status: abstract seed build verified with Lean 4.21.0.**
[VERIFICATION.json](VERIFICATION.json) contains the actual successful build
receipt and exact source hashes. The original authoring environment lacked
Lean; that historical limitation was superseded by the local build.
Verification is limited to the structural seed below; it does not verify
Python, the external native engine, floating-point execution or QCD.

## What is being checked

`TypedTMDSeed.lean` defines presentations indexed by a context, explicitly
admitted evolution steps, and observable outputs. A `Transformation A B` is a
map with two proof obligations: it commutes with each admitted evolution step
and it preserves the chosen observable response. `Transformation.comp`
constructs a composite transformation and proves both obligations. A second
theorem extends a primitive evolution certificate to a two-step calculation.

This is an exact, conditional algebraic seed. It supplies neither the premises
for a particular QCD realization nor an error theorem for floating-point code.
The numerical toy model and this Lean seed are separate implementations; their
semantic correspondence has not been formally proved. The source uses Lean's
core library only and does not require mathlib.

## Build on the already selected Lean 4.21.0 toolchain

From the project root, create a location for local logs:

```sh
mkdir -p results/local
cd lean
lean --version
lake build > ../results/local/lean-build.log 2>&1
```

Check the exit status immediately after `lake build`:

```sh
echo $?
```

A zero exit status, the version output `4.21.0`, and an inspected build log
are the expected checkpoint. Keep the log and source hash with the handoff:

```sh
shasum -a 256 TypedTMDSeed.lean > ../results/local/lean-source.sha256
```

`lean-toolchain` pins the version only in this `lean/` directory and its
descendants. It does not change the user's global default. `ELAN_TOOLCHAIN`
or a command-line toolchain selection can override a directory pin, so inspect
the version actually reported. Do not run `elan default` for this project.
If elan does not already have the pinned toolchain installed, the `lean` or
`lake` shim may offer/download it. First inspect `elan toolchain list`; a
missing toolchain is a separate local setup task, not a reason to change the
global default. An installed toolchain may be invoked explicitly as:

```sh
elan run leanprover/lean4:v4.21.0 lean --version
elan run leanprover/lean4:v4.21.0 lake build
```

The checkpoint runner writes a per-run `lean_verification.json` containing the
actual build status and source hashes beside its build log in `results/local`.
A successful receipt applies to the exact recorded source and supersedes the
seed's initial `VERIFICATION.json` status for that run. A subsequent handoff may
also update the seed record with `VERIFIED`, the exit code, log path, and source
hash. Do not infer proof verification merely from an installed compiler or
from the environment probe's result.

## Foundations and later growth

Lean 4 uses dependent type theory with proof-irrelevant propositional equality.
Higher mathematical structure can later be represented as explicit data;
different proofs of Lean equality are not nontrivial homotopy paths. This seed
keeps chosen maps as data and their correctness laws as propositions. It makes
no assumption that a homotopical construction of hadronic physics is already
available.

Official references:

- [Lake manual for Lean 4.21.0](https://lean-lang.org/doc/reference/4.21.0/Build-Tools-and-Distribution/Lake/)
- [Lean propositional equality](https://lean-lang.org/doc/reference/latest/Basic-Propositions/Propositional-Equality/)
