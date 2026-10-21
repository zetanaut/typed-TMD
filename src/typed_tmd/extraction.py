"""Finite-window H003 two-parameter response and analytic sensitivities."""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.special import j0

from .contracts import ContractError
from .provider_replay import ReplayProvider, parse_hex
from .qcd_forward import ProductionMoments
from .qcd_reference import ReferenceMoments
from .qcd_plan import profile_mu


LOG2 = math.log(2.0)
LOWER = np.array([0.1, 0.0])
WIDTH = np.array([0.4, 0.1])


@dataclass(frozen=True)
class ModelTemplate:
    coefficient_id: str
    lam: float

    def __post_init__(self):
        if self.coefficient_id not in {"approved", "noncusp-coefficient-lambda-0p8"}:
            raise ContractError("unknown_coefficient_identity")
        expected = 1.0 if self.coefficient_id == "approved" else 0.8
        if self.lam != expected:
            raise ContractError("coefficient_identity_mismatch")

    def compatible_with(self, other: "ModelTemplate") -> None:
        if self != other:
            raise ContractError("coefficient_identity_mismatch")


APPROVED = ModelTemplate("approved", 1.0)
CONTROL = ModelTemplate("noncusp-coefficient-lambda-0p8", 0.8)


@dataclass(frozen=True)
class Chart:
    name: str

    def canonical(self, coordinates) -> np.ndarray:
        value = np.asarray(coordinates, dtype=float)
        if value.shape != (2,) or not np.all(np.isfinite(value)):
            raise ContractError("invalid_parameter_vector")
        if self.name == "A":
            theta = value
        elif self.name == "B":
            theta = np.array([value[0] - LOG2 * value[1], value[1]])
        else:
            raise ContractError("unknown_parameter_chart")
        if np.any(theta < LOWER - 1e-14) or np.any(theta > LOWER + WIDTH + 1e-14):
            raise ContractError("parameter_outside_mapped_domain")
        return theta

    def coordinates(self, theta) -> np.ndarray:
        theta = Chart("A").canonical(theta)
        if self.name == "A":
            return theta.copy()
        if self.name == "B":
            return np.array([theta[0] + LOG2 * theta[1], theta[1]])
        raise ContractError("unknown_parameter_chart")

    def jacobian_to_canonical(self) -> np.ndarray:
        if self.name == "A":
            return np.eye(2)
        if self.name == "B":
            return np.array([[1.0, -LOG2], [0.0, 1.0]])
        raise ContractError("unknown_parameter_chart")


@dataclass(frozen=True)
class ObservationTarget:
    Q_GeV: float
    qT_GeV: float
    x_a: float
    x_b: float
    window: tuple[float, float] = (0.0001, 8.0)
    measure: str = "d2qT"
    units: str = "GeV^-2"

    def __post_init__(self):
        if (self.Q_GeV not in (20.0, 30.0, 40.0) or
            not 0 < self.qT_GeV / self.Q_GeV <= 0.1 or
            self.window != (0.0001, 8.0) or self.measure != "d2qT" or
            self.units != "GeV^-2"):
            raise ContractError("unsupported_observation_target")


@dataclass
class CompiledWindow:
    """Signed native luminosity and quadrature, independent of fit parameters."""
    targets: tuple[ObservationTarget, ...]
    b: np.ndarray
    weights: np.ndarray
    base: np.ndarray
    b2: np.ndarray
    log_q_over_mu: np.ndarray
    i0: np.ndarray

    def response(self, coordinates, chart: Chart, model: ModelTemplate):
        a, g2 = chart.canonical(coordinates)
        # The B route explicitly keeps its full transported boundary. The
        # beta chart is inverted at every call, including the g2 transport.
        if chart.name == "B":
            beta = float(coordinates[0])
            log_b_over_mu = self.log_q_over_mu - np.log(
                np.array([t.Q_GeV for t in self.targets])[:, None] / 10.0)
            boundary_b = -beta * self.b2 + g2 * LOG2 * self.b2 - g2 * self.b2 * log_b_over_mu
            transport_b_target = -g2 * self.b2 * (self.log_q_over_mu - log_b_over_mu)
            exponent = 2 * (boundary_b + transport_b_target)
        else:
            exponent = -2 * a * self.b2 - 2 * g2 * self.b2 * self.log_q_over_mu
        exponent = exponent + 3 * (model.lam - 1.0) * self.i0
        term = self.base * np.exp(exponent)
        values = np.sum(self.weights * term, axis=1)
        ja = np.sum(self.weights * term * (-2 * self.b2), axis=1)
        jg = np.sum(self.weights * term * (-2 * self.b2 * self.log_q_over_mu), axis=1)
        jl = np.sum(self.weights * term * (3 * self.i0), axis=1)
        canonical_jac = np.column_stack([ja, jg])
        return values, canonical_jac @ chart.jacobian_to_canonical(), jl


def compile_window(provider: ReplayProvider, plan: dict, *, b_variant: str,
                   scale_variant: str, Q_values=(20.0, 40.0)) -> CompiledWindow:
    if b_variant not in ("P16", "P32", "R16", "R32", "R64"):
        raise ContractError("unknown_b_resolution")
    if b_variant.startswith("P") != scale_variant.startswith("P"):
        raise ContractError("mixed_quadrature_routes")
    moments = (ProductionMoments(provider, plan, scale_variant) if b_variant.startswith("P")
               else ReferenceMoments(provider, plan, int(scale_variant[1:])))
    nodes = plan["b_plans"]["nominal"]["variants"][b_variant]
    b = np.array([parse_hex(row[0]) for row in nodes])
    w = np.array([parse_hex(row[1]) for row in nodes])
    b2 = np.broadcast_to(b * b, (3 * len(Q_values), len(b)))
    targets, base, weights, logs, i0s = [], [], [], [], []
    points = [{key: parse_hex(value) for key, value in p.items()} for p in plan["points"]]
    for p in points:
        Q = p["Q_GeV"]
        if Q not in Q_values:
            continue
        target = ObservationTarget(Q, p["qT_GeV"], p["x_a"], p["x_b"])
        targets.append(target)
        # No absolute values or clipping: signed native PDF products survive.
        lum = []
        for bi in b:
            mu = profile_mu(float(bi))
            total = 0.0
            for pid, charge in ((1, 1/9), (2, 4/9), (3, 1/9)):
                total += charge * (
                    provider.f(pid, p["x_a"], mu) * provider.f(-pid, p["x_b"], mu) +
                    provider.f(-pid, p["x_a"], mu) * provider.f(pid, p["x_b"], mu))
            lum.append(total)
        integral, integral0, logrow = [], [], []
        for bi in b:
            mu = profile_mu(float(bi))
            if b_variant.startswith("P"):
                d0, d1 = moments.between(mu, Q)
            else:
                lo0, lo1 = moments.moment(mu)
                hi0, hi1 = moments.moment(Q)
                d0, d1 = hi0 - lo0, hi1 - lo1
            integral.append((1.5 - 2 * math.log(Q)) * d0 + 2 * d1)
            integral0.append(d0)
            logrow.append(math.log(Q / mu))
        base.append(np.asarray(lum) * np.exp(2 * np.asarray(integral)))
        weights.append(w * b * j0(b * p["qT_GeV"]) / (2 * math.pi))
        logs.append(logrow)
        i0s.append(integral0)
    if len(targets) != 3 * len(Q_values):
        raise ContractError("incomplete_observation_grid")
    return CompiledWindow(tuple(targets), b, np.asarray(weights), np.asarray(base),
                          b2, np.asarray(logs), np.asarray(i0s))
