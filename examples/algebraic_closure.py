#!/usr/bin/env python3
"""Run the handoff-001 synthetic fixture; no optimizer or physical QCD fit.

After an editable installation:
    python examples/algebraic_closure.py --output results/local/algebraic_closure.json
The optional --backend stdlib flag exercises the dependency-free quadrature.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, fields, replace
import hashlib
import json
import math
from pathlib import Path
import sys

from typed_tmd import (
    AccuracySpec, AnalyticFixturePDF, CoefficientOrders, ContractError,
    DYKinematics, EvolutionGenerators, GaussianParameters, KinematicDomain,
    Polynomial, ScalePoint, SyntheticGaussianModel, TMDContext,
    describe_expression, require_compatible,
)


def _known_fields(cls, values: dict) -> dict:
    return {item.name: values[item.name] for item in fields(cls) if item.name in values}


def load_benchmark(path: Path) -> tuple[dict, SyntheticGaussianModel, ScalePoint, ScalePoint, DYKinematics, tuple]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or config.get("fixture", {}).get("id") != "synthetic-gaussian-v1":
        raise ContractError("Only schema 1 and the explicitly synthetic Gaussian fixture are implemented")
    fixture = config["fixture"]
    reference = ScalePoint(fixture["mu_ref_GeV"], fixture["zeta_ref_GeV2"])
    parameters = GaussianParameters(
        gamma_K=fixture["gamma_K"], gamma0=fixture["gamma0"],
        width_GeV2=fixture["width_GeV2"], g2_GeV2=fixture["g2_GeV2"], reference=reference,
    )
    A = ScalePoint(**config["boundaries"]["A"])
    B = ScalePoint(**config["boundaries"]["B"])
    target = ScalePoint(**config["target"])
    if A != reference:
        raise ContractError("Boundary A must equal the specified fixture reference")
    provider_config = config.get("pdf_provider", {})
    if provider_config.get("id", "analytic-fixture-pdf-v1") not in ("analytic-fixture-v1", "analytic-fixture-pdf-v1"):
        raise ContractError("The example only executes the analytic fixture provider")
    if provider_config.get("lhapdf_set") is not None:
        raise ContractError("LHAPDF integration is not silently substituted into this synthetic benchmark")
    norms = provider_config.get("normalizations")
    provider = AnalyticFixturePDF() if norms is None else AnalyticFixturePDF(tuple((int(pid), value) for pid, value in norms.items()))
    accuracy = config.get("accuracy_inventory", {})
    if accuracy:
        if accuracy.get("mode") not in ("synthetic_exact_connection", "synthetic_exact"):
            raise ContractError("The example refuses a physical perturbative accuracy claim")
        forbidden = [name for name, value in accuracy.items()
                     if (name.startswith("qcd_") or name in ("resummation_label", "collinear_pdf_perturbative_order", "fixed_order_Y_matching_order"))
                     and value is not None]
        if forbidden:
            raise ContractError("Synthetic configuration has unsupported QCD accuracy fields: " + ", ".join(forbidden))
    observable = config.get("observable", {})
    if observable.get("primary_density", "per_d2_qT") != "per_d2_qT" or observable.get("photon_dy_prefactor_applied", False):
        raise ContractError("Only the synthetic W density per d2qT is implemented")
    if observable.get("fourier_inverse", "F(k)=integral d2b/(2*pi)^2 exp(+i*k.b) F_tilde(b)") != "F(k)=integral d2b/(2*pi)^2 exp(+i*k.b) F_tilde(b)":
        raise ContractError("The requested Fourier inverse differs from the implemented convention")
    if observable.get("fourier_forward", "F_tilde(b)=integral d2k exp(-i*k.b) F(k)") != "F_tilde(b)=integral d2k exp(-i*k.b) F(k)":
        raise ContractError("The requested Fourier forward transform differs from the implemented convention")
    domain_config = config["domain"]
    if domain_config.get("x_endpoints", "excluded") != "excluded" or domain_config.get("qT_min_GeV", 0) != 0:
        raise ContractError("The fixture supports open x endpoints and nonnegative qT")
    domain = KinematicDomain(**_known_fields(KinematicDomain, domain_config))
    context = TMDContext(domain=domain, provider_id=provider.identifier)
    model = SyntheticGaussianModel(parameters, provider, context)
    kinematics = DYKinematics(**_known_fields(DYKinematics, config["kinematics"]))
    flavors = tuple((entry["pid"], entry["charge"]) for entry in config["flavors"])
    return config, model, B, target, kinematics, flavors


def _rejection(function) -> dict:
    try:
        function()
    except ContractError as error:
        return {"passed": True, "status": "rejected_as_expected", "error_type": type(error).__name__, "reason": str(error)}
    return {"passed": False, "status": "unexpectedly_accepted"}


def _line_integral(model: SyntheticGaussianModel, source: ScalePoint, target: ScalePoint, b: float) -> tuple[float, float]:
    """Independent hand-integrated polynomial generators, in both rectangular orders."""
    us, vs = source.coordinates(model.parameters.reference)
    ut, vt = target.coordinates(model.parameters.reference)
    p = model.parameters
    uv = (p.gamma0 - p.gamma_K * vs) * (ut - us) + p.gamma_K * (ut * ut - us * us) / 2
    uv += (-p.gamma_K * ut - p.g2_GeV2 * b * b) * (vt - vs)
    vu = (-p.gamma_K * us - p.g2_GeV2 * b * b) * (vt - vs)
    vu += (p.gamma0 - p.gamma_K * vt) * (ut - us) + p.gamma_K * (ut * ut - us * us) / 2
    return uv, vu


def _simpson_from_values(values: list[float], lower: float, upper: float) -> float:
    intervals = len(values) - 1
    if intervals <= 0 or intervals % 2:
        raise ValueError("Composite Simpson needs a positive even interval count")
    weighted = values[0] + values[-1] + 4 * math.fsum(values[1:-1:2]) + 2 * math.fsum(values[2:-1:2])
    return (upper - lower) * weighted / (3 * intervals)


def run(config_path: Path, backend: str = "auto") -> dict:
    config, model, B, target, point, flavors = load_benchmark(config_path)
    integration = config.get("integration", {})
    abs_tol, rel_tol = float(integration.get("abs_tol", 1e-8)), float(integration.get("rel_tol", 1e-6))
    plan = config.get("verification_plan", {})
    evo_abs, evo_rel = float(plan.get("evolution_abs_tol", 1e-12)), float(plan.get("evolution_rel_tol", 1e-11))
    b_values = tuple(plan.get("boundary_transport_b_GeV_inv", (0, 0.1, 0.5, 1, 2)))
    Q_values = tuple(plan.get("canonical_Q_GeV", (4, 5, 8)))
    if len(set(Q_values)) < 2:
        raise ContractError("The checkpoint requires more than one canonical Q")
    A = model.parameters.reference
    reference = model.reference(flavors[0][0])
    rebased = model.boundary_transport(B).apply(reference)
    via_target = model.evolution(B, target).apply(rebased)
    checks = []

    generators = model.generators
    checks.append({"name": "exact_polynomial_connection", "passed": generators.curvature.is_zero,
                   "status": "symbolically_checked_in_finite_rational_polynomial_grammar",
                   "potential": model.potential.to_dict(), "gamma": generators.gamma.to_dict(),
                   "kernel": generators.kernel.to_dict(), "curvature": generators.curvature.to_dict()})

    samples = []
    line_errors = []
    for Q in Q_values:
        k = replace(point, Q_GeV=Q)
        model.context.domain.validate_dy(k)
        end = ScalePoint(Q, Q * Q)
        direct = model.evolution(A, end).apply(reference)
        via = model.evolution(B, end).apply(rebased)
        for b in b_values:
            direct_value, via_value = model.evaluate(direct, point.x_a, b), model.evaluate(via, point.x_a, b)
            tolerance = evo_abs + evo_rel * abs(direct_value)
            samples.append({"Q_GeV": Q, "b_GeV_inv": b, "direct": direct_value, "via_B": via_value,
                            "abs_difference": abs(direct_value - via_value), "tolerance": tolerance})
            uv, vu = _line_integral(model, A, end, b)
            endpoint = model.potential_value(end, b) - model.potential_value(A, b)
            line_errors.extend((abs(endpoint - uv), abs(endpoint - vu)))
    checks.append({"name": "boundary_transport_multiple_Q", "passed": all(row["abs_difference"] <= row["tolerance"] for row in samples),
                   "status": "numerically_validated", "samples": samples})
    checks.append({"name": "independent_generator_line_integrals", "passed": max(line_errors) <= evo_abs,
                   "status": "numerically_validated_against_separately_integrated_generators",
                   "maximum_absolute_log_transport_error": max(line_errors), "tolerance": evo_abs})

    fourier_samples = []
    for Q in Q_values:
        k = replace(point, Q_GeV=Q)
        direct = model.dy_expression(k, flavors=flavors)
        via = model.dy_expression(k, flavors=flavors, via_boundary=B)
        exact = model.dy_analytic(direct)
        numerical = model.dy_numerical(via, abs_tol=abs_tol, rel_tol=rel_tol, backend=backend)
        tolerance = abs_tol + rel_tol * abs(exact)
        fourier_samples.append({"Q_GeV": Q, "analytic_W_GeV_inverse2": exact, "numerical": asdict(numerical),
                                "abs_difference": abs(exact - numerical.value), "tolerance": tolerance})
    checks.append({"name": "dy_flavor_sum_and_fourier_multiple_Q", "passed": all(row["abs_difference"] <= row["tolerance"] for row in fourier_samples),
                   "status": "numerically_validated_synthetic_observable", "samples": fourier_samples})

    baseline = model.dy_expression(point, flavors=flavors, mu_GeV=target.mu_GeV,
                                   zeta_a_GeV2=target.zeta_GeV2)
    varied = model.dy_expression(point, flavors=flavors, mu_GeV=1.4 * point.Q_GeV,
                                 zeta_a_GeV2=point.Q_GeV ** 2 * math.exp(0.6), via_boundary=B)
    cancellation_errors = [abs(model.dy_b_space(baseline, b) - model.dy_b_space(varied, b)) for b in b_values]
    checks.append({"name": "synthetic_hard_and_rapidity_partition_cancellation", "passed": max(cancellation_errors) <= evo_abs,
                   "status": "numerically_validated_synthetic_counterfactor_only",
                   "maximum_absolute_error": max(cancellation_errors), "tolerance": evo_abs})

    lower, upper = plan.get("radial_bin_GeV", (0, 1))
    if not (0 <= lower < upper):
        raise ContractError("The radial bin must be nonnegative and ordered")
    model.context.domain.validate_dy(replace(point, qT_GeV=upper))
    amplitude, width = model.dy_gaussian_parameters(baseline)
    exact_bin = amplitude * (math.exp(-lower * lower / (4 * width)) - math.exp(-upper * upper / (4 * width)))
    # This is a separate qT integration of independently Fourier-integrated W.
    intervals = 32
    densities, density_errors = [], []
    for i in range(intervals + 1):
        q = lower + (upper - lower) * i / intervals
        expression = model.dy_expression(replace(point, qT_GeV=q), flavors=flavors, via_boundary=B)
        result = model.dy_numerical(expression, abs_tol=abs_tol / 8, rel_tol=rel_tol / 8, backend=backend)
        densities.append(2 * math.pi * q * result.value)
        density_errors.append(2 * math.pi * q * result.estimated_abs_error)
    numerical_bin = _simpson_from_values(densities, lower, upper)
    coarse_bin = _simpson_from_values(densities[::2], lower, upper)
    estimated_bin_error = abs(numerical_bin - coarse_bin) / 15 + _simpson_from_values(density_errors, lower, upper)
    bin_tolerance = abs_tol + rel_tol * abs(exact_bin)
    W = model.dy_analytic(baseline)
    checks.append({"name": "density_jacobians_and_finite_radial_bin", "passed": abs(exact_bin - numerical_bin) <= bin_tolerance,
                   "status": "numerically_validated_with_independent_closed_bin_reference",
                   "W_per_d2qT_GeV_inverse2": W, "density_per_dqT_GeV_inverse": 2 * math.pi * point.qT_GeV * W,
                   "density_per_dqT_squared_GeV_inverse2": math.pi * W, "bin_GeV": [lower, upper],
                   "analytic_bin": exact_bin, "numerical_bin": numerical_bin,
                   "abs_difference": abs(exact_bin - numerical_bin), "tolerance": bin_tolerance,
                   "estimated_numerical_error": estimated_bin_error,
                   "error_note": "Quadrature estimates are not certified global error bounds"})

    wrong_source = ScalePoint(A.mu_GeV * 1.1, A.zeta_GeV2)
    checks.append({"name": "illegal_composition", **_rejection(lambda: model.evolution(wrong_source, target).apply(reference))})
    wrong_context = replace(model.context, conventions=replace(model.context.conventions, provider_quantity="xf"))
    checks.append({"name": "convention_mismatch", **_rejection(lambda: replace(model.evolution(A, target), context=wrong_context).apply(reference))})
    narrow_domain = replace(model.context.domain, x_min=(model.context.domain.x_min + model.context.domain.x_max) / 2)
    checks.append({"name": "domain_mismatch", **_rejection(lambda: require_compatible(model.context, replace(model.context, domain=narrow_domain)))})
    orders = CoefficientOrders(H=1, C=1, K=2, gamma=2, cusp=3, P=2, beta=3)
    metadata = AccuracySpec("perturbative_manifest", "metadata-only rejection test; never executed", "alpha_s/(4*pi)", orders)
    first_context = replace(model.context, accuracy=metadata)
    second_context = replace(first_context, accuracy=replace(metadata, coefficients=replace(orders, C=2)))
    checks.append({"name": "perturbative_inventory_mismatch", **_rejection(lambda: require_compatible(first_context, second_context)),
                   "note": "This checks metadata compatibility, not finite-order QCD evolution"})
    bad_generators = EvolutionGenerators(generators.gamma, generators.kernel + Polynomial.from_terms((("0.01", (1, 0, 0)),)))
    checks.append({"name": "invalid_exact_generator", **_rejection(bad_generators.require_exact_flatness),
                   "curvature": bad_generators.curvature.to_dict()})

    other = SyntheticGaussianModel(replace(model.parameters, width_GeV2=model.parameters.width_GeV2 * 1.2), model.provider, model.context)
    require_compatible(model.context, other.context)
    changed_W = other.dy_analytic(other.dy_expression(point, flavors=flavors))
    model_difference = abs(changed_W - W)
    checks.append({"name": "legitimate_model_difference", "passed": model_difference > abs_tol,
                   "status": "admitted_distinct_model; difference_is_not_repaired",
                   "original_model_id": model.model_id, "other_model_id": other.model_id,
                   "original_W": W, "other_W": changed_W, "abs_difference": model_difference,
                   "note": "No data fit, parameter bias or extraction claim follows from this difference"})

    passed = all(item["passed"] for item in checks)
    return {
        "schema_version": 1, "benchmark_id": config.get("benchmark_id", "synthetic-gaussian-v1"),
        "status": "passed" if passed else "failed", "all_passed": passed,
        "scientific_status": "synthetic_fixture_only; no_physical_QCD_validation; no_extraction",
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "context": asdict(model.context), "parameters": asdict(model.parameters),
        "boundary_A": asdict(A), "boundary_B": asdict(B), "target": asdict(target),
        "example_transport_ast": describe_expression(via_target), "checks": checks,
        "evidence_limits": [
            "Type checks establish declared compatibility, not physical validity.",
            "Polynomial identities are checked by a small exact rational algebra, not a proof assistant.",
            "The analytic reference and the numerical Fourier evaluator are independent value computations sharing input validation.",
            "Quadrature estimates and sampled closure do not certify arbitrary functions or all parameter values.",
            "QCD factorization, coefficient matching, data extraction and physical scheme conversion are not implemented.",
            "LHAPDF adapter tests use a native-interface test double unless a separate real-library smoke test is run.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "configs" / "benchmark.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("auto", "scipy", "stdlib"), default="auto")
    args = parser.parse_args()
    try:
        report = run(args.config, args.backend)
    except Exception as error:
        report = {"schema_version": 1, "status": "failed", "all_passed": False,
                  "scientific_status": "synthetic_fixture_only", "error_type": type(error).__name__, "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    passed_count = sum(item["passed"] for item in report.get("checks", []))
    print(f"{report['status']}: {passed_count}/{len(report.get('checks', []))} checks; synthetic fixture only; report: {args.output}")
    if "error" in report:
        print(report["error"], file=sys.stderr)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
