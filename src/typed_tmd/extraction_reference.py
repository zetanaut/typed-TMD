"""Independent canonical, per-leg scalar reference for the H003 extraction.

Only the native input interface, the declared profile, numerical reference
moments, and shared contract *types* are reused.  Neither the production
compiler nor its cache/exponent/luminosity assembly is used here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path

import numpy as np
from scipy.special import j0

from .contracts import ContractError
from .extraction import Chart, ModelTemplate, ObservationTarget
from .provider_replay import ReplayProvider, parse_hex
from .qcd_plan import profile_mu
from .qcd_reference import ReferenceMoments


REFERENCE_ID = "direct-canonical-per-leg-reference-v1"
_REGISTERED_LAMBDAS = {"approved": 1.0, "noncusp-coefficient-lambda-0p8": 0.8}
_Q_VALUES = (20.0, 30.0, 40.0)
_FRACTIONS = (0.025, 0.05, 0.1)
_CHARGES_SQUARED = (1.0 / 9.0, 4.0 / 9.0, 1.0 / 9.0)


class _FrozenIdentity(dict):
    """Read-only dict/tuple provenance that standard json.dumps can encode."""

    def __init__(self, entries):
        def freeze(value):
            if isinstance(value, dict):
                return _FrozenIdentity(value)
            if isinstance(value, (list, tuple)):
                return tuple(freeze(item) for item in value)
            return value
        dict.__init__(self, ((key, freeze(value)) for key, value in dict(entries).items()))

    def _immutable(self, *args, **kwargs):
        raise TypeError("reference_identity_is_immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable
    __ior__ = _immutable


def _checked_lambda(model: ModelTemplate) -> float:
    if not isinstance(model, ModelTemplate):
        raise ContractError("reference_model_type")
    expected = _REGISTERED_LAMBDAS.get(model.coefficient_id)
    if expected is None or isinstance(model.lam, bool) or model.lam != expected:
        raise ContractError("reference_coefficient_identity_mismatch")
    return float(model.lam)


def _linked_plan(provider: ReplayProvider, plan: dict) -> dict:
    """Bind to the payload already verified by the replay provider.

    Object identity avoids a second expensive hash of the complete finite
    query plan.  ReplayProvider verifies the document hashes on construction.
    """
    native_plan = getattr(provider, "plan", None)
    if not isinstance(native_plan, dict) or native_plan.get("payload") is not plan:
        raise ContractError("reference_plan_provider_mismatch")
    if (not getattr(provider, "identifier", None)
            or plan.get("provider_id") != provider.identifier
            or not native_plan.get("payload_sha256")
            or not getattr(provider, "snapshot_id", None)):
        raise ContractError("reference_provider_identity_missing")
    return native_plan


def _frozen_points(plan: dict) -> tuple[ObservationTarget, ...]:
    points = plan.get("points", [])
    expected = [(q, fraction * q) for q in _Q_VALUES for fraction in _FRACTIONS]
    if len(points) != len(expected):
        raise ContractError("reference_incomplete_frozen_grid")
    targets = []
    for point, (q, qt) in zip(points, expected):
        if set(point) != {"Q_GeV", "qT_GeV", "x_a", "x_b"}:
            raise ContractError("reference_point_shape")
        values = {key: parse_hex(value) for key, value in point.items()}
        if (values["Q_GeV"] != q or values["qT_GeV"] != qt
                or values["x_a"] != q * math.exp(0.3) / 200.0
                or values["x_b"] != q * math.exp(-0.3) / 200.0):
            raise ContractError("reference_frozen_kinematics_mismatch")
        targets.append(ObservationTarget(q, qt, values["x_a"], values["x_b"]))
    return tuple(targets)


def _requested_qs(values) -> tuple[float, ...]:
    requested = tuple(float(q) for q in values)
    if not requested or requested != tuple(q for q in _Q_VALUES if q in requested):
        raise ContractError("reference_Q_selection")
    return requested


@dataclass(frozen=True)
class _ScaleData:
    b: float
    mu_b: float
    log_q_over_mu_b: float
    integral_c: float
    integral_c_log_mu: float
    log_q: float

    def exponent(self, a: float, g2: float, lam: float) -> float:
        # Direct integration of c(mu) [3 lambda/2 - 2 ln(Q/mu)].
        noncusp = 1.5 * lam * self.integral_c
        sudakov = -2.0 * (
            self.log_q * self.integral_c - self.integral_c_log_mu)
        boundary = -a * self.b * self.b
        rapidity = -g2 * self.b * self.b * self.log_q_over_mu_b
        return math.fsum((noncusp, sudakov, boundary, rapidity))


class CanonicalReference:
    """Independent f(x,mu_b) exp(S_lambda) at the canonical final scales.

    Theta is always canonical (a,g2), even when a caller's fit uses chart B.
    Moments and scalar input values are cached; fit parameters are never
    frozen into that cache.  All numerical data come from the linked plan.
    """

    def __init__(self, provider: ReplayProvider, plan: dict, *,
                 scale_variant: str = "R8"):
        _linked_plan(provider, plan)
        _frozen_points(plan)
        if (scale_variant not in ("R4", "R8")
                or scale_variant not in plan.get("scale_plans", {})):
            raise ContractError("reference_scale_resolution")
        self.provider = provider
        self.plan = plan
        self.scale_variant = scale_variant
        self._moments = None
        self._scales: dict[tuple[float, float], _ScaleData] = {}
        self._pdf_values: dict[tuple[int, float, float], float] = {}

    def _scale_data(self, b: float, Q: float) -> _ScaleData:
        b, Q = float(b), float(Q)
        if not math.isfinite(b) or not 0.0001 <= b <= 8.0 or Q not in _Q_VALUES:
            raise ContractError("reference_TMD_kinematics")
        key = (b, Q)
        if key not in self._scales:
            if self._moments is None:
                self._moments = ReferenceMoments(
                    self.provider, self.plan, int(self.scale_variant[1:]))
            mu_b = profile_mu(b)
            lower0, lower1 = self._moments.moment(mu_b)
            upper0, upper1 = self._moments.moment(Q)
            self._scales[key] = _ScaleData(
                b, mu_b, math.log(Q / mu_b),
                upper0 - lower0, upper1 - lower1, math.log(Q))
        return self._scales[key]

    def _pdf(self, pid: int, x: float, mu: float) -> float:
        key = (pid, x, mu)
        if key not in self._pdf_values:
            self._pdf_values[key] = self.provider.f(pid, x, mu)
        return self._pdf_values[key]

    def tmd(self, pid: int, x: float, b: float, Q: float, theta,
            model: ModelTemplate) -> float:
        lam = _checked_lambda(model)
        a, g2 = Chart("A").canonical(theta)
        if type(pid) is not int or pid not in (-3, -2, -1, 1, 2, 3):
            raise ContractError("reference_TMD_flavor")
        if not math.isfinite(x) or not 0.0 < x < 1.0:
            raise ContractError("reference_TMD_x")
        data = self._scale_data(b, Q)
        amplitude = self._pdf(pid, float(x), data.mu_b)
        return amplitude * math.exp(data.exponent(float(a), float(g2), lam))


@dataclass(frozen=True)
class _PerLegNode:
    scales: _ScaleData
    # One tuple per positive flavor: q_A, qbar_B, qbar_A, q_B.
    amplitudes: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class _ReferenceGroup:
    nodes: tuple[_PerLegNode, ...]

    def integrands(self, a: float, g2: float, lam: float):
        luminosity, da, dg, dlambda = [], [], [], []
        for node in self.nodes:
            scale = node.scales
            evolution = math.exp(scale.exponent(a, g2, lam))
            products = []
            for charge, legs in zip(_CHARGES_SQUARED, node.amplitudes):
                quark_a, antiquark_b, antiquark_a, quark_b = (
                    amplitude * evolution for amplitude in legs)
                products.extend((charge * quark_a * antiquark_b,
                                 charge * antiquark_a * quark_b))
            value = math.fsum(products)
            luminosity.append(value)
            da.append((-2.0 * scale.b * scale.b) * value)
            dg.append((-2.0 * scale.b * scale.b *
                       scale.log_q_over_mu_b) * value)
            dlambda.append((3.0 * scale.integral_c) * value)
        return luminosity, da, dg, dlambda


@dataclass(frozen=True)
class ReferenceWindow:
    """A scalar per-leg reference cache with no production cache dependency."""

    targets: tuple[ObservationTarget, ...]
    identity: dict
    _groups: tuple[_ReferenceGroup, ...]
    _group_for_target: tuple[int, ...]
    _weights: tuple[tuple[float, ...], ...]

    def response(self, coordinates, chart: Chart, model: ModelTemplate):
        lam = _checked_lambda(model)
        if not isinstance(chart, Chart):
            raise ContractError("reference_chart_type")
        a, g2 = chart.canonical(coordinates)
        sampled = [group.integrands(float(a), float(g2), lam)
                   for group in self._groups]
        rows = []
        for group_index, weights in zip(self._group_for_target, self._weights):
            rows.append(tuple(math.fsum(w * value for w, value in zip(weights, column))
                              for column in sampled[group_index]))
        values = np.asarray(rows, dtype=float)
        canonical_jacobian = values[:, 1:3]
        return (values[:, 0],
                canonical_jacobian @ chart.jacobian_to_canonical(),
                values[:, 3])


def compile_reference_window(provider: ReplayProvider, plan: dict, *,
                             b_variant: str = "R64",
                             scale_variant: str = "R8",
                             Q_values=(20.0, 40.0)) -> ReferenceWindow:
    """Compile only native inputs and reference quadrature for the fixed window."""
    linked = _linked_plan(provider, plan)
    all_targets = _frozen_points(plan)
    requested = _requested_qs(Q_values)
    if b_variant not in ("R16", "R32", "R64"):
        raise ContractError("reference_b_resolution")
    nominal = plan.get("b_plans", {}).get("nominal", {})
    edges = tuple(parse_hex(value) for value in nominal.get("edges_hex", []))
    if (len(edges) < 2 or edges[0] != 0.0001 or edges[-1] != 8.0
            or any(a >= b for a, b in zip(edges, edges[1:]))):
        raise ContractError("reference_window_mismatch")
    encoded = nominal.get("variants", {}).get(b_variant)
    if not encoded:
        raise ContractError("reference_unplanned_b_resolution")
    nodes = tuple((parse_hex(b), parse_hex(w)) for b, w in encoded)
    if any(not edges[0] < b < edges[-1] or w <= 0.0 for b, w in nodes):
        raise ContractError("reference_quadrature_node")
    scalar = CanonicalReference(provider, plan, scale_variant=scale_variant)
    targets = tuple(target for target in all_targets if target.Q_GeV in requested)
    groups, group_ids, group_for_target, weights = [], {}, [], []
    for target in targets:
        group_key = (target.Q_GeV, target.x_a, target.x_b)
        if group_key not in group_ids:
            per_leg = []
            for b, _ in nodes:
                scales = scalar._scale_data(b, target.Q_GeV)
                native = tuple((
                    scalar._pdf(pid, target.x_a, scales.mu_b),
                    scalar._pdf(-pid, target.x_b, scales.mu_b),
                    scalar._pdf(-pid, target.x_a, scales.mu_b),
                    scalar._pdf(pid, target.x_b, scales.mu_b))
                    for pid in (1, 2, 3))
                per_leg.append(_PerLegNode(scales, native))
            group_ids[group_key] = len(groups)
            groups.append(_ReferenceGroup(tuple(per_leg)))
        group_for_target.append(group_ids[group_key])
        weights.append(tuple(
            w * b * float(j0(b * target.qT_GeV)) / (2.0 * math.pi)
            for b, w in nodes))
    identity = _FrozenIdentity({
        "schema": "typed_tmd.canonical_reference_window.v1",
        "evaluator_id": REFERENCE_ID,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "provider_id": provider.identifier,
        "snapshot_id": provider.snapshot_id,
        "plan_payload_sha256": linked["payload_sha256"],
        "coefficient_models": {
            name: {"noncusp_lambda": lam, "noncusp_coefficient": 1.5 * lam}
            for name, lam in _REGISTERED_LAMBDAS.items()},
        "coefficient_inventory": {
            "expansion": "alpha_s/(4*pi)", "H": 0, "C": 0,
            "K_generator": 1, "gamma_F": 1, "cusp": 1,
            "local_P": None, "local_beta": None},
        "b_variant": b_variant,
        "scale_variant": scale_variant,
        "window_GeV_inv": [0.0001, 8.0],
        "density_measure": "d2qT",
        "units": "GeV^-2",
        "targets": [asdict(target) for target in targets],
        "assembly": "independent canonical f*exp(S) on each signed leg; scalar flavor and quadrature sums",
    })
    return ReferenceWindow(targets, identity, tuple(groups),
                           tuple(group_for_target), tuple(weights))

