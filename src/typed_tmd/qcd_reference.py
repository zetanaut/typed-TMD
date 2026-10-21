"""Independent direct scalar H002 reference using composite two-point Gauss."""
from __future__ import annotations

import math

from scipy.special import j0

from .provider_replay import MissingQueryError, ReplayProvider, parse_hex
from .qcd_plan import profile_mu


class ReferenceMoments:
    """Own cumulative integration; never imports production evolution values."""

    def __init__(self, inputs: ReplayProvider, plan: dict, subdivision: int):
        self.inputs = inputs
        table = plan["scale_plans"]["R" + str(subdivision)]
        self.partial = table["partial"]
        self.cumulative = [(0.0, 0.0)]
        for segment in table["full"]:
            area = weighted = 0.0
            for sample in segment["nodes"]:
                mu, weight, log_mu = map(parse_hex, sample)
                c = (4.0 / 3.0) * inputs.alpha_s(mu) / math.pi
                area += weight * c
                weighted += weight * c * log_mu
            old_area, old_weighted = self.cumulative[-1]
            self.cumulative.append((old_area + area, old_weighted + weighted))
        self.values: dict[str, tuple[float, float]] = {}

    def moment(self, scale: float) -> tuple[float, float]:
        key = scale.hex()
        if key not in self.values:
            piece = self.partial.get(key)
            if piece is None:
                raise MissingQueryError("reference_endpoint_unplanned " + key)
            area, weighted = self.cumulative[piece["lower_knot_index"]]
            for sample in piece["nodes"]:
                mu, weight, log_mu = map(parse_hex, sample)
                c = (4.0 / 3.0) * self.inputs.alpha_s(mu) / math.pi
                area += weight * c
                weighted += weight * c * log_mu
            self.values[key] = (area, weighted)
        return self.values[key]


class QCDReference:
    def __init__(self, inputs: ReplayProvider, plan: dict, subdivision: int):
        self.inputs = inputs
        self.moments = ReferenceMoments(inputs, plan, subdivision)
        self._exponent_cache: dict[tuple[float, float], float] = {}
        self._luminosity_cache: dict[tuple, float] = {}

    def scalar_exponent(self, b: float, Q: float) -> float:
        key = (b, Q)
        if key in self._exponent_cache:
            return self._exponent_cache[key]
        mub = profile_mu(b)
        base0, base1 = self.moments.moment(mub)
        final0, final1 = self.moments.moment(Q)
        integral = (1.5 - 2 * math.log(Q)) * (final0 - base0) + 2 * (final1 - base1)
        value = -0.25 * b * b - 0.04 * b * b * math.log(Q / mub) + integral
        self._exponent_cache[key] = value
        return value

    def tmd(self, pid: int, x: float, b: float, Q: float) -> float:
        mub = profile_mu(b)
        amplitude = self.inputs.f(pid, x, mub)
        return amplitude * math.exp(self.scalar_exponent(b, Q))

    def luminosity(self, point: dict, b: float) -> float:
        Q, xa, xb = point["Q_GeV"], point["x_a"], point["x_b"]
        key = (Q, xa, xb, b)
        if key in self._luminosity_cache:
            return self._luminosity_cache[key]
        total = 0.0
        for positive, weight in ((1, 1 / 9), (2, 4 / 9), (3, 1 / 9)):
            a = self.tmd(positive, xa, b, Q)
            bbar = self.tmd(-positive, xb, b, Q)
            abar = self.tmd(-positive, xa, b, Q)
            bq = self.tmd(positive, xb, b, Q)
            total += weight * (a * bbar + abar * bq)
        self._luminosity_cache[key] = total
        return total

    def windowed_W(self, point: dict, nodes: list[list[str]]) -> float:
        total = 0.0
        for b_hex, weight_hex in nodes:
            b = parse_hex(b_hex)
            weight = parse_hex(weight_hex)
            total += weight * b * float(j0(point["qT_GeV"] * b)) * self.luminosity(point, b)
        return total / (2 * math.pi)
