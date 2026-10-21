"""Public API for the dependency-light, explicitly synthetic typed TMD seed."""

from .algebra import EvolutionGenerators, Monomial, Polynomial
from .contracts import (
    AccuracySpec, CoefficientOrders, ContractError, ContextMismatchError,
    Conventions, DefinitionSpec, DomainCompatibilityError, DomainViolationError,
    DYKinematics, Evidence, EvidenceStatus, EvolutionConsistencyError, ExternalInput,
    InventoryMismatchError, KinematicDomain, Provenance, ScalePoint, TMDContext,
    require_compatible,
)
from .expressions import (
    BoundaryTMD, BoundaryTransport, DYExpression, DYTerm, EvolvedTMD,
    EvolutionMap, TMDExpression, TransportedBoundary, describe_evolution, describe_expression,
)
from .fixtures import GaussianParameters, SyntheticGaussianModel
from .numerics import QuadratureResult, gaussian_fourier_analytic, radial_fourier
from .providers import AnalyticFixturePDF, CollinearProvider, LHAPDFProvider, ProviderSupport

__version__ = "0.4.0"

__all__ = [
    "AccuracySpec", "AnalyticFixturePDF", "BoundaryTMD", "BoundaryTransport",
    "CoefficientOrders", "CollinearProvider", "ContractError", "ContextMismatchError",
    "Conventions", "DefinitionSpec", "DomainCompatibilityError", "DomainViolationError",
    "DYExpression", "DYKinematics", "DYTerm", "EvolvedTMD", "Evidence", "EvidenceStatus",
    "EvolutionConsistencyError", "EvolutionGenerators", "EvolutionMap", "ExternalInput", "GaussianParameters",
    "InventoryMismatchError", "KinematicDomain", "LHAPDFProvider", "Monomial", "Polynomial",
    "Provenance", "ProviderSupport", "QuadratureResult", "ScalePoint", "SyntheticGaussianModel", "TMDContext",
    "TMDExpression", "TransportedBoundary", "describe_evolution", "describe_expression", "gaussian_fourier_analytic",
    "radial_fourier", "require_compatible",
]
