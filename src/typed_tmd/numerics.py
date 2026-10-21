"""Independent radial quadrature for a function with a declared Gaussian bound.

The omitted Gaussian tail is bounded analytically. Quadrature errors are
estimates, not certified global bounds. SciPy is optional; the standard-library
backend uses adaptive Simpson quadrature and an angular quadrature for J0.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from .contracts import ContractError, finite


@dataclass(frozen=True)
class QuadratureResult:
    value: float
    estimated_abs_error: float
    tail_bound: float
    backend: str
    b_max_GeV_inv: float
    evaluations: int


def gaussian_fourier_analytic(amplitude: float, width_GeV2: float, kT_GeV: float) -> float:
    """Integral d2b/(2pi)^2 exp(+i k.b) amplitude*exp(-width*b^2)."""
    amplitude = finite(amplitude, "amplitude")
    width = finite(width_GeV2, "Gaussian width", positive=True)
    k = finite(kT_GeV, "kT")
    if k < 0:
        raise ContractError("kT must be nonnegative")
    return amplitude / (4 * math.pi * width) * math.exp(-k * k / (4 * width))


def _j0_angular(z: float) -> float:
    # J0(z) = mean_theta cos(z*cos(theta)); periodic trapezoidal quadrature.
    # Oversampling resolves the oscillation without a large-z power series.
    count = max(96, int(8 * abs(z)) + 32)
    return math.fsum(math.cos(z * math.cos(2 * math.pi * i / count)) for i in range(count)) / count


def _adaptive_simpson(function: Callable[[float], float], upper: float, tolerance: float) -> tuple[float, float, int]:
    evaluations = 0

    def evaluate(x: float) -> float:
        nonlocal evaluations
        evaluations += 1
        return finite(function(x), "integrand")

    def recurse(a: float, b: float, fa: float, fm: float, fb: float,
                whole: float, tol: float, depth: int) -> tuple[float, float]:
        midpoint = (a + b) / 2
        fl, fr = evaluate((a + midpoint) / 2), evaluate((midpoint + b) / 2)
        left = (midpoint - a) * (fa + 4 * fl + fm) / 6
        right = (b - midpoint) * (fm + 4 * fr + fb) / 6
        difference = left + right - whole
        if abs(difference) <= 15 * tol:
            return left + right + difference / 15, abs(difference) / 15
        if depth == 0:
            raise ArithmeticError("Standard-library quadrature failed to meet its requested tolerance")
        vl, el = recurse(a, midpoint, fa, fl, fm, left, tol / 2, depth - 1)
        vr, er = recurse(midpoint, b, fm, fr, fb, right, tol / 2, depth - 1)
        return vl + vr, el + er

    fa, fm, fb = evaluate(0), evaluate(upper / 2), evaluate(upper)
    initial = upper * (fa + 4 * fm + fb) / 6
    value, error = recurse(0, upper, fa, fm, fb, initial, tolerance, 22)
    return value, error, evaluations


def radial_fourier(
    b_space_function: Callable[[float], float], kT_GeV: float, *,
    bound_amplitude: float, bound_width_GeV2: float,
    abs_tol: float = 1e-8, rel_tol: float = 1e-6, backend: str = "auto",
) -> QuadratureResult:
    """Compute integral_0^infinity db*b*J0(k*b)*F(b)/(2pi).

    The caller must justify |F(b)| <= bound_amplitude*exp(-bound_width*b^2).
    This routine cannot establish that precondition for an arbitrary callable.
    """
    k = finite(kT_GeV, "kT")
    amplitude = finite(bound_amplitude, "bound amplitude")
    width = finite(bound_width_GeV2, "bound width", positive=True)
    abs_tol, rel_tol = finite(abs_tol, "absolute tolerance", positive=True), finite(rel_tol, "relative tolerance")
    if k < 0 or amplitude < 0 or rel_tol < 0:
        raise ContractError("kT, bound amplitude and relative tolerance must be nonnegative")
    if backend not in ("auto", "scipy", "stdlib"):
        raise ContractError("Quadrature backend must be auto, scipy or stdlib")
    if amplitude == 0:
        return QuadratureResult(0.0, 0.0, 0.0, "zero_gaussian_bound", 0.0, 0)
    tail_budget = abs_tol / 8
    log_ratio = math.log(amplitude) - math.log(4 * math.pi * width) - math.log(tail_budget)
    upper = math.sqrt(max(1.0, log_ratio) / width)
    tail = amplitude / (4 * math.pi * width) * math.exp(-width * upper * upper)
    if backend in ("auto", "scipy"):
        try:
            from scipy.integrate import quad
            from scipy.special import j0
        except ImportError:
            if backend == "scipy":
                raise ImportError("The requested SciPy quadrature backend is unavailable")
        else:
            def integrand(b: float) -> float:
                return b * float(j0(k * b)) * finite(b_space_function(b), "F(b)") / (2 * math.pi)
            output = quad(integrand, 0, upper, epsabs=abs_tol / 2,
                          epsrel=rel_tol / 2, limit=300, full_output=1)
            if len(output) > 3:
                raise ArithmeticError(f"SciPy quadrature did not converge: {output[3]}")
            value, error, info = output
            return QuadratureResult(value, error + tail, tail, "scipy_quad_j0", upper, info["neval"])
    def integrand(b: float) -> float:
        return b * _j0_angular(k * b) * finite(b_space_function(b), "F(b)") / (2 * math.pi)
    value, error, count = _adaptive_simpson(integrand, upper, abs_tol / 2)
    return QuadratureResult(value, error + tail, tail, "stdlib_simpson_angular_j0", upper, count)

