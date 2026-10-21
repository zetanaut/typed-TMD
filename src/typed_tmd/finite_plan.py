"""H007: exact finite-expression translation and dependency-safe cache plans.

This executable reference checker is not itself a kernel-checked Python program.
The corresponding Lean definitions/theorems are in formal/007.  A runtime check
and a successful Lean certificate check have different evidence statuses.

The language deliberately preserves operation order: no ring rewrites, exp
splitting, summation reassociation, or numerical-error claims are hidden here.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any
from types import MappingProxyType

from .contracts import ContractError

SCHEMA = "typed-tmd/finite-plan/007-v1"
LEAN_VERSION = "4.21.0"
# Ordinary kernel reduction of full literal plans exceeds Lean's default stack
# on macOS. This changes a resource limit, not the checker or its trust level.
LEAN_STACK_KB = 65536
MAX_NODES = 500_000


@dataclass(frozen=True)
class Expr:
    tag: str
    ident: int
    children: tuple[Expr, ...] = ()

    def __post_init__(self):
        arity = {"var": 0, "atom": 0, "unary": 1, "binary": 2}
        if (self.tag not in arity or type(self.ident) is not int or self.ident < 0
                or type(self.children) is not tuple or len(self.children) != arity[self.tag]
                or any(not isinstance(e, Expr) for e in self.children)):
            raise ContractError("invalid_finite_expression")


@dataclass(frozen=True)
class Plan:
    tag: str
    expr: Expr | None = None
    ident: int = 0
    children: tuple[Plan, ...] = ()

    def __post_init__(self):
        arity = {"live": 0, "cache": 0, "unary": 1, "binary": 2}
        if (self.tag not in arity or type(self.ident) is not int or self.ident < 0
                or type(self.children) is not tuple or len(self.children) != arity[self.tag]
                or any(not isinstance(p, Plan) for p in self.children)):
            raise ContractError("invalid_finite_plan")
        if ((self.tag in ("live", "cache") and not isinstance(self.expr, Expr))
                or (self.tag not in ("live", "cache") and self.expr is not None)):
            raise ContractError("plan_leaf_expression")
        if self.tag in ("live", "cache") and self.ident != 0:
            raise ContractError("plan_leaf_unused_field")


def var(i: int) -> Expr:
    return Expr("var", i)


def atom(i: int) -> Expr:
    return Expr("atom", i)


def unary(k: int, x: Expr) -> Expr:
    return Expr("unary", k, (x,))


def binary(k: int, x: Expr, y: Expr) -> Expr:
    return Expr("binary", k, (x, y))


def dependencies(e: Expr) -> frozenset[int]:
    if e.tag == "var":
        return frozenset((e.ident,))
    return frozenset().union(*(dependencies(c) for c in e.children))


def cacheable(e: Expr, varying: Sequence[bool]) -> bool:
    dep = dependencies(e)
    if any(i >= len(varying) for i in dep):
        raise ContractError("unbound_parameter")
    return not any(varying[i] for i in dep)


def erase(p: Plan) -> Expr:
    if p.tag in ("live", "cache"):
        assert p.expr is not None
        return p.expr
    return Expr(p.tag, p.ident, tuple(erase(c) for c in p.children))


def safe(p: Plan, varying: Sequence[bool]) -> bool:
    if p.tag == "live":
        assert p.expr is not None
        cacheable(p.expr, varying)  # also checks variable scope, not a cache request
        return True
    if p.tag == "cache":
        assert p.expr is not None
        return cacheable(p.expr, varying)
    return all(safe(c, varying) for c in p.children)


def check(e: Expr, p: Plan, varying: Sequence[bool]) -> None:
    """Rejects before invoking any primitive or numerical backend."""
    if any(type(v) is not bool for v in varying):
        raise ContractError("non_boolean_variation_mask")
    if erase(p) != e:
        raise ContractError("source_plan_erasure_mismatch")
    if not safe(p, varying):
        raise ContractError("cache_depends_on_fitted_parameter")


def propose(e: Expr, varying: Sequence[bool]) -> Plan:
    """Untrusted proposer; acceptance always uses check(), not this function."""
    if cacheable(e, varying):
        return Plan("cache", e)
    if e.tag in ("atom", "var"):
        return Plan("live", e)
    return Plan(e.tag, ident=e.ident, children=tuple(propose(c, varying) for c in e.children))


def substitute(e: Expr, sigma: Sequence[Expr]) -> Expr:
    if e.tag == "var":
        if e.ident >= len(sigma):
            raise ContractError("substitution_arity")
        return sigma[e.ident]
    return Expr(e.tag, e.ident, tuple(substitute(c, sigma) for c in e.children))


def compose(f: Sequence[Expr], g: Sequence[Expr]) -> tuple[Expr, ...]:
    """g after f. Objects are finite parameter interfaces, not numerical arrays."""
    return tuple(substitute(e, f) for e in g)


def respects_variation(f: Sequence[Expr], source_mask: Sequence[bool],
                       target_mask: Sequence[bool]) -> bool:
    if len(f) != len(target_mask):
        raise ContractError("variation_interface_arity")
    return all(target_mask[j] or cacheable(e, source_mask) for j, e in enumerate(f))


@dataclass(frozen=True)
class Algebra:
    atoms: tuple[float, ...]
    unary_ops: tuple[Callable[[float], float], ...]
    binary_ops: tuple[Callable[[float, float], float], ...]

    def eval(self, e: Expr, theta: Sequence[float]) -> float:
        if e.tag == "atom":
            return self.atoms[e.ident]
        if e.tag == "var":
            return float(theta[e.ident])
        values = tuple(self.eval(c, theta) for c in e.children)
        result = (self.unary_ops[e.ident](values[0]) if e.tag == "unary"
                  else self.binary_ops[e.ident](*values))
        if not math.isfinite(float(result)):
            raise ContractError("nonfinite_plan_evaluation")
        return float(result)


class PreparedPlan:
    """Evaluates exactly the accepted plan objects, never a regenerated plan.

    Caches are computed here from the retained source subtree at theta0. The
    caller cannot inject a numeric cache table. Primitive binding is an explicit
    trust boundary: functions must be pure for their complete declared inputs.
    """
    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            raise AttributeError("PreparedPlan is immutable")
        object.__setattr__(self, name, value)

    def __init__(self, source: Sequence[Expr], plans: Sequence[Plan],
                 varying: Sequence[bool], theta0: Sequence[float], algebra: Algebra,
                 *, context_identity: str, receipt: Mapping[str, Any] | None = None):
        if not source or len(source) != len(plans) or len(varying) != len(theta0) or not context_identity:
            raise ContractError("plan_interface_mismatch")
        if not all(math.isfinite(float(v)) for v in theta0):
            raise ContractError("nonfinite_reference_environment")
        if (type(algebra.atoms) is not tuple or type(algebra.unary_ops) is not tuple
                or type(algebra.binary_ops) is not tuple
                or any(not math.isfinite(float(v)) for v in algebra.atoms)
                or any(not callable(f) for f in algebra.unary_ops + algebra.binary_ops)):
            raise ContractError("invalid_algebra_binding")
        def scope(e):
            size = {"var": len(varying), "atom": len(algebra.atoms),
                    "unary": len(algebra.unary_ops), "binary": len(algebra.binary_ops)}[e.tag]
            if not 0 <= e.ident < size:
                raise ContractError("primitive_or_input_binding_scope")
            for c in e.children:
                scope(c)
        # Check the entire vector BEFORE initializing even one cached primitive.
        for e, p in zip(source, plans):
            check(e, p, varying)
            scope(e)
        self.source, self.plans = tuple(source), tuple(plans)
        self.varying, self.theta0 = tuple(varying), tuple(float(x) for x in theta0)
        self.algebra, self.context_identity = algebra, context_identity
        self.receipt = MappingProxyType(dict(receipt or {"status": "runtime_checked_only"}))
        cache: dict[Expr, float] = {}
        def initialize(p):
            if p.tag == "cache":
                if p.expr not in cache:
                    cache[p.expr] = algebra.eval(p.expr, self.theta0)
            for c in p.children:
                initialize(c)
        for p in self.plans:
            initialize(p)
        # Immutable storage; no external numerical cache values are accepted.
        self._cache_items = tuple(cache.items())
        self._cache = MappingProxyType(cache)
        self._sealed = True

    def evaluate(self, theta: Sequence[float], *, context_identity: str) -> tuple[float, ...]:
        if context_identity != self.context_identity:
            raise ContractError("cache_context_changed")
        if len(theta) != len(self.theta0) or not all(math.isfinite(float(x)) for x in theta):
            raise ContractError("parameter_environment")
        for i, varies in enumerate(self.varying):
            if not varies and float(theta[i]).hex() != self.theta0[i].hex():
                raise ContractError("fixed_parameter_changed")
        def run(p):
            if p.tag == "live":
                return self.algebra.eval(p.expr, theta)
            if p.tag == "cache":
                return self._cache[p.expr]
            args = tuple(run(c) for c in p.children)
            value = (self.algebra.unary_ops[p.ident](args[0]) if p.tag == "unary"
                     else self.algebra.binary_ops[p.ident](*args))
            if not math.isfinite(float(value)):
                raise ContractError("nonfinite_plan_evaluation")
            return float(value)
        return tuple(run(p) for p in self.plans)


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _hex(x: object) -> float:
    if type(x) is not str:
        raise ContractError("number_requires_canonical_hex")
    try:
        v = float.fromhex(x)
    except ValueError as exc:
        raise ContractError("invalid_hex_number") from exc
    if not math.isfinite(v) or v.hex() != x:
        raise ContractError("noncanonical_or_nonfinite_number")
    return v


def _keys(obj, keys):
    if type(obj) is not dict or set(obj) != set(keys):
        raise ContractError("wire_fields")


def _index(x, size):
    if type(x) is not int or not 0 <= x < size:
        raise ContractError("wire_index_or_forward_reference")
    return x


def encode(source: Sequence[Expr], plans: Sequence[Plan], *, names: Sequence[str],
           varying: Sequence[bool], theta0: Sequence[float], atom_values: Sequence[float],
           unary_symbols: Sequence[str], binary_symbols: Sequence[str],
           context: dict) -> dict:
    """Canonical topological tables. Source/candidate IDs remain separately visible."""
    es, ps, emap, pmap = [], [], {}, {}
    def eindex(e):
        if e in emap:
            return emap[e]
        children = [eindex(c) for c in e.children]
        i = len(es)
        es.append({"tag": e.tag, "id": e.ident, "args": children})
        emap[e] = i
        return i
    roots = [eindex(e) for e in source]
    def pindex(p):
        if p in pmap:
            return pmap[p]
        children = [pindex(c) for c in p.children]
        i = len(ps)
        ps.append({"tag": p.tag, "id": p.ident,
                   "expr": eindex(p.expr) if p.expr is not None else None, "args": children})
        pmap[p] = i
        return i
    proots = [pindex(p) for p in plans]
    doc = {"schema": SCHEMA, "context": context, "parameters": {
        "names": list(names), "varying": list(varying), "reference_hex": [float(x).hex() for x in theta0]},
        "atoms_hex": [float(x).hex() for x in atom_values], "unary_symbols": list(unary_symbols),
        "binary_symbols": list(binary_symbols), "expressions": es, "source_roots": roots,
        "plans": ps, "plan_roots": proots}
    decode(doc)  # Always validate a generated payload before exposing it.
    return doc


def decode(doc: dict) -> tuple[tuple[Expr, ...], tuple[Plan, ...], tuple[float, ...]]:
    _keys(doc, ("schema", "context", "parameters", "atoms_hex", "unary_symbols",
                "binary_symbols", "expressions", "source_roots", "plans", "plan_roots"))
    if doc["schema"] != SCHEMA or type(doc["context"]) is not dict or not doc["context"]:
        raise ContractError("wire_schema_or_context")
    p = doc["parameters"]
    _keys(p, ("names", "varying", "reference_hex"))
    if (type(p["names"]) is not list or any(type(x) is not str or not x for x in p["names"])
            or len(set(p["names"])) != len(p["names"])):
        raise ContractError("parameter_names")
    n = len(p["names"])
    if (type(p["varying"]) is not list or len(p["varying"]) != n
            or any(type(v) is not bool for v in p["varying"])
            or type(p["reference_hex"]) is not list or len(p["reference_hex"]) != n):
        raise ContractError("parameter_mask")
    tuple(_hex(x) for x in p["reference_hex"])
    for key in ("unary_symbols", "binary_symbols"):
        symbols = doc[key]
        if (type(symbols) is not list or any(type(s) is not str or not s for s in symbols)
                or len(set(symbols)) != len(symbols)):
            raise ContractError("primitive_symbol_registry")
    if type(doc["atoms_hex"]) is not list:
        raise ContractError("atom_table")
    values = tuple(_hex(x) for x in doc["atoms_hex"])
    es = []
    if type(doc["expressions"]) is not list or len(doc["expressions"]) > MAX_NODES:
        raise ContractError("expression_table_size")
    for row in doc["expressions"]:
        _keys(row, ("tag", "id", "args"))
        if type(row["args"]) is not list:
            raise ContractError("wire_arguments")
        args = tuple(es[_index(i, len(es))] for i in row["args"])
        e = Expr(row["tag"], row["id"], args)
        size = n if e.tag == "var" else (len(values) if e.tag == "atom" else len(doc[e.tag+"_symbols"]))
        _index(e.ident, size)
        es.append(e)
    ps = []
    if type(doc["plans"]) is not list or len(doc["plans"]) > MAX_NODES:
        raise ContractError("plan_table_size")
    for row in doc["plans"]:
        _keys(row, ("tag", "id", "expr", "args"))
        if type(row["args"]) is not list:
            raise ContractError("wire_arguments")
        args = tuple(ps[_index(i, len(ps))] for i in row["args"])
        expr = None if row["expr"] is None else es[_index(row["expr"], len(es))]
        plan = Plan(row["tag"], expr, row["id"], args)
        if plan.tag in ("unary", "binary"):
            _index(plan.ident, len(doc[plan.tag+"_symbols"]))
        ps.append(plan)
    for key in ("source_roots", "plan_roots"):
        if type(doc[key]) is not list or not doc[key]:
            raise ContractError("empty_or_invalid_roots")
    source = tuple(es[_index(i, len(es))] for i in doc["source_roots"])
    plans = tuple(ps[_index(i, len(ps))] for i in doc["plan_roots"])
    if len(source) != len(plans):
        raise ContractError("output_shape_mismatch")
    # Wire well-formedness is distinct from translation acceptance. Negative
    # plans may be encoded and inspected, but cannot become PreparedPlan.
    return source, plans, values


def read_wire(path: str | Path) -> dict:
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ContractError("duplicate_json_key")
            result[k] = v
        return result
    def bad_constant(s):
        raise ContractError("nonfinite_json_constant")
    doc = json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=bad_constant)
    decode(doc)
    return doc


def check_wire(doc: dict, *, expected_context: dict) -> None:
    source, plans, _ = decode(doc)
    if canonical(doc["context"]) != canonical(expected_context):
        raise ContractError("finite_plan_context_mismatch")
    for e, p in zip(source, plans):
        check(e, p, doc["parameters"]["varying"])


def prepare_wire(doc: dict, *, expected_context: dict,
                 unary_ops: Sequence[Callable], binary_ops: Sequence[Callable],
                 unary_symbols: Sequence[str], binary_symbols: Sequence[str]) -> PreparedPlan:
    """Explicit runtime-only path; it never claims Lean execution."""
    check_wire(doc, expected_context=expected_context)
    if list(unary_symbols) != doc["unary_symbols"] or list(binary_symbols) != doc["binary_symbols"]:
        raise ContractError("primitive_registry_identity")
    if len(unary_ops) != len(unary_symbols) or len(binary_ops) != len(binary_symbols):
        raise ContractError("primitive_registry_arity")
    source, plans, atoms = decode(doc)
    return PreparedPlan(source, plans, doc["parameters"]["varying"],
                        tuple(_hex(x) for x in doc["parameters"]["reference_hex"]),
                        Algebra(atoms, tuple(unary_ops), tuple(binary_ops)),
                        context_identity=digest(expected_context),
                        receipt={"status": "runtime_checked_only", "wire_sha256": digest(doc)})


def lean_certificate(doc: dict, *, expect_accept: bool = True) -> str:
    """Literal finite terms and kernel-reduced Bool acceptance, not native_decide.

    The JSON-to-Lean correspondence is tested, not formally proved. Each emitted
    theorem is about the exact literals printed below and the universal theorem
    in TypedTMDPlan.Core. No numerical sample supplies its conclusion.
    """
    decode(doc)
    n = len(doc["parameters"]["names"])
    out = ["import TypedTMDPlan.Core", "open TypedTMDPlan", "namespace WireCertificate",
           f"-- wire_sha256: {digest(doc)}", "set_option maxRecDepth 100000",
           "set_option maxHeartbeats 0", f"def varies : Fin {n} → Bool := fun i =>"]
    mask = doc["parameters"]["varying"]
    result = "false"
    for i in reversed(range(n)):
        result = f"if i.val = {i} then {str(mask[i]).lower()} else ({result})"
    out.append("  " + result)
    for i, row in enumerate(doc["expressions"]):
        tag, k, a = row["tag"], row["id"], row["args"]
        if tag == "var": term = f".var ⟨{k}, by decide⟩"
        elif tag == "atom": term = f".atom {k}"
        elif tag == "unary": term = f".unary {k} e{a[0]}"
        else: term = f".binary {k} e{a[0]} e{a[1]}"
        out.append(f"def e{i} : Expr {n} := {term}")
    for i, row in enumerate(doc["plans"]):
        tag, k, a = row["tag"], row["id"], row["args"]
        if tag in ("live", "cache"): term = f".{tag} e{row['expr']}"
        elif tag == "unary": term = f".unary {k} p{a[0]}"
        else: term = f".binary {k} p{a[0]} p{a[1]}"
        out.append(f"def p{i} : Plan {n} := {term}")
    for i, (e, p) in enumerate(zip(doc["source_roots"], doc["plan_roots"])):
        out.append(f"theorem accepted_{i} : check varies e{e} p{p} = {str(expect_accept).lower()} := by decide")
        if expect_accept:
            out += [f"theorem preservation_{i} {{α : Type}} (M : Model α)",
                    f"    (θ0 θ : Fin {n} → α) (fixed : FixedAgreement varies θ0 θ) :",
                    f"    Plan.eval M θ0 θ p{p} = Expr.eval M θ e{e} :=",
                    f"  check_sound M varies θ0 θ e{e} p{p} fixed accepted_{i}",
                    f"#print axioms preservation_{i}"]
    out += ["end WireCertificate", ""]
    return "\n".join(out)


def run_lean_certificate(doc: dict, project_dir: str | Path, output_dir: str | Path,
                         *, lake: str = "lake") -> dict:
    """Fail closed: absence of Lean is a blocked proof step, never acceptance.

    Runs a fresh certificate through the pinned local toolchain. This function
    does not install or upgrade the user's toolchain. Build the library first.
    """
    check_wire(doc, expected_context=doc["context"])
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    source = lean_certificate(doc)
    path = out / "Certificate.lean"
    path.write_text(source)
    result = {"wire_sha256": digest(doc), "certificate_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "status": "pending", "scope": "kernel-reduced acceptance for literal terms; decoder/FFI/IEEE not proved"}
    theory_dir = Path(project_dir).resolve()
    theory_files = sorted(theory_dir.rglob("*.lean"))
    theory_files = [p for p in theory_files if ".lake" not in p.relative_to(theory_dir).parts]
    theory_files += [theory_dir / "lean-toolchain", theory_dir / "lakefile.toml"]
    result["theory_sources"] = {str(p.relative_to(theory_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in theory_files if p.is_file()}
    result["theory_source_digest"] = digest(result["theory_sources"])
    try:
        version = subprocess.run([lake, "env", "lean", "--version"], cwd=project_dir,
                                 capture_output=True, text=True, timeout=30)
        (out / "version.log").write_text(version.stdout+version.stderr)
        if version.returncode or not re.search(r"version 4\.21\.0(?:,|\s|\))", version.stdout):
            raise ContractError("pinned_lean_version_required")
        command = [lake, "env", "lean", f"--tstack={LEAN_STACK_KB}", str(path.resolve())]
        result["command"] = command
        result["thread_stack_kb"] = LEAN_STACK_KB
        proc = subprocess.run(command, cwd=project_dir,
                              capture_output=True, text=True, timeout=600)
        text = proc.stdout+proc.stderr
        (out / "certificate.log").write_text(text)
        if proc.returncode != 0 or any(s in text for s in ("sorryAx", "ofReduceBool", "declaration uses 'sorry'")):
            result.update(status="failed", returncode=proc.returncode)
        elif "preservation_" not in text:
            result.update(status="failed", reason="expected_axiom_reports_absent", returncode=0)
        else:
            result.update(status="kernel_checked", returncode=0)
    except (OSError, subprocess.TimeoutExpired, ContractError) as exc:
        result.update(status="blocked", reason=str(exc))
    (out / "receipt.json").write_bytes(canonical(result)+b"\n")
    if result["status"] != "kernel_checked":
        raise ContractError("Lean certificate did not pass; see " + str(out / "receipt.json"))
    return result


def prepare_certified(doc: dict, *, expected_context: dict, unary_ops: Sequence[Callable],
                      binary_ops: Sequence[Callable], unary_symbols: Sequence[str],
                      binary_symbols: Sequence[str], project_dir: str | Path,
                      output_dir: str | Path, lake: str = "lake") -> PreparedPlan:
    """Fresh kernel check followed by binding the SAME sealed wire snapshot.

    Unavailable Lean is an error. There is no fallback to runtime-only evidence.
    The caller should freeze domain-checked primitive bindings before this call.
    """
    sealed = json.loads(canonical(doc))
    check_wire(sealed, expected_context=expected_context)
    if list(unary_symbols) != sealed["unary_symbols"] or list(binary_symbols) != sealed["binary_symbols"]:
        raise ContractError("primitive_registry_identity")
    if len(unary_ops) != len(unary_symbols) or len(binary_ops) != len(binary_symbols):
        raise ContractError("primitive_registry_arity")
    receipt = run_lean_certificate(sealed, project_dir, output_dir, lake=lake)
    source, plans, atoms = decode(sealed)
    return PreparedPlan(source, plans, sealed["parameters"]["varying"],
                        tuple(_hex(x) for x in sealed["parameters"]["reference_hex"]),
                        Algebra(atoms, tuple(unary_ops), tuple(binary_ops)),
                        context_identity=digest(expected_context), receipt=receipt)
