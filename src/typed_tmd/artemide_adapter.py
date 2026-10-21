"""Narrow serial adapter for the pinned SV19 DY harpy interface.

The owning process must not mutate harpy outside this session. Native global
state has no trustworthy public getter; arbitrary out-of-band FFI mutations
cannot be detected. All admitted evaluations rebind the complete NP vector.
Provider, code, constants or precision changes require a new isolated process.
"""
from __future__ import annotations

from threading import RLock
import math
import numpy as np

from .contracts import ContractError
from .observations import ObservationContract, ResponseMeaning, ResponsePlan, identity
from .observation_quadrature import integrate_mass_rapidity, integrate_point_density

_NATIVE_STATE_LOCK = RLock()


class ArtemideSession:
    def __init__(self, native, physics_identity, fixed_parameters, parameter_bounds,
                 *, sections=16, orders=(12, 8, 6), mass_breaks=(80., 86., 89., 91., 93., 96., 102.), native_config_sha256="analytic_fixture"):
        if len(fixed_parameters) != 9 or not all(math.isfinite(v) for v in fixed_parameters):
            raise ContractError("SV19 requires the declared full nine-parameter vector")
        if not physics_identity or sections < 2 or sections % 2:
            raise ContractError("Missing backend identity or invalid Simpson sections")
        lo, hi = parameter_bounds
        if not (math.isfinite(lo) and math.isfinite(hi) and 0 < lo < hi):
            raise ContractError("Invalid admitted c0 domain")
        self._native = native
        self._fixed = tuple(fixed_parameters)
        self.bounds, self._sections = (lo, hi), sections
        self._native_config_sha256 = native_config_sha256
        self.orders, self.mass_breaks = tuple(orders), tuple(mass_breaks)
        self.identity = identity({"native_inputs": physics_identity,
            "fixed_parameters": {str(i): v for i, v in enumerate(self._fixed) if i != 1},
            "free_parameter": "SV19.c0", "domain": self.bounds})
        # The native library is process-global, so distinct session instances
        # must share this lock too. Per-instance locks would permit NP races.
        self._lock, self._epoch, self._invalid = _NATIVE_STATE_LOCK, 0, None
        self.calls = {"parameter_sets": 0, "native_bin": 0, "native_point_batches": 0, "native_points": 0}

    @property
    def sections(self):
        """Native configuration minimum; changing it requires a new process."""
        return self._sections

    def invalidate(self, reason):
        """Retire plans before any admitted external provider/precision change."""
        with self._lock:
            self._epoch += 1
            self._invalid = str(reason)

    def _check(self, contract, epoch):
        if self._invalid is not None or epoch != self._epoch:
            raise ContractError("Stale native state; start an isolated session: " + str(self._invalid))
        if contract.physics_identity != self.identity:
            raise ContractError("Provider/model/configuration identity differs")

    def _bind(self, theta):
        if len(theta) != 1 or not math.isfinite(theta[0]) or not self.bounds[0] <= theta[0] <= self.bounds[1]:
            raise ContractError("Expected one c0 within the frozen native domain")
        values = list(self._fixed)
        values[1] = float(theta[0])
        self._native.setNPparameters(values)
        self.calls["parameter_sets"] += 1

    def _points(self, row, qt, mass, rapidity):
        n = len(qt)
        self.calls["native_point_batches"] += 1
        self.calls["native_points"] += n
        return self._native.DY.xSecListBINLESS(
            np.tile(row.process, (n, 1)), np.full(n, row.s), qt, mass, rapidity,
            np.full(n, row.include_cuts), np.tile(row.cuts, (n, 1)))

    def plan(self, contract: ObservationContract, *, operation="native_bin_average") -> ResponsePlan:
        epoch = self._epoch
        sections, orders, mass_breaks = self.sections, self.orders, self.mass_breaks
        self._check(contract, epoch)
        if operation not in {"native_bin_average", "independent_bin_average", "qT_point_density"}:
            raise ContractError("Unsupported observation operation")
        meaning = contract.expected if operation != "qT_point_density" else ResponseMeaning(
            "point_density", contract.measure, contract.units, contract.digest)
        source = {
            "native_bin_average": "native.integral[dqT2,dQ2,dy](kernel(theta),cuts)/bin_measure * rapidity_multiplicity",
            "independent_bin_average": "GL[dqT,dQ,dy](4*qT*Q*native.point(theta),cuts)/bin_measure * rapidity_multiplicity",
            "qT_point_density": "point(qT_mid, integral[dQ2,dy](native.point(theta),cuts)) * qT_measure_Jacobian * rapidity_multiplicity",
        }[operation]

        def evaluate(theta):
            with self._lock:
                self._check(contract, epoch)
                self._bind(theta)
                result = []
                for row in contract.bins:
                    if operation == "native_bin_average":
                        self.calls["native_bin"] += 1
                        value = self._native.DY.xSec(list(row.process), row.s, list(row.qT),
                            list(row.Q), list(row.y), row.include_cuts, list(row.cuts))
                        value *= row.average_factor(contract.measure)
                    elif operation == "independent_bin_average":
                        value = integrate_point_density(self._points, row, orders, mass_breaks)
                        value *= row.average_factor(contract.measure)
                    else:
                        qt = sum(row.qT)/2
                        value = integrate_mass_rapidity(self._points, row, qt, orders[1:], mass_breaks)
                        value *= row.rapidity_multiplicity * (2*qt if contract.measure == "dqT" else 1)
                    if not math.isfinite(float(value)):
                        raise ContractError("Native response is nonfinite")
                    result.append(float(value))
                return tuple(result)

        return ResponsePlan(meaning, source, ("SV19.c0",), self.identity, epoch,
            (("operation", operation), ("native_minimum_Simpson_sections", str(sections)),
             ("native_constants_sha256", self._native_config_sha256),
             ("GL_orders", repr(orders)), ("Q_breaks_GeV", repr(mass_breaks))),
            "pinned source audit and native/independent observation comparisons; caller metadata is not a proof", evaluate)
