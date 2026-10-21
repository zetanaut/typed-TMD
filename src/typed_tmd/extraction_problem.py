"""Small runtime types binding a frozen observable, dataset, and fit model.

These contracts validate an executable calculation. They are not a proof of
factorization, an experimental-data validator, or a static dependent type system.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

import numpy as np

from .contracts import ContractError
from .extraction import APPROVED, CONTROL, Chart, LOWER, WIDTH, ModelTemplate, ObservationTarget


def _immutable_array(value, shape, *, positive=False):
    array = np.asarray(value, dtype=float)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ContractError("invalid_dataset_array")
    if positive and not np.all(array > 0):
        raise ContractError("nonpositive_dataset_standard_deviation")
    # A bytes-backed array cannot have WRITEABLE restored by its caller.
    return np.frombuffer(array.tobytes(), dtype=float).reshape(shape)


def target_record(target):
    return {"Q_GeV": target.Q_GeV, "qT_GeV": target.qT_GeV,
            "x_a": target.x_a, "x_b": target.x_b,
            "window": list(target.window), "measure": target.measure,
            "units": target.units}


def observable_identity(targets):
    """The ordered grid is part of the observable, not an array annotation."""
    if not isinstance(targets, tuple) or not targets:
        raise ContractError("invalid_observation_sequence")
    for t in targets:
        if type(t) is not ObservationTarget:
            raise ContractError("untyped_observation_target")
        for x, y in ((t.x_a, 0.3), (t.x_b, -0.3)):
            if (not math.isfinite(x) or not 0 < x < 1 or
                    not math.isclose(x, t.Q_GeV * math.exp(y) / 200., rel_tol=2e-14, abs_tol=0.)):
                raise ContractError("beam_kinematics_mismatch")
    grid = [(t.Q_GeV, t.qT_GeV) for t in targets]
    if grid != sorted(set(grid)):
        raise ContractError("observation_order_or_duplicate_mismatch")
    payload = {"definition": "Collins-soft-subtracted-unpolarized-DY-v1",
               "accuracy": "one-loop-generator/tree-matching diagnostic",
               "fourier": "1/(2*pi) integral db b J0(b*qT)",
               "target": "finite-window response without cross-section prefactor or Y term",
               "ordered_rows": [target_record(t) for t in targets]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class FrozenDataset:
    targets: tuple[ObservationTarget, ...]
    values: np.ndarray
    sigma: np.ndarray
    data_id: str
    provider_snapshot_id: str
    generating_model: ModelTemplate = APPROVED

    def __post_init__(self):
        observable_identity(self.targets)
        if not self.data_id or not self.provider_snapshot_id:
            raise ContractError("missing_dataset_provenance")
        if type(self.generating_model) is not ModelTemplate:
            raise ContractError("untyped_generating_model")
        object.__setattr__(self, "values", _immutable_array(self.values, (len(self.targets),)))
        object.__setattr__(self, "sigma", _immutable_array(self.sigma, (len(self.targets),), positive=True))

    @property
    def observation_id(self):
        return observable_identity(self.targets)


@dataclass(frozen=True)
class FitProblem:
    compiled: object
    dataset: FrozenDataset
    chart: Chart
    model: ModelTemplate
    comparison: str = "same_model"

    def __post_init__(self):
        if type(self.dataset) is not FrozenDataset or type(self.chart) is not Chart or type(self.model) is not ModelTemplate:
            raise ContractError("untyped_fit_problem")
        self.chart.jacobian_to_canonical()
        if observable_identity(self.compiled.targets) != self.dataset.observation_id:
            raise ContractError("fit_observation_mismatch")
        identity = self.compiled.identity
        cache_snapshot = (identity.get("snapshot_id") or identity.get("snapshot_payload_sha256")
                          or identity.get("provider_snapshot_id"))
        if cache_snapshot != self.dataset.provider_snapshot_id:
            raise ContractError("fit_provider_snapshot_mismatch")
        if self.comparison == "same_model":
            self.dataset.generating_model.compatible_with(self.model)
        elif self.comparison == "declared_coefficient_control":
            if self.dataset.generating_model != APPROVED or self.model != CONTROL:
                raise ContractError("unsupported_control_comparison")
        else:
            raise ContractError("unknown_model_comparison")

    def prediction_and_unit_jacobian(self, u):
        u = np.asarray(u, dtype=float)
        if u.shape != (2,) or not np.all(np.isfinite(u)) or np.any(u < 0) or np.any(u > 1):
            raise ContractError("invalid_optimizer_coordinates")
        canonical = LOWER + WIDTH * u
        values, chart_jac, _ = self.compiled.response(self.chart.coordinates(canonical), self.chart, self.model)
        canonical_jac = chart_jac @ np.linalg.inv(self.chart.jacobian_to_canonical())
        if (values.shape != self.dataset.values.shape or canonical_jac.shape != (len(values), 2)
                or not np.all(np.isfinite(values)) or not np.all(np.isfinite(canonical_jac))):
            raise ContractError("invalid_forward_response")
        return values, canonical_jac * WIDTH[None, :]

    def residual(self, u):
        return (self.prediction_and_unit_jacobian(u)[0] - self.dataset.values) / self.dataset.sigma

    def residual_jacobian(self, u):
        return self.prediction_and_unit_jacobian(u)[1] / self.dataset.sigma[:, None]
