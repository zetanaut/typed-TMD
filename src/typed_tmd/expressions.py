"""Typed symbolic constructors for reference objects, transport and DY sums.

The constructors reject incompatible declared operands. Their output is an
expression tree interpreted by a separate evaluator; no implicit scheme change,
truncation change or replacement of a transported model family is performed.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TypeAlias

from .contracts import (
    ContractError, DYKinematics, Evidence, EvidenceStatus, Provenance,
    ScalePoint, TMDContext, finite, require_compatible,
)


@dataclass(frozen=True)
class BoundaryTMD:
    context: TMDContext
    flavor: int
    scale: ScalePoint
    model_id: str
    evolution_id: str
    boundary_id: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if type(self.flavor) is not int or not 1 <= abs(self.flavor) <= 6:
            raise ContractError("This core's quark sector requires signed flavor ids +/-1 through +/-6")
        if not self.model_id or not self.evolution_id or not self.boundary_id:
            raise ContractError("Boundary expressions require explicit model, evolution and boundary ids")


@dataclass(frozen=True)
class EvolutionMap:
    context: TMDContext
    source: ScalePoint
    target: ScalePoint
    evolution_id: str
    provenance: Provenance
    components: tuple[EvolutionMap, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", tuple(self.components))
        if not self.evolution_id:
            raise ContractError("An evolution map requires an evolution identifier")
        if self.components:
            endpoint = self.source
            for component in self.components:
                if not isinstance(component, EvolutionMap):
                    raise ContractError("Composition history must contain EvolutionMap objects")
                require_compatible(self.context, component.context)
                if component.evolution_id != self.evolution_id or component.source != endpoint:
                    raise ContractError("Composition history has incompatible generators or endpoints")
                endpoint = component.target
            if endpoint != self.target:
                raise ContractError("Composition history does not reach the declared target")

    def check_operand(self, operand: TMDExpression) -> None:
        if not isinstance(operand, (BoundaryTMD, EvolvedTMD, TransportedBoundary)):
            raise ContractError("Evolution requires a typed TMD expression")
        require_compatible(self.context, operand.context)
        if self.source != operand.scale:
            raise ContractError(f"Transport source {self.source} does not match operand scale {operand.scale}")
        if self.evolution_id != operand.evolution_id:
            raise ContractError("Evolution identifiers differ; no kernel conversion is implied")

    def apply(self, operand: TMDExpression) -> EvolvedTMD:
        return EvolvedTMD(operand, self)

    def compose(self, before: EvolutionMap) -> EvolutionMap:
        """Return self after before; this certifies only declared composability."""
        require_compatible(self.context, before.context)
        if before.target != self.source:
            raise ContractError("Evolution composition requires before.target == self.source")
        if self.evolution_id != before.evolution_id:
            raise ContractError("Cannot compose different declared evolution fields")
        return EvolutionMap(
            self.context, before.source, self.target, self.evolution_id,
            Provenance(
                f"compose({self.provenance.source_id},{before.provenance.source_id})",
                "Endpoint map in the same declared evolution field; ordered components retain construction history",
                (Evidence("Declared source/target and context composition", EvidenceStatus.TYPE_CHECKED,
                          ("The identified evolution field implements the required composition law",)),),
            ),
            (before, self),
        )


@dataclass(frozen=True)
class EvolvedTMD:
    operand: TMDExpression
    transport: EvolutionMap

    def __post_init__(self) -> None:
        self.transport.check_operand(self.operand)

    @property
    def context(self) -> TMDContext:
        return self.operand.context

    @property
    def flavor(self) -> int:
        return self.operand.flavor

    @property
    def scale(self) -> ScalePoint:
        return self.transport.target

    @property
    def model_id(self) -> str:
        return self.operand.model_id

    @property
    def evolution_id(self) -> str:
        return self.operand.evolution_id


@dataclass(frozen=True)
class BoundaryTransport:
    evolution: EvolutionMap
    source_boundary_id: str
    target_boundary_id: str

    def __post_init__(self) -> None:
        if not self.source_boundary_id or not self.target_boundary_id:
            raise ContractError("Boundary transport requires source and target labels")

    def apply(self, boundary: BoundaryTMD | TransportedBoundary) -> TransportedBoundary:
        return TransportedBoundary(boundary, self)


@dataclass(frozen=True)
class TransportedBoundary:
    operand: BoundaryTMD | TransportedBoundary
    boundary_transport: BoundaryTransport

    def __post_init__(self) -> None:
        if not isinstance(self.operand, (BoundaryTMD, TransportedBoundary)):
            raise ContractError("Rebasing requires an explicitly declared boundary object")
        if self.operand.boundary_id != self.boundary_transport.source_boundary_id:
            raise ContractError("Boundary label does not match the declared transport source")
        self.boundary_transport.evolution.check_operand(self.operand)

    @property
    def context(self) -> TMDContext:
        return self.operand.context

    @property
    def flavor(self) -> int:
        return self.operand.flavor

    @property
    def scale(self) -> ScalePoint:
        return self.boundary_transport.evolution.target

    @property
    def model_id(self) -> str:
        return self.operand.model_id

    @property
    def evolution_id(self) -> str:
        return self.operand.evolution_id

    @property
    def boundary_id(self) -> str:
        return self.boundary_transport.target_boundary_id


TMDExpression: TypeAlias = BoundaryTMD | EvolvedTMD | TransportedBoundary


@dataclass(frozen=True)
class DYTerm:
    left: TMDExpression
    right: TMDExpression
    charge: float
    Q_GeV: float

    def __post_init__(self) -> None:
        require_compatible(self.left.context, self.right.context)
        if self.left.context.process != "dy_unpolarized_angular_integrated":
            raise ContractError("A DY term requires the admitted DY process context")
        if self.left.flavor != -self.right.flavor:
            raise ContractError("A quark DY term requires a same-flavor quark/antiquark pair")
        if self.left.scale.mu_GeV != self.right.scale.mu_GeV:
            raise ContractError("The two DY factors must share the declared UV scale")
        charge, Q = finite(self.charge, "charge"), finite(self.Q_GeV, "Q", positive=True)
        object.__setattr__(self, "charge", charge)
        object.__setattr__(self, "Q_GeV", Q)
        log_product = math.log(self.left.scale.zeta_GeV2) + math.log(self.right.scale.zeta_GeV2)
        if not math.isclose(log_product, 4 * math.log(Q), rel_tol=0, abs_tol=1e-12):
            raise ContractError("DY scales must satisfy zeta_A*zeta_B = Q^4")


@dataclass(frozen=True)
class DYExpression:
    terms: tuple[DYTerm, ...]
    kinematics: DYKinematics
    hard_factor_id: str
    provenance: Provenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "terms", tuple(self.terms))
        if not self.terms or any(not isinstance(term, DYTerm) for term in self.terms):
            raise ContractError("A DY expression needs at least one typed DY term")
        first = self.terms[0]
        first.left.context.domain.validate_dy(self.kinematics)
        if not self.hard_factor_id:
            raise ContractError("The hard factor must be explicitly identified")
        for term in self.terms:
            require_compatible(first.left.context, term.left.context)
            if term.Q_GeV != self.kinematics.Q_GeV:
                raise ContractError("DY terms and observable have different hard scales")
            if term.left.scale.mu_GeV != first.left.scale.mu_GeV:
                raise ContractError("All DY terms must share a UV scale")

    @property
    def context(self) -> TMDContext:
        return self.terms[0].left.context


def describe_expression(expression: TMDExpression) -> dict:
    """Return a small serializable AST, retaining model and transport identities."""
    result = {
        "node": type(expression).__name__, "flavor": expression.flavor,
        "mu_GeV": expression.scale.mu_GeV, "zeta_GeV2": expression.scale.zeta_GeV2,
        "model_id": expression.model_id, "evolution_id": expression.evolution_id,
    }
    if isinstance(expression, BoundaryTMD):
        result.update(boundary_id=expression.boundary_id, source_id=expression.provenance.source_id)
    elif isinstance(expression, TransportedBoundary):
        result.update(boundary_id=expression.boundary_id, operand=describe_expression(expression.operand),
                      transport=describe_evolution(expression.boundary_transport.evolution))
    else:
        result.update(operand=describe_expression(expression.operand),
                      transport=describe_evolution(expression.transport))
    return result


def describe_evolution(transport: EvolutionMap) -> dict:
    return {
        "source": {"mu_GeV": transport.source.mu_GeV, "zeta_GeV2": transport.source.zeta_GeV2},
        "target": {"mu_GeV": transport.target.mu_GeV, "zeta_GeV2": transport.target.zeta_GeV2},
        "evolution_id": transport.evolution_id, "source_id": transport.provenance.source_id,
        "evidence_statuses": [item.status.value for item in transport.provenance.evidence],
        "components_in_application_order": [describe_evolution(component) for component in transport.components],
    }
