"""Immutable declarations and checked composition preconditions.

These declarations are not proofs of QCD.  In particular, a compatible pair of
contexts establishes agreement of declared inputs, not their physical validity.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
import math


class ContractError(ValueError):
    """A declared precondition is not satisfied."""


class ContextMismatchError(ContractError):
    pass


class InventoryMismatchError(ContextMismatchError):
    pass


class DomainCompatibilityError(ContextMismatchError):
    pass


class DomainViolationError(ContractError):
    pass


class EvolutionConsistencyError(ContractError):
    pass


def finite(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ContractError(f"{name} must be a real number, not a boolean")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ContractError(f"{name} must be a real number") from error
    if not math.isfinite(result) or (positive and result <= 0):
        qualifier = "positive and finite" if positive else "finite"
        raise ContractError(f"{name} must be {qualifier}; received {value!r}")
    return result


@dataclass(frozen=True)
class ScalePoint:
    mu_GeV: float
    zeta_GeV2: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "mu_GeV", finite(self.mu_GeV, "mu", positive=True))
        object.__setattr__(self, "zeta_GeV2", finite(self.zeta_GeV2, "zeta", positive=True))

    def coordinates(self, reference: ScalePoint) -> tuple[float, float]:
        return (
            math.log(self.mu_GeV) - math.log(reference.mu_GeV),
            0.5 * (math.log(self.zeta_GeV2) - math.log(reference.zeta_GeV2)),
        )


@dataclass(frozen=True)
class KinematicDomain:
    x_min: float = 0.0
    x_max: float = 1.0
    Q_min_GeV: float = 2.0
    Q_max_GeV: float = 100.0
    max_qT_over_Q: float = 0.2
    b_min_GeV_inv: float = 0.0
    b_max_GeV_inv: float | None = None

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if value is not None:
                object.__setattr__(self, item.name, finite(value, item.name))
        if not 0 <= self.x_min < self.x_max <= 1:
            raise ContractError("x-domain must satisfy 0 <= x_min < x_max <= 1")
        if not 0 < self.Q_min_GeV <= self.Q_max_GeV:
            raise ContractError("Q-domain must be positive and ordered")
        if not 0 < self.max_qT_over_Q <= 1:
            raise ContractError("max_qT_over_Q must lie in (0, 1]")
        if self.b_min_GeV_inv < 0:
            raise ContractError("b_min must be nonnegative")
        if self.b_max_GeV_inv is not None and self.b_max_GeV_inv <= self.b_min_GeV_inv:
            raise ContractError("finite b_max must exceed b_min")

    def validate_x_b(self, x: float, b: float) -> None:
        x, b = finite(x, "x"), finite(b, "b_T")
        if not (0 < x < 1 and self.x_min <= x <= self.x_max):
            raise DomainViolationError(f"x={x} lies outside the declared open partonic domain")
        if b < self.b_min_GeV_inv or (
            self.b_max_GeV_inv is not None and b > self.b_max_GeV_inv
        ):
            raise DomainViolationError(f"b_T={b} lies outside the declared domain")

    def validate_dy(self, point: DYKinematics) -> None:
        for x in (point.x_a, point.x_b):
            if not (0 < x < 1 and self.x_min <= x <= self.x_max):
                raise DomainViolationError(f"x={x} lies outside the declared domain")
        if not self.Q_min_GeV <= point.Q_GeV <= self.Q_max_GeV:
            raise DomainViolationError("Q lies outside the declared domain")
        if point.qT_GeV / point.Q_GeV > self.max_qT_over_Q:
            raise DomainViolationError("qT/Q exceeds the declared process domain")


@dataclass(frozen=True)
class DYKinematics:
    Q_GeV: float
    qT_GeV: float
    x_a: float
    x_b: float

    def __post_init__(self) -> None:
        for item in fields(self):
            object.__setattr__(self, item.name, finite(getattr(self, item.name), item.name))
        if self.Q_GeV <= 0 or self.qT_GeV < 0:
            raise ContractError("Q must be positive and qT nonnegative")
        if not (0 < self.x_a < 1 and 0 < self.x_b < 1):
            raise ContractError("Both momentum fractions must lie in (0, 1)")


@dataclass(frozen=True)
class DefinitionSpec:
    name: str = "synthetic-gaussian-v1"
    operator: str = "synthetic scalar fixture; no QCD operator asserted"
    uv_scheme: str = "not_applicable_synthetic"
    rapidity_scheme: str = "not_applicable_synthetic"
    soft_subtraction: str = "not_applicable_synthetic"
    wilson_line: str = "not_applicable_synthetic"


@dataclass(frozen=True)
class Conventions:
    fourier: str = "F(k)=integral[d2b/(2pi)^2] exp(+i k.b) F(b); F(b)=integral[d2k] exp(-i k.b) F(k)"
    scale_derivatives: str = "ln_mu,ln_sqrt_zeta"
    kernel: str = "dF/dln_sqrt_zeta=K*F"
    provider_quantity: str = "f"
    momentum_density_measure: str = "d2kT"
    units: str = "momenta_GeV; b_GeV_inverse; zeta_GeV_squared"


@dataclass(frozen=True)
class CoefficientOrders:
    """Highest powers of a_s retained; None means explicitly not applicable.

    The beta entry refers to da_s/dln(mu), whose leading power is normally a_s^2.
    No conversion from an NLL/NNLL label is inferred by this class.
    """

    H: int | None = None
    C: int | None = None
    K: int | None = None
    gamma: int | None = None
    cusp: int | None = None
    P: int | None = None
    beta: int | None = None

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"{item.name} order must be a nonnegative integer or None")


@dataclass(frozen=True)
class ExternalInput:
    """An external ingredient identity, never a locally retained coefficient."""

    provider_id: str
    dataset_id: str
    method: str
    fingerprint: str
    native_order_label: str
    order_meaning: str
    flavor_policy: str
    status: str = "external"

    def __post_init__(self) -> None:
        if self.status != "external" or any(
            not isinstance(getattr(self, item.name), str) or not getattr(self, item.name).strip()
            for item in fields(self)
        ):
            raise ContractError("External inputs require a complete external identity and order semantics")


@dataclass(frozen=True)
class AccuracySpec:
    mode: str = "synthetic_exact"
    label: str = "exact synthetic polynomial potential; no QCD perturbative order"
    expansion_parameter: str | None = None
    coefficients: CoefficientOrders = field(default_factory=CoefficientOrders)
    external_collinear: ExternalInput | None = None
    external_coupling: ExternalInput | None = None
    kernel_completion: str | None = None

    def __post_init__(self) -> None:
        values = [getattr(self.coefficients, item.name) for item in fields(self.coefficients)]
        if self.mode == "synthetic_exact":
            if (self.expansion_parameter is not None or any(value is not None for value in values)
                    or self.external_collinear or self.external_coupling or self.kernel_completion):
                raise ContractError("Synthetic-exact accuracy must not claim QCD coefficient orders")
        elif self.mode == "perturbative_manifest":
            if (not self.expansion_parameter or any(value is None for value in values)
                    or self.external_collinear or self.external_coupling):
                raise ContractError("A perturbative manifest requires an expansion and every order")
        elif self.mode == "external_inputs":
            if (self.expansion_parameter != "a_s=alpha_s/(4*pi)"
                    or values[:5] != [0, 0, 1, 1, 1] or values[5:] != [None, None]
                    or not isinstance(self.external_collinear, ExternalInput)
                    or not isinstance(self.external_coupling, ExternalInput)
                    or self.external_collinear.provider_id != self.external_coupling.provider_id
                    or self.kernel_completion != "RG_integral_of_one_loop_gamma_K_with_native_alpha_s"):
                raise ContractError("External-input QCD manifest requires the fixed local inventory, both external identities and RG completion")
        else:
            raise ContractError(f"Unsupported accuracy mode {self.mode!r}")


@dataclass(frozen=True)
class TMDContext:
    process: str = "dy_unpolarized_angular_integrated"
    hadron: str = "synthetic_hadron"
    definition: DefinitionSpec = field(default_factory=DefinitionSpec)
    conventions: Conventions = field(default_factory=Conventions)
    accuracy: AccuracySpec = field(default_factory=AccuracySpec)
    domain: KinematicDomain = field(default_factory=KinematicDomain)
    provider_id: str = "analytic-fixture-pdf-v1"


def require_compatible(left: TMDContext, right: TMDContext) -> None:
    if left.accuracy.coefficients != right.accuracy.coefficients:
        raise InventoryMismatchError("Perturbative coefficient inventories differ; conversion or refit is not implicit")
    if left.domain != right.domain:
        raise DomainCompatibilityError("Kinematic domains differ; an explicit restriction is required")
    different = [item.name for item in fields(left) if getattr(left, item.name) != getattr(right, item.name)]
    if different:
        raise ContextMismatchError("Incompatible declared context fields: " + ", ".join(different))


class EvidenceStatus(str, Enum):
    DECLARED_ASSUMPTION = "declared_assumption"
    TYPE_CHECKED = "type_checked"
    ANALYTICALLY_DERIVED = "analytically_derived"
    SYMBOLICALLY_CHECKED = "symbolically_checked"
    NUMERICALLY_VALIDATED = "numerically_validated"
    PROOF_ASSISTANT_VERIFIED = "proof_assistant_verified"


@dataclass(frozen=True)
class Evidence:
    """An evidence record, not a verifier; its status must match actual work."""

    statement: str
    status: EvidenceStatus
    assumptions: tuple[str, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvidenceStatus):
            raise ContractError("Evidence status must be an EvidenceStatus member")
        if isinstance(self.assumptions, str):
            raise ContractError("Evidence assumptions must be a sequence, not a string")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))


@dataclass(frozen=True)
class Provenance:
    source_id: str
    description: str
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if not self.source_id or any(not isinstance(item, Evidence) for item in self.evidence):
            raise ContractError("Provenance requires a source id and Evidence records")
