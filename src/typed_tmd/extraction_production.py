"""Parameterized, typed production routes for the frozen H003 diagnostic.

The retained H003 implementation is not changed by this module.  A and B are
compiled through different complete transport chains.  Both use the production
scale quadrature and the same verified native inputs; neither is the independent
canonical reference.  Read-only numerical caches record their construction and
input identities.  A cache identity records provenance, not a proof of accuracy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol

import numpy as np
from scipy.special import j0

from .contracts import (AccuracySpec, CoefficientOrders, Conventions,
                        ContractError, DefinitionSpec, Evidence, EvidenceStatus,
                        ExternalInput, KinematicDomain, Provenance, ScalePoint,
                        TMDContext, finite, require_compatible)
from .expressions import (BoundaryTMD, BoundaryTransport, EvolvedTMD,
                          EvolutionMap, TransportedBoundary)
from .extraction import Chart, ModelTemplate, ObservationTarget
from .provider_replay import digest, parse_hex
from .qcd_forward import ProductionMoments
from .qcd_plan import profile_mu


A = ScalePoint(5.0, 25.0)
B = ScalePoint(10.0, 100.0)
PIDS = (-3, -2, -1, 1, 2, 3)
CHARGES = ((1, 1.0 / 9), (2, 4.0 / 9), (3, 1.0 / 9))
WINDOW = (0.0001, 8.0)
LOG2 = math.log(2.0)
EVALUATOR_ID = "parameterized-production-complete-routes-v1"
COEFFICIENT_DEFINITION = "gamma_F=c*(1.5*lambda-log(zeta/mu^2)); gamma_K=2*c; c=4*alpha_s/(3*pi)"
COEFFICIENT_REGISTRY = (("approved", 1.0), ("noncusp-coefficient-lambda-0p8", 0.8))
LOCAL_INVENTORY = (("H", 0), ("C", 0), ("K_generator", 1), ("gamma_F", 1), ("cusp", 1))


class ProductionInputs(Protocol):
    """Provider interface; no LHAPDF import or interpolation is performed here."""
    identifier: str
    snapshot_id: str
    quantity: str
    inspection: dict
    plan: dict

    def f(self, pid: int, x: float, mu_GeV: float) -> float: ...
    def alpha_s(self, mu_GeV: float) -> float: ...


def _registered(model: ModelTemplate) -> None:
    if not isinstance(model, ModelTemplate):
        raise ContractError("production_requires_registered_model_template")
    lam = finite(model.lam, "lambda")
    if (model.coefficient_id, lam) not in COEFFICIENT_REGISTRY:
        raise ContractError("production_coefficient_identity_mismatch")


def gamma_F(alpha_s: float, mu_GeV: float, zeta_GeV2: float,
            model: ModelTemplate) -> float:
    """Registered local coefficient; independently test a representative value."""
    _registered(model)
    alpha = finite(alpha_s, "alpha_s", positive=True)
    mu = finite(mu_GeV, "mu", positive=True)
    zeta = finite(zeta_GeV2, "zeta", positive=True)
    return (4.0 / 3.0) * alpha / math.pi * (1.5 * model.lam - math.log(zeta / (mu * mu)))


@dataclass(frozen=True)
class BoundProductionModel:
    """Exact parameter identity is distinct from tolerance-based chart equality."""
    template: ModelTemplate
    canonical: tuple[float, float]
    coordinates: tuple[float, float]
    chart: str
    identity: str
    evolution_id: str


def bind_parameters(coordinates, chart: Chart, model: ModelTemplate) -> BoundProductionModel:
    _registered(model)
    if not isinstance(chart, Chart) or chart.name not in ("A", "B"):
        raise ContractError("production_requires_parameter_chart")
    raw = np.asarray(coordinates, dtype=float)
    if raw.shape != (2,) or not np.all(np.isfinite(raw)):
        raise ContractError("invalid_parameter_vector")
    if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(coordinates).flat):
        raise ContractError("boolean_parameter")
    canonical = chart.canonical(raw)
    a, g2 = map(float, canonical)
    # Immutable constants here avoid relying on the old module's mutable arrays.
    if not (0.1 - 1e-14 <= a <= 0.5 + 1e-14 and -1e-14 <= g2 <= 0.1 + 1e-14):
        raise ContractError("parameter_outside_mapped_domain")
    coefficient = {"id": model.coefficient_id, "lambda_hex": float(model.lam).hex(),
                   "definition": COEFFICIENT_DEFINITION, "evaluator": EVALUATOR_ID}
    identity = digest({"coefficient": coefficient, "a_hex": a.hex(), "g2_hex": g2.hex()})
    evolution = digest({"coefficient": coefficient, "g2_hex": g2.hex(),
                        "kernel": "-g2*b^2-2*integral_mu_b^mu c dlnmu"})
    return BoundProductionModel(model, (a, g2), tuple(map(float, raw)), chart.name,
                                identity, evolution)


def _freeze(value) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ContractError("nonfinite_compiled_factor")
    # An immutable bytes owner also prevents callers from re-enabling write access.
    return np.frombuffer(np.ascontiguousarray(array).tobytes(), dtype=np.float64).reshape(array.shape)


def _array_digest(array: np.ndarray) -> str:
    value = np.asarray(array, dtype="<f8")
    header = digest({"shape": list(value.shape), "dtype": "little-endian-binary64"})
    return hashlib.sha256(header.encode("ascii") + value.tobytes()).hexdigest()


def _source_hashes() -> tuple[tuple[str, str], ...]:
    root = Path(__file__).resolve().parent
    names = ("extraction_production.py", "extraction.py", "contracts.py",
             "expressions.py", "qcd_forward.py", "qcd_plan.py", "provider_replay.py")
    return tuple((name, hashlib.sha256((root / name).read_bytes()).hexdigest()) for name in names)


def _physical_rows(plan: dict) -> tuple[ObservationTarget, ...]:
    rows = []
    seen = set()
    for point in plan["points"]:
        if set(point) != {"Q_GeV", "qT_GeV", "x_a", "x_b"}:
            raise ContractError("production_observation_fields")
        values = {key: parse_hex(value) for key, value in point.items()}
        Q, qT = values["Q_GeV"], values["qT_GeV"]
        if Q not in (20.0, 30.0, 40.0) or qT not in tuple(Q * r for r in (.025, .05, .1)):
            raise ContractError("production_frozen_kinematics")
        expected = (Q * math.exp(.3) / 200.0, Q * math.exp(-.3) / 200.0)
        if (values["x_a"], values["x_b"]) != expected:
            raise ContractError("production_beam_kinematics_mismatch")
        key = (Q, qT)
        if key in seen:
            raise ContractError("production_duplicate_observation")
        seen.add(key)
        rows.append(ObservationTarget(**values))
    expected_keys = {(Q, Q * r) for Q in (20., 30., 40.) for r in (.025, .05, .1)}
    if seen != expected_keys:
        raise ContractError("production_incomplete_frozen_grid")
    return tuple(rows)


def _provider_contract(provider: ProductionInputs, plan: dict) -> tuple[dict, str]:
    if provider.quantity != "f" or not provider.identifier or not provider.snapshot_id:
        raise ContractError("production_provider_convention_or_identity")
    doc = provider.plan
    if doc.get("schema") != "typed_tmd.provider_query_plan.v1" or not doc.get("payload_sha256"):
        raise ContractError("production_provider_plan_identity")
    # ReplayProvider already checks its full envelope.  The compiler accepts its
    # exact payload object, or a separate payload only after a full hash match.
    if plan is not doc["payload"] and digest(plan) != doc["payload_sha256"]:
        raise ContractError("production_provider_plan_mismatch")
    if plan.get("provider_id") != provider.identifier:
        raise ContractError("production_provider_plan_mismatch")
    ip = provider.inspection["payload"]
    if plan.get("inspection_sha256") != provider.inspection["payload_sha256"]:
        raise ContractError("production_inspection_identity_mismatch")
    if (plan.get("set"), plan.get("member")) != (ip.get("set"), ip.get("member")):
        raise ContractError("production_provider_dataset_mismatch")
    if not set(PIDS).issubset(ip["flavors"]):
        raise ContractError("production_provider_missing_light_flavor")
    return ip, doc["payload_sha256"]


def _context(provider: ProductionInputs, ip: dict) -> TMDContext:
    dataset = f"{ip['set']}/{ip['member']}"
    effective = ip["effective"]
    files = ip["files"]
    pdf = ExternalInput(provider.identifier, dataset, "provider f; exact finite native replay",
                        files["set_info"]["sha256"] + ":" + files["member_data"]["sha256"],
                        "OrderQCD=" + str(effective["OrderQCD"]["value"]),
                        "external collinear evolution; no local P implemented",
                        "native flavor policy; light u,d,s electromagnetic current")
    coupling = ExternalInput(provider.identifier, dataset, "provider alpha_s; exact finite native replay",
                             ip["alpha_table_sha256"],
                             "AlphaS_OrderQCD=" + str(effective["AlphaS_OrderQCD"]["value"]),
                             "external running; no local beta implemented",
                             "native coupling thresholds and interpolation retained")
    return TMDContext(
        process="dy_unpolarized_angular_integrated", hadron="proton",
        definition=DefinitionSpec("Collins-soft-subtracted-unpolarized-DY-v1",
                                  "unpolarized quark TMD", "MSbar", "Collins", "soft-subtracted",
                                  "past-pointing DY staple"),
        conventions=Conventions(provider_quantity="f", momentum_density_measure="d2qT"),
        accuracy=AccuracySpec("external_inputs", "one-loop-generator/tree-matching diagnostic",
                              "a_s=alpha_s/(4*pi)", CoefficientOrders(0, 0, 1, 1, 1),
                              pdf, coupling, "RG_integral_of_one_loop_gamma_K_with_native_alpha_s"),
        domain=KinematicDomain(parse_hex(ip["bounds"]["x_min"]), parse_hex(ip["bounds"]["x_max"]),
                               20., 40., .1, WINDOW[0], WINDOW[1]),
        provider_id=provider.identifier + ":snapshot:" + provider.snapshot_id)


class ParameterizedProduction:
    """Direct typed expression interpreter; no compiled response arrays are used.

    Native scale moments are lazy and may be reused as a low-level quadrature
    utility.  Parameters, target, expression and endpoints are validated before
    the first PDF or alpha_s access for a requested evaluation.
    """
    def __init__(self, provider: ProductionInputs, plan: dict, scale_variant: str = "P32"):
        if scale_variant not in ("P16", "P32"):
            raise ContractError("production_scale_variant")
        ip, self.plan_id = _provider_contract(provider, plan)
        self.rows = _physical_rows(plan)
        if scale_variant not in plan["scale_plans"]:
            raise ContractError("production_missing_scale_plan")
        self.provider, self.plan, self.scale_variant = provider, plan, scale_variant
        self.context = _context(provider, ip)
        self._bounds = {name: parse_hex(value) for name, value in ip["bounds"].items()}
        self._moments = None

    @property
    def moments(self) -> ProductionMoments:
        if self._moments is None:
            self._moments = ProductionMoments(self.provider, self.plan, self.scale_variant)
        return self._moments

    def _endpoint(self, mu: float) -> None:
        mu = finite(mu, "mu", positive=True)
        if not self._bounds["alpha_min"] <= mu <= self._bounds["alpha_max"]:
            raise ContractError("production_coupling_support")
        if mu.hex() not in self.plan["scale_plans"][self.scale_variant]["partial"]:
            raise ContractError("production_unplanned_scale_endpoint")

    def _point(self, pid: int, x: float, b: float, Q: float) -> None:
        if type(pid) is not int or pid not in PIDS:
            raise ContractError("production_light_current_only")
        self.context.domain.validate_x_b(x, b)
        if Q not in (20., 30., 40.):
            raise ContractError("production_frozen_Q")
        allowed_x = {r.x_a for r in self.rows if r.Q_GeV == Q} | {r.x_b for r in self.rows if r.Q_GeV == Q}
        if x not in allowed_x:
            raise ContractError("production_unplanned_beam_x")
        if not self._bounds["q_min"] <= profile_mu(b) <= self._bounds["q_max"]:
            raise ContractError("production_pdf_scale_support")
        for scale in (profile_mu(b), 5., 10., Q):
            self._endpoint(scale)

    def _parts(self, b: float, source: ScalePoint, target: ScalePoint,
               path: str = "rapidity_first") -> tuple[float, float, float]:
        """Per-leg log-U at lambda=1, d/dlambda, d/dg2 for one segment."""
        dv = .5 * math.log(target.zeta_GeV2 / source.zeta_GeV2)
        d0, d1 = self.moments.between(source.mu_GeV, target.mu_GeV)
        kernel_mu = source.mu_GeV if path == "rapidity_first" else target.mu_GeV
        zeta = target.zeta_GeV2 if path == "rapidity_first" else source.zeta_GeV2
        k0, _ = self.moments.between(profile_mu(b), kernel_mu)
        perturb = -2 * k0 * dv + (1.5 - math.log(zeta)) * d0 + 2 * d1
        return perturb, 1.5 * d0, -b * b * dv

    def log_transport(self, b: float, source: ScalePoint, target: ScalePoint,
                      coordinates, chart: Chart, model: ModelTemplate,
                      path: str = "rapidity_first") -> float:
        bound = bind_parameters(coordinates, chart, model)
        if path not in ("rapidity_first", "mu_first"):
            raise ContractError("production_unknown_evolution_path")
        if not isinstance(source, ScalePoint) or not isinstance(target, ScalePoint):
            raise ContractError("production_scale_point_required")
        b = finite(b, "b_T", positive=True)
        if not WINDOW[0] <= b <= WINDOW[1]:
            raise ContractError("production_b_window")
        for mu in (profile_mu(b), source.mu_GeV, target.mu_GeV):
            self._endpoint(mu)
        p, lam, g = self._parts(b, source, target, path)
        return p + (model.lam - 1) * lam + bound.canonical[1] * g

    def _map(self, source: ScalePoint, target: ScalePoint, bound: BoundProductionModel, tag: str):
        return EvolutionMap(self.context, source, target, bound.evolution_id,
                            Provenance(tag, "parameter-bound completed one-loop connection",
                                       (Evidence("Context, parameter identity and endpoints checked",
                                                 EvidenceStatus.TYPE_CHECKED),)))

    def target_expressions(self, pid: int, b: float, Q: float, coordinates,
                           chart: Chart, model: ModelTemplate):
        bound = bind_parameters(coordinates, chart, model)
        if type(pid) is not int or pid not in PIDS or Q not in (20., 30., 40.):
            raise ContractError("production_expression_flavor_or_Q")
        b = finite(b, "b_T", positive=True)
        if not WINDOW[0] <= b <= WINDOW[1]:
            raise ContractError("production_b_window")
        mub = profile_mu(b)
        for mu in (mub, A.mu_GeV, B.mu_GeV, Q):
            self._endpoint(mu)
        sb, target = ScalePoint(mub, mub * mub), ScalePoint(Q, Q * Q)
        boundary = BoundaryTMD(self.context, pid, sb, bound.identity, bound.evolution_id,
                               "matching", Provenance(bound.identity, "parameter-bound f(x,mu_b)*exp(-a*b^2)"))
        at_a = BoundaryTransport(self._map(sb, A, bound, "sb-to-A"), "matching", "A").apply(boundary)
        at_b = BoundaryTransport(self._map(A, B, bound, "A-to-B"), "A", "B").apply(at_a)
        return self._map(A, target, bound, "A-to-target").apply(at_a), self._map(B, target, bound, "B-to-target").apply(at_b)

    def evaluate(self, expression, x: float, b: float, coordinates,
                 chart: Chart, model: ModelTemplate) -> float:
        bound = bind_parameters(coordinates, chart, model)
        if not isinstance(expression, EvolvedTMD):
            raise ContractError("production_requires_complete_target_expression")
        require_compatible(self.context, expression.context)
        self._point(expression.flavor, x, b, expression.scale.mu_GeV)
        expected = self.target_expressions(expression.flavor, b, expression.scale.mu_GeV,
                                            coordinates, chart, model)[0 if chart.name == "A" else 1]
        if expression != expected:
            raise ContractError("production_expression_or_parameter_identity_mismatch")

        def interpret(node):
            if isinstance(node, BoundaryTMD):
                return self.provider.f(node.flavor, x, node.scale.mu_GeV) * math.exp(-bound.canonical[0] * b * b)
            if isinstance(node, TransportedBoundary):
                transport = node.boundary_transport.evolution
            else:
                transport = node.transport
            return interpret(node.operand) * math.exp(self.log_transport(
                b, transport.source, transport.target, coordinates, chart, model))
        return finite(interpret(expression), "TMD result")

    def tmd(self, pid: int, x: float, b: float, Q: float, coordinates,
            chart: Chart, model: ModelTemplate) -> float:
        bind_parameters(coordinates, chart, model)
        self._point(pid, x, b, Q)
        expression = self.target_expressions(pid, b, Q, coordinates, chart, model)[0 if chart.name == "A" else 1]
        return self.evaluate(expression, x, b, coordinates, chart, model)


@dataclass(frozen=True)
class RouteFactors:
    name: str
    path: tuple[str, ...]
    weights: np.ndarray
    base: np.ndarray
    perturbative_segments: np.ndarray
    lambda_segments: np.ndarray
    g2_segments: np.ndarray

    def __post_init__(self):
        for name in ("weights", "base", "perturbative_segments", "lambda_segments", "g2_segments"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))


@dataclass(frozen=True)
class ProductionWindow:
    targets: tuple[ObservationTarget, ...]
    b: np.ndarray
    route_a: RouteFactors
    route_b: RouteFactors
    identity: Mapping[str, object]

    def __post_init__(self):
        object.__setattr__(self, "targets", tuple(self.targets))
        object.__setattr__(self, "b", _freeze(self.b))
        object.__setattr__(self, "identity", MappingProxyType(dict(self.identity)))
        expected = (len(self.targets), len(self.b))
        for route, name, segments in ((self.route_a, "A", 2), (self.route_b, "B", 3)):
            if route.name != name or route.base.shape != expected or route.weights.shape != expected:
                raise ContractError("production_cache_shape_or_route")
            if any(getattr(route, field).shape != expected + (segments,) for field in
                   ("perturbative_segments", "lambda_segments", "g2_segments")):
                raise ContractError("production_cache_transport_shape")

    def response(self, coordinates, chart: Chart, model: ModelTemplate):
        bound = bind_parameters(coordinates, chart, model)
        route = self.route_a if chart.name == "A" else self.route_b
        b2 = self.b[None, :] ** 2
        g_transport = np.sum(route.g2_segments, axis=2)
        lambda_transport = np.sum(route.lambda_segments, axis=2)
        if chart.name == "A":
            boundary = -bound.coordinates[0] * b2
            derivative_g = g_transport
        else:
            # beta is an actual B-chart input.  Its extra g2*ln(2) boundary
            # term and all three g2-dependent transports are rebound each call.
            boundary = -bound.coordinates[0] * b2 + bound.canonical[1] * LOG2 * b2
            derivative_g = g_transport + LOG2 * b2
        exponent = 2 * (boundary + bound.canonical[1] * g_transport +
                        (model.lam - 1) * lambda_transport)
        term = route.weights * route.base * np.exp(exponent)
        values = np.sum(term, axis=1)
        jacobian = np.column_stack((np.sum(-2 * b2 * term, axis=1),
                                    np.sum(2 * derivative_g * term, axis=1)))
        lambda_jacobian = np.sum(2 * lambda_transport * term, axis=1)
        if not all(np.all(np.isfinite(v)) for v in (values, jacobian, lambda_jacobian)):
            raise ContractError("production_nonfinite_response")
        return values, jacobian, lambda_jacobian


def compile_production_window(provider: ProductionInputs, plan: dict, *, b_variant: str,
                              scale_variant: str, Q_values=(20., 40.)) -> ProductionWindow:
    if b_variant not in ("P16", "P32") or scale_variant not in ("P16", "P32"):
        raise ContractError("production_quadrature_variant")
    requested = tuple(finite(q, "Q", positive=True) for q in Q_values)
    if not requested or requested != tuple(sorted(set(requested))) or any(q not in (20., 30., 40.) for q in requested):
        raise ContractError("production_requested_Q_order")
    evaluator = ParameterizedProduction(provider, plan, scale_variant)
    targets = tuple(row for row in evaluator.rows if row.Q_GeV in requested)
    if tuple((r.Q_GeV, r.qT_GeV) for r in targets) != tuple((Q, Q * ratio) for Q in requested for ratio in (.025, .05, .1)):
        raise ContractError("production_observation_row_order")
    window_plan = plan["b_plans"]["nominal"]
    edges = tuple(map(parse_hex, window_plan["edges_hex"]))
    if len(edges) < 2 or (edges[0], edges[-1]) != WINDOW or any(a >= b for a, b in zip(edges, edges[1:])):
        raise ContractError("production_frozen_window")
    nodes = window_plan["variants"][b_variant]
    if not nodes or any(len(row) != 2 for row in nodes):
        raise ContractError("production_b_nodes")
    b = np.array([parse_hex(row[0]) for row in nodes])
    w = np.array([parse_hex(row[1]) for row in nodes])
    if (np.any(b <= WINDOW[0]) or np.any(b >= WINDOW[1]) or np.any(np.diff(b) <= 0) or
            np.any(w <= 0) or not math.isclose(float(np.sum(w)), WINDOW[1] - WINDOW[0], rel_tol=1e-12, abs_tol=1e-12)):
        raise ContractError("production_b_quadrature_support_or_weights")
    # Every target and endpoint is checked before moments create any alpha_s calls.
    for target in targets:
        for bi in b:
            evaluator._point(1, target.x_a, float(bi), target.Q_GeV)
            evaluator._point(-1, target.x_b, float(bi), target.Q_GeV)

    compiled = []
    for route_name in ("A", "B"):
        bases, weights, p_rows, l_rows, g_rows = [], [], [], [], []
        for target in targets:
            luminosity, per_p, per_l, per_g = [], [], [], []
            for bi in b:
                bi = float(bi)
                mu = profile_mu(bi)
                sb, final = ScalePoint(mu, mu * mu), ScalePoint(target.Q_GeV, target.Q_GeV ** 2)
                chain = (sb, A, final) if route_name == "A" else (sb, A, B, final)
                parts = [evaluator._parts(bi, source, dest) for source, dest in zip(chain, chain[1:])]
                per_p.append([part[0] for part in parts])
                per_l.append([part[1] for part in parts])
                per_g.append([part[2] for part in parts])
                # Each route assembles its own luminosity and perturbative base.
                total = 0.0
                for pid, charge in CHARGES:
                    total += charge * (provider.f(pid, target.x_a, mu) * provider.f(-pid, target.x_b, mu) +
                                       provider.f(-pid, target.x_a, mu) * provider.f(pid, target.x_b, mu))
                luminosity.append(total)
            p_array = np.asarray(per_p)
            bases.append(np.asarray(luminosity) * np.exp(2 * np.sum(p_array, axis=1)))
            weights.append(w * b * j0(b * target.qT_GeV) / (2 * math.pi))
            p_rows.append(per_p)
            l_rows.append(per_l)
            g_rows.append(per_g)
        path = ("sb", "A", "target") if route_name == "A" else ("sb", "A", "B", "target")
        compiled.append(RouteFactors(route_name, path, np.asarray(weights), np.asarray(bases),
                                     np.asarray(p_rows), np.asarray(l_rows), np.asarray(g_rows)))
    target_rows = tuple((r.Q_GeV.hex(), r.qT_GeV.hex(), r.x_a.hex(), r.x_b.hex(),
                         tuple(v.hex() for v in r.window), r.measure, r.units) for r in targets)
    identity = {"evaluator_id": EVALUATOR_ID, "provider_id": provider.identifier,
                "snapshot_id": provider.snapshot_id, "plan_id": evaluator.plan_id,
                "inspection_id": provider.inspection["payload_sha256"],
                "context_sha256": digest(asdict(evaluator.context)),
                "target_rows": target_rows, "target_sha256": digest(target_rows),
                "b_variant": b_variant, "scale_variant": scale_variant,
                "local_highest_powers": LOCAL_INVENTORY, "P": "external", "beta": "external",
                "coefficient_registry": COEFFICIENT_REGISTRY, "coefficient_definition": COEFFICIENT_DEFINITION,
                "parameter_domain_GeV2": (("a", .1, .5), ("g2", 0., .1)),
                "b_star_max_GeV_inv": .5, "source_sha256": _source_hashes(),
                "route_paths": tuple((r.name, r.path) for r in compiled),
                "factor_sha256": tuple((r.name, field, _array_digest(getattr(r, field))) for r in compiled
                                       for field in ("weights", "base", "perturbative_segments", "lambda_segments", "g2_segments")),
                "b_nodes_sha256": _array_digest(b),
                "evidence_status": "construction_and_input_identity_checked; numerical_validation_separate"}
    identity["cache_sha256"] = digest(identity)
    return ProductionWindow(targets, b, compiled[0], compiled[1], identity)
