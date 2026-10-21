"""Lower concrete H006 observation geometry to the H007 finite language.

Uses the existing quadrature node functions but neither its integration routine
nor its response assembler. The callback is a complete point response with an
explicit parameter value. For H006 only c0 varies; other inputs are sealed into
context. A live native bridge must rebind the complete NP vector under the native
process-global lock and check the session epoch before every batch.
"""
from __future__ import annotations
from dataclasses import asdict
import math
from typing import Callable, Sequence
import numpy as np
from .contracts import ContractError
from .observations import ObservationContract
from .observation_quadrature import nodes, mass_nodes
from .finite_plan import (Expr, Plan, Algebra, PreparedPlan, atom, var, unary, binary,
                          propose, encode, prepare_wire, digest, check_wire)


def balanced_sum(items: Sequence[Expr], zero: Expr) -> Expr:
    """A specified binary tree, not a theorem about NumPy's reduction order."""
    items = tuple(items)
    if not items:
        return zero
    if len(items) == 1:
        return items[0]
    mid = len(items)//2
    return binary(0, balanced_sum(items[:mid], zero), balanced_sum(items[mid:], zero))


def observation_packet(contract: ObservationContract, orders=(8, 8, 4),
                       mass_breaks=(80., 86., 89., 91., 93., 96., 102.),
                       reference_c0=.029551) -> dict:
    """Finite GL source for h=dσ/(dqT² dQ² dy), average per declared qT measure.

    Every native call is explicitly unary in c0. Its coordinates, full row,
    physics identity, and fixed NP identity are part of the source context. This
    bridge refuses more than one fitted native parameter rather than hiding it.
    No kernel value is classified as a constant.
    """
    if len(orders) != 3 or any(type(n) is not int or n < 2 for n in orders):
        raise ContractError("quadrature_orders")
    constants: list[float] = []
    index: dict[str, int] = {}
    def const(x):
        x = float(x)
        if not math.isfinite(x):
            raise ContractError("nonfinite_geometry")
        key = x.hex()
        if key not in index:
            index[key] = len(constants)
            constants.append(x)
        return atom(index[key])
    samples = []
    roots = []
    zero = const(0.)
    for row_index, row in enumerate(contract.bins):
        qt, wq = nodes(*row.qT, orders[0])
        mass, wm = mass_nodes(row.Q, orders[1], mass_breaks)
        rap, wy = nodes(*row.y, orders[2])
        terms = []
        for iq, q in enumerate(qt):
            for im, Q in enumerate(mass):
                for iy, y in enumerate(rap):
                    symbol_index = len(samples)
                    samples.append({"row": row_index, "qT_hex": float(q).hex(),
                                    "Q_hex": float(Q).hex(), "y_hex": float(y).hex()})
                    # Retain the actual geometric operations rather than trusting
                    # a precombined floating weight as the entire source proof.
                    jac_q = binary(1, const(2.), const(q))
                    jac_Q = binary(1, const(2.), const(Q))
                    geometry = binary(1, binary(1, binary(1, jac_q, const(wq[iq])),
                                                 binary(1, jac_Q, const(wm[im]))), const(wy[iy]))
                    kernel = unary(symbol_index, var(0))
                    terms.append(binary(1, geometry, kernel))
        roots.append(binary(1, const(row.average_factor(contract.measure)), balanced_sum(terms, zero)))
    context = {"kind": "H006-finite-observation-source-v1", "observation": asdict(contract),
               "observation_digest": contract.digest, "expected_kind": "bin_average",
               "units": contract.units, "native_measure": "dqT2_dQ2_dy", "GL_orders": list(orders),
               "mass_breaks_hex": [float(x).hex() for x in mass_breaks], "samples": samples,
               "primitive_assumption": "same immutable native context; each kernel is a pure function of explicit c0",
               "native_parameter_count": 1, "finite_sum_order": "balanced source tree; separate float comparison to H006 NumPy"}
    return encode(roots, [propose(e, (True,)) for e in roots], names=("SV19.c0",), varying=(True,),
                  theta0=(reference_c0,), atom_values=constants,
                  unary_symbols=[f"point:{i}" for i in range(len(samples))],
                  binary_symbols=("add", "mul"), context=context)


