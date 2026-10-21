"""Finite DY observation contracts. These are runtime checks, not proofs.

The native adapter, not its caller, binds a response's observation meaning.
Point evaluation and bin averaging can have the same units and still differ.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Callable

from .contracts import ContractError


def identity(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class DYBin:
    name: str
    qT: tuple[float, float]
    Q: tuple[float, float]
    y: tuple[float, float]
    s: float
    process: tuple[int, int, int]
    include_cuts: bool
    cuts: tuple[float, float, float, float]
    rapidity_multiplicity: float = 1.0

    def __post_init__(self):
        for name in ("qT", "Q", "y"):
            interval = getattr(self, name)
            if (not isinstance(interval, tuple) or len(interval) != 2
                    or not all(math.isfinite(x) for x in interval)
                    or interval[0] >= interval[1]):
                raise ContractError(f"Invalid {name} interval")
        if (self.qT[0] < 0 or self.Q[0] <= 0 or not math.isfinite(self.s) or self.s <= 0
                or not math.isfinite(self.rapidity_multiplicity) or self.rapidity_multiplicity <= 0):
            raise ContractError("Invalid DY domain or rapidity multiplicity")
        if (not self.name or not isinstance(self.process, tuple) or len(self.process) != 3
                or any(type(p) is not int for p in self.process)
                or not isinstance(self.cuts, tuple) or len(self.cuts) != 4 or not all(math.isfinite(x) for x in self.cuts)
                or type(self.include_cuts) is not bool):
            raise ContractError("Invalid process/cuts identity")

    def average_factor(self, measure: str) -> float:
        if measure == "dqT":
            return self.rapidity_multiplicity / (self.qT[1] - self.qT[0])
        if measure == "dqT2":
            return self.rapidity_multiplicity / (self.qT[1]**2 - self.qT[0]**2)
        raise ContractError(f"Unsupported observation measure: {measure}")


@dataclass(frozen=True)
class ObservationContract:
    bins: tuple[DYBin, ...]
    physics_identity: str
    measure: str = "dqT"

    def __post_init__(self):
        if not isinstance(self.bins, tuple) or not self.bins or not self.physics_identity:
            raise ContractError("Ordered bins and physics identity are required")
        if len({b.name for b in self.bins}) != len(self.bins):
            raise ContractError("Duplicate observation row identity")
        for b in self.bins:
            b.average_factor(self.measure)

    @property
    def digest(self) -> str:
        return identity(asdict(self))

    @property
    def units(self) -> str:
        return "pb/GeV" if self.measure == "dqT" else "pb/GeV^2"

    @property
    def expected(self) -> "ResponseMeaning":
        return ResponseMeaning("bin_average", self.measure, self.units, self.digest)


@dataclass(frozen=True)
class ResponseMeaning:
    kind: str
    measure: str
    units: str
    observation_identity: str


class ObservationMismatch(ContractError):
    def __init__(self, expected: ResponseMeaning, supplied: ResponseMeaning):
        self.diagnostic = {
            "code": "observation_mismatch", "expected": asdict(expected),
            "supplied": asdict(supplied),
            "required_operation": "integrate the point density over the declared qT bin with its measure, then divide by the bin measure",
            "stage": "fit_problem_construction",
        }
        super().__init__(json.dumps(self.diagnostic, sort_keys=True))


@dataclass(frozen=True)
class ResponsePlan:
    meaning: ResponseMeaning
    source_expression: str
    parameter_dependencies: tuple[str, ...]
    backend_identity: str
    state_epoch: int
    numerical_plan: tuple[tuple[str, str], ...]
    check_origin: str
    # Evaluation is excluded from serialized identity. It must be the adapter's
    # audited binding; a caller attaching false metadata is outside this check.
    evaluator: Callable[[tuple[float, ...]], tuple[float, ...]]

    def record(self) -> dict:
        result = {
            "meaning": asdict(self.meaning), "source_expression": self.source_expression,
            "parameter_dependencies": self.parameter_dependencies,
            "backend_identity": self.backend_identity, "state_epoch": self.state_epoch,
            "numerical_plan": self.numerical_plan, "check_origin": self.check_origin,
            "evidence_kind": "runtime_contract; not Lean-verified translation",
        }
        result["source_identity"] = identity({"expression": self.source_expression,
                                               "dependencies": self.parameter_dependencies,
                                               "backend": self.backend_identity})
        result["plan_identity"] = identity(result)
        return result

    def evaluate(self, theta: tuple[float, ...]) -> tuple[float, ...]:
        return self.evaluator(theta)


class ObservedFitProblem:
    """Bind semantics before invoking any backend or optimizer."""
    def __init__(self, contract: ObservationContract, plan: ResponsePlan,
                 data: tuple[float, ...], sigma: tuple[float, ...]):
        if plan.meaning != contract.expected:
            raise ObservationMismatch(contract.expected, plan.meaning)
        if plan.backend_identity != contract.physics_identity:
            raise ContractError("Response and observation physics identities differ")
        if len(data) != len(contract.bins) or len(sigma) != len(data):
            raise ContractError("Observation/data/covariance dimensions differ")
        if not all(math.isfinite(v) for v in data) or not all(math.isfinite(v) and v > 0 for v in sigma):
            raise ContractError("Data must be finite and diagonal errors positive")
        self.contract, self.plan, self.data, self.sigma = contract, plan, tuple(data), tuple(sigma)

    def residuals(self, theta: tuple[float, ...]) -> tuple[float, ...]:
        prediction = self.plan.evaluate(theta)
        if len(prediction) != len(self.data) or not all(math.isfinite(v) for v in prediction):
            raise ContractError("Invalid backend response")
        return tuple((p-y)/s for p, y, s in zip(prediction, self.data, self.sigma))


def convert_averages(values: tuple[float, ...], source: ObservationContract,
                     target: ObservationContract) -> tuple[float, ...]:
    """Exact diagonal map between two averages of the SAME integrated yields.

    Apply this same map to data and both axes of covariance when transporting
    a full inference problem. This function converts only a response vector.
    """
    if source.bins != target.bins or source.physics_identity != target.physics_identity:
        raise ContractError("Average conversion requires identical bin yields and physics")
    if len(values) != len(source.bins) or not all(math.isfinite(v) for v in values):
        raise ContractError("Invalid average vector")
    return tuple(v * b.average_factor(target.measure) / b.average_factor(source.measure)
                 for v, b in zip(values, source.bins))
