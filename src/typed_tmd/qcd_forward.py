"""Typed H002 one-loop-generator/tree-matching forward construction."""
from __future__ import annotations

import math

from scipy.special import j0

from .contracts import (AccuracySpec, CoefficientOrders, Conventions, ContractError,
                        DefinitionSpec, Evidence, EvidenceStatus,
                        ExternalInput, KinematicDomain, Provenance, ScalePoint, TMDContext)
from .contracts import require_compatible
from .expressions import (BoundaryTMD, BoundaryTransport, EvolvedTMD, EvolutionMap,
                          TransportedBoundary)
from .provider_replay import ReplayProvider, parse_hex
from .qcd_plan import profile_mu

A = ScalePoint(5.0, 25.0)
B = ScalePoint(10.0, 100.0)
CF = 4.0 / 3.0
MODEL_ID = "h002-ct18-light-uds-a0.25-g20.04-bmax0.5"
EVOLUTION_ID = "h002-one-loop-generators-RG-completed-K-v1"


class ProductionMoments:
    """Production Gauss-Legendre moments with separate complete knot panels."""

    def __init__(self, provider: ReplayProvider, plan: dict, variant: str):
        if variant not in ("P16", "P32"):
            raise ValueError("production scale variant required")
        self.provider = provider
        self.table = plan["scale_plans"][variant]
        self.knots = [parse_hex(x) for x in plan["alpha_knots_hex"]]
        self.cumulative = [(0.0, 0.0)]
        for panel in self.table["full"]:
            v0 = v1 = 0.0
            for mu_h, weight_h, t_h in panel["nodes"]:
                c = CF * provider.alpha_s(parse_hex(mu_h)) / math.pi
                w = parse_hex(weight_h)
                v0 += w * c
                v1 += w * c * parse_hex(t_h)
            a, b = self.cumulative[-1]
            self.cumulative.append((a + v0, b + v1))
        self.cache: dict[str, tuple[float, float]] = {}

    def at(self, mu: float) -> tuple[float, float]:
        key = mu.hex()
        if key not in self.cache:
            part = self.table["partial"].get(key)
            if part is None:
                raise ContractError("Unplanned production scale endpoint")
            v0, v1 = self.cumulative[part["lower_knot_index"]]
            for mu_h, weight_h, t_h in part["nodes"]:
                c = CF * self.provider.alpha_s(parse_hex(mu_h)) / math.pi
                w = parse_hex(weight_h)
                v0 += w * c
                v1 += w * c * parse_hex(t_h)
            self.cache[key] = (v0, v1)
        return self.cache[key]

    def between(self, lower: float, upper: float) -> tuple[float, float]:
        l0, l1 = self.at(lower)
        u0, u1 = self.at(upper)
        return u0 - l0, u1 - l1