def bind_observation_packet(doc: dict, contract: ObservationContract,
                            point: Callable[[object, float, float, float, float], float]) -> PreparedPlan:
    context = doc["context"]
    if (context.get("kind") != "H006-finite-observation-source-v1"
            or context.get("observation_digest") != contract.digest
            or context.get("expected_kind") != "bin_average"
            or context.get("units") != contract.units
            or context.get("native_parameter_count") != 1
            or context.get("observation") != _jsonable(asdict(contract))):
        # In-memory tuples serialize as lists; normalize below for the ordinary
        # direct constructor too.
        if not (context.get("observation_digest") == contract.digest
                and _jsonable(context.get("observation")) == _jsonable(asdict(contract))
                and context.get("kind") == "H006-finite-observation-source-v1"
                and context.get("expected_kind") == "bin_average"
                and context.get("units") == contract.units
                and context.get("native_parameter_count") == 1):
            raise ContractError("observation_binding_mismatch")
    if doc["parameters"]["names"] != ["SV19.c0"] or doc["parameters"]["varying"] != [True]:
        raise ContractError("native_fit_dependency_mismatch")
    # Validate source against regeneration from admitted geometry. This binds the
    # source itself; a preservation proof alone would not detect a forged source.
    regenerated = observation_packet(contract, tuple(context["GL_orders"]),
                    tuple(float.fromhex(x) for x in context["mass_breaks_hex"]),
                    float.fromhex(doc["parameters"]["reference_hex"][0]))
    for key in ("context", "atoms_hex", "unary_symbols", "binary_symbols", "expressions", "source_roots"):
        if digest(doc[key]) != digest(regenerated[key]):
            raise ContractError("observation_source_lowering_mismatch")
    callbacks = []
    for item in context["samples"]:
        row = contract.bins[item["row"]]
        q, Q, y = (float.fromhex(item[k]) for k in ("qT_hex", "Q_hex", "y_hex"))
        callbacks.append(lambda c0, row=row, q=q, Q=Q, y=y: float(point(row, q, Q, y, c0)))
    return prepare_wire(doc, expected_context=context, unary_ops=callbacks,
                        binary_ops=(lambda a,b:a+b, lambda a,b:a*b),
                        unary_symbols=[f"point:{i}" for i in range(len(callbacks))],
                        binary_symbols=("add", "mul"))


def _jsonable(value):
    import json
    return json.loads(json.dumps(value))


def kernel_cache_fixture(*, freeze_dynamic: bool = False) -> tuple[dict, tuple[float, ...]]:
    """A single evolved factor at unequal scales: value closure can miss a bug.

    F = exp(R - g*b² log(Q/QA))*exp(-a*b²).  The plan never splits exp or
    asserts a property of its floating implementation. The invalid candidate
    caches the entire g-dependent transport at theta0.
    """
    b, Q, QA, R = 1.3, 20., 5., .2
    c = (R, -b*b*math.log(Q/QA), -b*b)
    transport = unary(0, binary(0, atom(0), binary(1, var(1), atom(1))))
    boundary = unary(0, binary(1, var(0), atom(2)))
    source = binary(1, transport, boundary)
    plan = (Plan("binary", ident=1, children=(Plan("cache", transport), propose(boundary,(True,True))))
            if freeze_dynamic else propose(source,(True,True)))
    doc = encode((source,), (plan,), names=("a", "g2"), varying=(True,True), theta0=(.25,.04),
                 atom_values=c, unary_symbols=("exp",), binary_symbols=("add","mul"),
                 context={"fixture":"fitted-kernel-transport", "b_GeV_inv_hex":b.hex(),
                          "Q_GeV_hex":Q.hex(), "QA_GeV_hex":QA.hex(),
                          "units":"dimensionless", "stage":"finite idealized plan"})
    return doc, c


def production_window_packet(window, chart, model, reference=(.25,.04)) -> dict:
    """Export the actual H004 ProductionWindow factors to finite source syntax.

    Existing quadrature/PDF/scale coefficients are frozen atoms. Their
    approximation to QCD is not proved by this algebraic translation checker.
    The result evaluates both fitted coordinates as variables on every call.
    """
    from .extraction import LOG2
    constants = []
    indices = {}
    def const(x):
        x = float(x)
        if not math.isfinite(x):
            raise ContractError("nonfinite_H004_coefficient")
        key = x.hex()
        if key not in indices:
            indices[key] = len(constants)
            constants.append(x)
        return atom(indices[key])
    route = window.route_a if chart.name == "A" else window.route_b
    roots = []
    for i, target in enumerate(window.targets):
        terms = []
        for j, b in enumerate(window.b):
            b2 = float(b*b)
            boundary = binary(1, var(0), const(-b2))
            if chart.name == "B":
                boundary = binary(0, boundary, binary(1, var(1), const(LOG2*b2)))
            g = binary(1, var(1), const(np.sum(route.g2_segments[i,j])))
            lam = const((model.lam-1)*np.sum(route.lambda_segments[i,j]))
            exponent = binary(1, const(2.), binary(0, binary(0, boundary, g), lam))
            prefactor = binary(1, const(route.weights[i,j]), const(route.base[i,j]))
            terms.append(binary(1, prefactor, unary(0, exponent)))
        roots.append(balanced_sum(terms, const(0.)))
    raw_reference = chart.coordinates(reference)
    context = {"kind":"H004-ProductionWindow-finite-source-v1", "chart":chart.name,
               "model":{"coefficient_id":model.coefficient_id, "lambda_hex":model.lam.hex()},
               "cache_identity":dict(window.identity),
               "units":"GeV^-2", "measure":"d2qT", "window":[.0001,8.],
               "source_stage":"frozen scale/PDF/quadrature factors plus explicit a-or-beta,g2",
               "finite_sum_order":"balanced tree; compared numerically to NumPy reduction"}
    return encode(roots,[propose(e,(True,True)) for e in roots],
                  names=(("a" if chart.name=="A" else "beta"),"g2"),
                  varying=(True,True),theta0=raw_reference,atom_values=constants,
                  unary_symbols=("exp",),binary_symbols=("add","mul"),context=context)
