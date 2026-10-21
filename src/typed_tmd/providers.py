"""Collinear-value providers. Every provider returns f, never x*f.

The analytic provider has no DGLAP evolution. The optional LHAPDF adapter only
adapts its documented value convention; it does not supply TMD matching or make
the synthetic fixture a QCD prediction.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
from typing import Protocol, runtime_checkable

from .contracts import ContractError, finite


@runtime_checkable
class CollinearProvider(Protocol):
    @property
    def identifier(self) -> str: ...

    @property
    def quantity(self) -> str: ...

    def f(self, pid: int, x: float, mu_GeV: float) -> float: ...


@dataclass(frozen=True)
class ProviderSupport:
    x_min: float | None = None
    x_max: float | None = None
    q_min_GeV: float | None = None
    q_max_GeV: float | None = None
    flavors: tuple[int, ...] | None = None

    @property
    def known(self) -> bool:
        return all(value is not None for value in (self.x_min, self.x_max, self.q_min_GeV, self.q_max_GeV, self.flavors))


def _native_support(pdf: object) -> ProviderSupport:
    def read(name: str):
        value = getattr(pdf, name, None)
        return value() if callable(value) else value

    values = {}
    for native, name in (("xMin", "x_min"), ("xMax", "x_max"), ("qMin", "q_min_GeV"), ("qMax", "q_max_GeV")):
        raw = read(native)
        values[name] = None if raw is None else finite(raw, f"LHAPDF support {native}")
    # Some LHAPDF bindings expose the grid's scale limits only in GeV^2.
    # Convert those to the GeV convention used by this provider interface.
    for native, name in (("q2Min", "q_min_GeV"), ("q2Max", "q_max_GeV")):
        if values[name] is None:
            raw = read(native)
            if raw is not None:
                values[name] = math.sqrt(finite(raw, f"LHAPDF support {native}", positive=True))
    raw_flavors = read("flavors")
    flavors = None if raw_flavors is None else tuple(raw_flavors)
    if flavors is not None and (not flavors or any(type(pid) is not int for pid in flavors)):
        raise ContractError("LHAPDF flavors metadata must be a nonempty integer sequence")
    for lower, upper in (("x_min", "x_max"), ("q_min_GeV", "q_max_GeV")):
        if values[lower] is not None and values[upper] is not None and values[lower] > values[upper]:
            raise ContractError("LHAPDF support metadata has reversed bounds")
    for name in ("x_min", "x_max"):
        if values[name] is not None and not 0 <= values[name] <= 1:
            raise ContractError("LHAPDF x support metadata must lie in [0,1]")
    for name in ("q_min_GeV", "q_max_GeV"):
        if values[name] is not None and values[name] <= 0:
            raise ContractError("LHAPDF Q support metadata must be positive")
    return ProviderSupport(**values, flavors=flavors)


def _arguments(pid: int, x: float, mu_GeV: float) -> tuple[float, float]:
    if type(pid) is not int:
        raise ContractError("A parton id must be an integer")
    x, mu_GeV = finite(x, "x"), finite(mu_GeV, "mu", positive=True)
    if not 0 < x < 1:
        raise ContractError("Provider momentum fraction x must lie in (0,1)")
    return x, mu_GeV


@dataclass(frozen=True)
class AnalyticFixturePDF:
    normalizations: tuple[tuple[int, float], ...] = ((1, 2.0), (2, 4.0), (-1, 0.2), (-2, 0.4))

    def __post_init__(self) -> None:
        values = tuple((pid, finite(value, "normalization")) for pid, value in self.normalizations)
        if len({pid for pid, _ in values}) != len(values):
            raise ContractError("Duplicate fixture parton ids")
        if any(type(pid) is not int or not 1 <= abs(pid) <= 6 for pid, _ in values):
            raise ContractError("The fixture supports signed quark ids +/-1 through +/-6")
        object.__setattr__(self, "normalizations", values)

    @property
    def identifier(self) -> str:
        standard = ((1, 2.0), (2, 4.0), (-1, 0.2), (-2, 0.4))
        return "analytic-fixture-pdf-v1" if self.normalizations == standard else f"analytic-fixture-pdf-v1:{self.normalizations!r}"

    @property
    def quantity(self) -> str:
        return "f"

    def f(self, pid: int, x: float, mu_GeV: float) -> float:
        x, _ = _arguments(pid, x, mu_GeV)
        values = dict(self.normalizations)
        if pid not in values:
            raise ContractError(f"No analytic fixture input for parton id {pid}")
        return values[pid] * x ** 0.3 * (1 - x) ** 3


class LHAPDFProvider:
    """An optional xfxQ/x adapter; LHAPDF and its data are installed separately."""

    def __init__(self, set_name: str, member: int = 0, *, allow_unknown_support: bool = False) -> None:
        if not set_name or type(member) is not int or member < 0:
            raise ContractError("LHAPDF requires a set name and a nonnegative integer member")
        try:
            lhapdf = importlib.import_module("lhapdf")
        except ImportError as error:
            raise ImportError("Optional LHAPDF Python bindings are unavailable; the analytic fixture needs none") from error
        self._pdf = lhapdf.mkPDF(set_name, member)
        self._identifier = f"LHAPDF:{set_name}/{member}"
        self._support = _native_support(self._pdf)
        self._allow_unknown_support = bool(allow_unknown_support)

    @classmethod
    def from_object(cls, pdf: object, identifier: str, *, allow_unknown_support: bool = False) -> LHAPDFProvider:
        """Adapt an existing native object, also allowing a small test double."""
        if not callable(getattr(pdf, "xfxQ", None)) or not identifier:
            raise ContractError("An LHAPDF-like object must expose xfxQ and have an identifier")
        instance = cls.__new__(cls)
        instance._pdf, instance._identifier = pdf, identifier
        instance._support = _native_support(pdf)
        instance._allow_unknown_support = bool(allow_unknown_support)
        return instance

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def quantity(self) -> str:
        return "f"

    @property
    def support(self) -> ProviderSupport:
        return self._support

    @property
    def support_policy(self) -> str:
        return "unknown_metadata_explicitly_allowed; known_bounds_still_enforced" if self._allow_unknown_support else "require_known_support; reject_extrapolation"

    def f(self, pid: int, x: float, mu_GeV: float) -> float:
        x, mu_GeV = _arguments(pid, x, mu_GeV)
        support = self.support
        if not support.known and not self._allow_unknown_support:
            raise ContractError("LHAPDF support metadata is incomplete; unknown support requires an explicit opt-in")
        if support.flavors is not None and pid not in support.flavors:
            raise ContractError(f"Parton id {pid} is absent from the declared LHAPDF flavors")
        for value, lower, upper, name in ((x, support.x_min, support.x_max, "x"),
                                          (mu_GeV, support.q_min_GeV, support.q_max_GeV, "Q")):
            if (lower is not None and value < lower) or (upper is not None and value > upper):
                raise ContractError(f"LHAPDF {name} lies outside native support; extrapolation is disabled")
        return finite(finite(self._pdf.xfxQ(pid, x, mu_GeV), "LHAPDF x*f") / x, "LHAPDF f")