class QCDProduction:
    def __init__(self, provider: ReplayProvider, plan: dict, scale_variant: str):
        self.provider = provider
        self.plan = plan
        self.moments = ProductionMoments(provider, plan, scale_variant)
        self.context = self.make_context(provider)
        self.lookup_count = 0
        self._transport_cache: dict[tuple, float] = {}
        self._luminosity_cache: dict[tuple, float] = {}

    @staticmethod
    def make_context(provider: ReplayProvider) -> TMDContext:
        ip = provider.inspection["payload"]
        files = ip["files"]
        external_pdf = ExternalInput(
            provider_id=provider.identifier, dataset_id="CT18NNLO/0",
            method="native xfxQ divided once by x; exact finite replay",
            fingerprint=files["set_info"]["sha256"] + ":" + files["member_data"]["sha256"],
            native_order_label="OrderQCD=2", order_meaning="NNLO native PDF; local P not implemented",
            flavor_policy="native variable flavor, maximum five; light u,d,s current")
        external_alpha = ExternalInput(
            provider_id=provider.identifier, dataset_id="CT18NNLO/0",
            method="native pdf.alphasQ; exact finite replay",
            fingerprint=ip["alpha_table_sha256"], native_order_label="AlphaS_OrderQCD=2",
            order_meaning="native coupling metadata; local beta not implemented",
            flavor_policy="native variable flavor; inherited NumFlavors=5")
        accuracy = AccuracySpec(
            mode="external_inputs", label="one-loop-generator/tree-matching diagnostic",
            expansion_parameter="a_s=alpha_s/(4*pi)",
            coefficients=CoefficientOrders(H=0, C=0, K=1, gamma=1, cusp=1, P=None, beta=None),
            external_collinear=external_pdf, external_coupling=external_alpha,
            kernel_completion="RG_integral_of_one_loop_gamma_K_with_native_alpha_s")
        return TMDContext(
            process="dy_unpolarized_angular_integrated", hadron="proton",
            definition=DefinitionSpec(name="Collins-soft-subtracted-unpolarized-DY-v1",
                                      operator="unpolarized quark TMD", uv_scheme="MSbar",
                                      rapidity_scheme="Collins", soft_subtraction="soft-subtracted",
                                      wilson_line="past-pointing DY staple"),
            conventions=Conventions(provider_quantity="f", momentum_density_measure="d2qT"),
            accuracy=accuracy,
            domain=KinematicDomain(x_min=parse_hex(ip["bounds"]["x_min"]),
                                   x_max=parse_hex(ip["bounds"]["x_max"]),
                                   Q_min_GeV=20, Q_max_GeV=40, max_qT_over_Q=0.1,
                                   b_min_GeV_inv=0.000025, b_max_GeV_inv=12),
            provider_id=provider.identifier + ":snapshot:" + provider.snapshot_id)

    def gamma_integral(self, mu_i: float, mu_f: float, zeta: float) -> float:
        i0, i1 = self.moments.between(mu_i, mu_f)
        return (1.5 - math.log(zeta)) * i0 + 2 * i1

    def kernel(self, b: float, mu: float) -> float:
        i0, _ = self.moments.between(profile_mu(b), mu)
        return -0.04 * b * b - 2 * i0

    def log_transport(self, b: float, source: ScalePoint, target: ScalePoint, path: str = "rapidity_first") -> float:
        if path not in ("rapidity_first", "mu_first"):
            raise ContractError("Unknown evolution path")
        key = (b, source, target, path)
        if key in self._transport_cache:
            return self._transport_cache[key]
        dv = 0.5 * math.log(target.zeta_GeV2 / source.zeta_GeV2)
        if path == "rapidity_first":
            value = self.kernel(b, source.mu_GeV) * dv + self.gamma_integral(
                source.mu_GeV, target.mu_GeV, target.zeta_GeV2)
        else:
            value = self.gamma_integral(source.mu_GeV, target.mu_GeV, source.zeta_GeV2) + self.kernel(b, target.mu_GeV) * dv
        self._transport_cache[key] = value
        return value

    def _map(self, source: ScalePoint, target: ScalePoint, tag: str) -> EvolutionMap:
        return EvolutionMap(self.context, source, target, EVOLUTION_ID,
                            Provenance(tag, "RG-completed one-loop generator transport",
                                       (Evidence("Declared compatible connection", EvidenceStatus.DECLARED_ASSUMPTION),)))

    def target_expressions(self, b: float, pid: int, Q: float, zeta: float | None = None):
        mub = profile_mu(b)
        sb = ScalePoint(mub, mub * mub)
        boundary = BoundaryTMD(self.context, pid, sb, MODEL_ID, EVOLUTION_ID,
                               "canonical-b-dependent-input",
                               Provenance("canonical-matching", "f(x,mu_b) exp(-a b^2)"))
        a = BoundaryTransport(self._map(sb, A, "matching-to-A"),
                              "canonical-b-dependent-input", "transported-A").apply(boundary)
        b_boundary = BoundaryTransport(self._map(A, B, "A-to-B"),
                                       "transported-A", "transported-B").apply(a)
        target = ScalePoint(Q, Q * Q if zeta is None else zeta)
        return self._map(A, target, "A-to-target").apply(a), self._map(B, target, "B-to-target").apply(b_boundary), b_boundary

    def evaluate(self, expression, x: float, b: float) -> float:
        if not isinstance(expression, (BoundaryTMD, TransportedBoundary, EvolvedTMD)):
            raise ContractError("Unsupported QCD expression")
        require_compatible(self.context, expression.context)
        if expression.model_id != MODEL_ID or expression.evolution_id != EVOLUTION_ID:
            raise ContractError("Unsupported QCD model or evolution identity")
        if isinstance(expression, BoundaryTMD):
            if expression.boundary_id != "canonical-b-dependent-input":
                raise ContractError("Unsupported QCD matching boundary")
            self.lookup_count += 1
            return self.provider.f(expression.flavor, x, expression.scale.mu_GeV) * math.exp(-0.25 * b * b)
        if isinstance(expression, TransportedBoundary):
            return self.evaluate(expression.operand, x, b) * math.exp(
                self.log_transport(b, expression.boundary_transport.evolution.source,
                                   expression.boundary_transport.evolution.target))
        if isinstance(expression, EvolvedTMD):
            return self.evaluate(expression.operand, x, b) * math.exp(
                self.log_transport(b, expression.transport.source, expression.transport.target))
        raise ContractError("Unsupported QCD expression")

    def tmd(self, pid: int, x: float, b: float, Q: float, route: str = "A", zeta: float | None = None) -> float:
        self.context.domain.validate_x_b(x, b)
        if route not in ("A", "B"):
            raise ContractError("Unknown QCD presentation route")
        if Q not in (20.0, 40.0):
            raise ContractError("Q outside frozen H002 grid")
        a, b_route, _ = self.target_expressions(b, pid, Q, zeta)
        return self.evaluate(a if route == "A" else b_route, x, b)

    def luminosity(self, point: dict, b: float) -> float:
        Q, xa, xb = point["Q_GeV"], point["x_a"], point["x_b"]
        key = (Q, xa, xb, b)
        if key in self._luminosity_cache:
            return self._luminosity_cache[key]
        result = 0.0
        for pid, charge_sq in ((1, 1.0 / 9), (2, 4.0 / 9), (3, 1.0 / 9)):
            result += charge_sq * (self.tmd(pid, xa, b, Q) * self.tmd(-pid, xb, b, Q)
                                   + self.tmd(-pid, xa, b, Q) * self.tmd(pid, xb, b, Q))
        self._luminosity_cache[key] = result
        return result

    def windowed_W(self, point: dict, nodes: list[list[str]]) -> float:
        qT = point["qT_GeV"]
        total = 0.0
        for b_h, w_h in nodes:
            b = parse_hex(b_h)
            total += parse_hex(w_h) * b * float(j0(b * qT)) * self.luminosity(point, b)
        return total / (2 * math.pi)
