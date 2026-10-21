"""An exact synthetic fixture, deliberately not a physical QCD extraction.

P = gamma0*u + gamma_K*u^2/2 - gamma_K*u*v - g2*b^2*v,
u=ln(mu/mu0), v=ln(sqrt(zeta)/mu0), U=exp(P_final-P_initial).

The boundary is f_fixture(x)*exp(-width*b^2). There are no QCD hard/matching
coefficients, perturbative running, DGLAP evolution, Wilson lines or data fits.
The DY-like example nevertheless exercises both legs, flavors, scale partition,
an explicit synthetic hard counterfactor, and a normalized Fourier transform.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction
import hashlib
import json
import math

from .algebra import EvolutionGenerators, Polynomial
from .contracts import (
    AccuracySpec, ContractError, Conventions, DefinitionSpec, DYKinematics,
    Evidence, EvidenceStatus, Provenance, ScalePoint, TMDContext, finite,
    require_compatible,
)
from .expressions import (
    BoundaryTMD, BoundaryTransport, DYExpression, DYTerm, EvolvedTMD,
    EvolutionMap, TMDExpression, TransportedBoundary,
)
from .numerics import QuadratureResult, gaussian_fourier_analytic, radial_fourier
from .providers import AnalyticFixturePDF, CollinearProvider


@dataclass(frozen=True)
class GaussianParameters:
    gamma_K: float = 0.24
    gamma0: float = 0.18
    width_GeV2: float = 0.25
    g2_GeV2: float = 0.04
    reference: ScalePoint = field(default_factory=lambda: ScalePoint(2.0, 4.0))

    def __post_init__(self) -> None:
        for name in ("gamma_K", "gamma0", "width_GeV2", "g2_GeV2"):
            object.__setattr__(self, name, finite(getattr(self, name), name))
        if self.gamma_K < 0 or self.g2_GeV2 < 0 or self.width_GeV2 <= 0:
            raise ContractError("The fixture requires positive boundary width and nonnegative gamma_K and g2")
        if not math.isclose(math.log(self.reference.zeta_GeV2), 2 * math.log(self.reference.mu_GeV), abs_tol=1e-12):
            raise ContractError("This fixture requires zeta_ref = mu_ref^2")


def _identifier(prefix: str, value: dict) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return prefix + ":" + hashlib.sha256(serialized.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class SyntheticGaussianModel:
    parameters: GaussianParameters = field(default_factory=GaussianParameters)
    provider: CollinearProvider = field(default_factory=AnalyticFixturePDF)
    context: TMDContext | None = None
    _potential: Polynomial = field(init=False, repr=False)
    _model_id: str = field(init=False, repr=False)
    _evolution_id: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.provider, CollinearProvider) or self.provider.quantity != "f":
            raise ContractError("A collinear provider returning f is required")
        context = self.context or TMDContext(provider_id=self.provider.identifier)
        if context.definition != DefinitionSpec() or context.accuracy != AccuracySpec():
            raise ContractError("The synthetic evaluator cannot execute a QCD definition or perturbative manifest")
        if context.conventions != Conventions() or context.process != "dy_unpolarized_angular_integrated":
            raise ContractError("The synthetic evaluator only implements its explicitly declared conventions and process")
        if context.provider_id != self.provider.identifier:
            raise ContractError("Provider identifier does not match the immutable context")
        object.__setattr__(self, "context", context)
        p = self.parameters
        potential = Polynomial.from_terms((
            (p.gamma0, (1, 0, 0)),
            (Fraction(str(p.gamma_K)) / 2, (2, 0, 0)),
            (-Fraction(str(p.gamma_K)), (1, 1, 0)),
            (-Fraction(str(p.g2_GeV2)), (0, 1, 2)),
        ))
        EvolutionGenerators.from_potential(potential).require_exact_flatness()
        object.__setattr__(self, "_potential", potential)
        record = asdict(p)
        object.__setattr__(self, "_model_id", _identifier("synthetic-model", record))
        del record["width_GeV2"]
        object.__setattr__(self, "_evolution_id", _identifier("synthetic-evolution", record))

    @property
    def potential(self) -> Polynomial:
        return self._potential

    @property
    def generators(self) -> EvolutionGenerators:
        return EvolutionGenerators.from_potential(self.potential)

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def evolution_id(self) -> str:
        return self._evolution_id

    @property
    def hard_factor_id(self) -> str:
        return "synthetic-hard:" + self.evolution_id

    def reference(self, flavor: int, boundary_id: str = "A") -> BoundaryTMD:
        return BoundaryTMD(
            self.context, flavor, self.parameters.reference, self.model_id,
            self.evolution_id, boundary_id,
            Provenance("synthetic-gaussian-boundary-v1", "Specified Gaussian boundary, not an extracted QCD TMD",
                       (Evidence("Analytic fixture boundary and collinear input", EvidenceStatus.DECLARED_ASSUMPTION,
                                 source="docs/PHYSICS_SPEC.md"),)),
        )

    def evolution(self, source: ScalePoint, target: ScalePoint) -> EvolutionMap:
        return EvolutionMap(
            self.context, source, target, self.evolution_id,
            Provenance("synthetic-potential-transport-v1", "exp(P(target)-P(source))",
                       (Evidence("Polynomial mixed derivatives commute exactly", EvidenceStatus.SYMBOLICALLY_CHECKED,
                                 ("Finite rational polynomial grammar in u,v,b",)),
                        Evidence("Exponential endpoint differences compose", EvidenceStatus.ANALYTICALLY_DERIVED,
                                 ("The same potential and boundary model are used",), "docs/PHYSICS_SPEC.md"))),
        )

    def boundary_transport(self, target: ScalePoint, source_boundary_id: str = "A",
                           target_boundary_id: str = "B") -> BoundaryTransport:
        return BoundaryTransport(self.evolution(self.parameters.reference, target), source_boundary_id, target_boundary_id)

    def potential_value(self, scale: ScalePoint, b: float) -> float:
        b = finite(b, "b_T")
        if b < 0:
            raise ContractError("b_T must be nonnegative")
        u, v = scale.coordinates(self.parameters.reference)
        return self.potential.evaluate(u=u, v=v, b=b)

    def evolution_factor(self, source: ScalePoint, target: ScalePoint, b: float) -> float:
        return math.exp(self.potential_value(target, b) - self.potential_value(source, b))

    def effective_width(self, scale: ScalePoint) -> float:
        _, v = scale.coordinates(self.parameters.reference)
        width = self.parameters.width_GeV2 + self.parameters.g2_GeV2 * v
        if width <= 0:
            raise ContractError("This Gaussian fixture is not integrable at the requested rapidity scale")
        return width

    def evaluate(self, expression: TMDExpression, x: float, b: float) -> float:
        self._validate_tmd(expression)
        self.context.domain.validate_x_b(x, b)
        return self._evaluate_value(expression, x, b)

    def _validate_tmd(self, expression: TMDExpression) -> None:
        """Shared input validation; analytic and numerical values remain independent."""
        if not isinstance(expression, (BoundaryTMD, EvolvedTMD, TransportedBoundary)):
            raise ContractError("Unsupported symbolic TMD node")
        require_compatible(self.context, expression.context)
        if expression.model_id != self.model_id or expression.evolution_id != self.evolution_id:
            raise ContractError("Expression belongs to a different model or evolution field")
        self.effective_width(expression.scale)
        if isinstance(expression, BoundaryTMD):
            if expression.scale != self.parameters.reference:
                raise ContractError("A different boundary scale requires an explicit boundary transport")
        else:
            self._validate_tmd(expression.operand)

    def _evaluate_value(self, expression: TMDExpression, x: float, b: float) -> float:
        if isinstance(expression, BoundaryTMD):
            return self.provider.f(expression.flavor, x, self.parameters.reference.mu_GeV) * math.exp(-self.parameters.width_GeV2 * b * b)
        if isinstance(expression, TransportedBoundary):
            transport = expression.boundary_transport.evolution
        elif isinstance(expression, EvolvedTMD):
            transport = expression.transport
        else:
            raise ContractError("Unsupported symbolic TMD node")
        return self._evaluate_value(expression.operand, x, b) * self.evolution_factor(transport.source, transport.target, b)

    def hard_factor(self, Q_GeV: float, mu_GeV: float) -> float:
        """Synthetic counterfactor; unity at mu=Q, not a QCD hard coefficient."""
        Q, mu = finite(Q_GeV, "Q", positive=True), finite(mu_GeV, "mu", positive=True)
        d = math.log(mu) - math.log(Q)
        return math.exp(-2 * self.parameters.gamma0 * d - self.parameters.gamma_K * d * d)

    def dy_expression(
        self, kinematics: DYKinematics, *,
        flavors: tuple[tuple[int, float], ...] = ((1, -1 / 3), (2, 2 / 3)),
        mu_GeV: float | None = None, zeta_a_GeV2: float | None = None,
        via_boundary: ScalePoint | None = None,
    ) -> DYExpression:
        self.context.domain.validate_dy(kinematics)
        Q = kinematics.Q_GeV
        mu = Q if mu_GeV is None else mu_GeV
        zeta_a = Q * Q if zeta_a_GeV2 is None else finite(zeta_a_GeV2, "zeta_A", positive=True)
        scales = (ScalePoint(mu, zeta_a), ScalePoint(mu, math.exp(4 * math.log(Q) - math.log(zeta_a))))
        flavors = tuple(flavors)
        if not flavors or len({pid for pid, _ in flavors}) != len(flavors):
            raise ContractError("Flavor manifest must be nonempty and have unique quark ids")

        def leg(pid: int, target: ScalePoint) -> TMDExpression:
            boundary = self.reference(pid)
            if via_boundary is not None:
                boundary = self.boundary_transport(via_boundary).apply(boundary)
            return self.evolution(boundary.scale, target).apply(boundary)

        terms = []
        for pid, charge in flavors:
            if type(pid) is not int or not 1 <= pid <= 6:
                raise ContractError("Flavor manifest uses positive quark ids 1 through 6")
            # Both q_A * qbar_B and qbar_A * q_B are necessary.
            for left, right in ((pid, -pid), (-pid, pid)):
                terms.append(DYTerm(leg(left, scales[0]), leg(right, scales[1]), charge, Q))
        return DYExpression(
            tuple(terms), kinematics, self.hard_factor_id,
            Provenance("synthetic-dy-W-v1", "Synthetic angular-independent W density per d2qT; not a QCD cross section"),
        )

    def _check_dy(self, expression: DYExpression) -> None:
        require_compatible(self.context, expression.context)
        self.context.domain.validate_dy(expression.kinematics)
        if expression.hard_factor_id != self.hard_factor_id:
            raise ContractError("Unsupported hard factor in the synthetic evaluator")
        for term in expression.terms:
            self._validate_tmd(term.left)
            self._validate_tmd(term.right)

    def dy_b_space(self, expression: DYExpression, b: float) -> float:
        self._check_dy(expression)
        k = expression.kinematics
        hard = self.hard_factor(k.Q_GeV, expression.terms[0].left.scale.mu_GeV)
        return hard * math.fsum(term.charge ** 2 * self.evaluate(term.left, k.x_a, b)
                               * self.evaluate(term.right, k.x_b, b) for term in expression.terms)

    def dy_gaussian_parameters(self, expression: DYExpression) -> tuple[float, float]:
        """Independent closed-form amplitude/width; does not traverse the transport AST."""
        self._check_dy(expression)
        k, p = expression.kinematics, self.parameters
        luminosity = math.fsum(term.charge ** 2 * self.provider.f(term.left.flavor, k.x_a, p.reference.mu_GeV)
                              * self.provider.f(term.right.flavor, k.x_b, p.reference.mu_GeV)
                              for term in expression.terms)
        L = math.log(k.Q_GeV) - math.log(p.reference.mu_GeV)
        amplitude = luminosity * math.exp(2 * p.gamma0 * L - p.gamma_K * L * L)
        width = 2 * (p.width_GeV2 + p.g2_GeV2 * L)
        if width <= 0:
            raise ContractError("The DY Gaussian is not integrable at this Q")
        return amplitude, width

    def dy_analytic(self, expression: DYExpression) -> float:
        amplitude, width = self.dy_gaussian_parameters(expression)
        return gaussian_fourier_analytic(amplitude, width, expression.kinematics.qT_GeV)

    def dy_numerical(self, expression: DYExpression, *, abs_tol: float = 1e-8,
                     rel_tol: float = 1e-6, backend: str = "auto") -> QuadratureResult:
        amplitude, width = self.dy_gaussian_parameters(expression)
        domain = self.context.domain
        if domain.b_min_GeV_inv != 0 or domain.b_max_GeV_inv is not None:
            raise ContractError("An infinite Fourier transform requires the fixture's full b>=0 domain")
        return radial_fourier(lambda b: self.dy_b_space(expression, b), expression.kinematics.qT_GeV,
                              bound_amplitude=abs(amplitude), bound_width_GeV2=width,
                              abs_tol=abs_tol, rel_tol=rel_tol, backend=backend)
