"""Independent-reference checks with analytic running inputs, no PDF snapshot."""
import math
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy.special import j0

from typed_tmd.contracts import ContractError
from typed_tmd.extraction import APPROVED, CONTROL, Chart
from typed_tmd.extraction_reference import CanonicalReference, compile_reference_window
from typed_tmd.provider_replay import digest
from typed_tmd.qcd_plan import profile_mu


class AnalyticInputs:
    """Signed toy densities and a coupling affine in log(mu), for tests only."""

    alpha0 = 0.23
    slope = 0.035
    normalizations = {1: 2.0, -1: -1.1, 2: 0.4, -2: 0.05, 3: 0.0, -3: -0.2}

    def __init__(self, payload):
        self.identifier = payload["provider_id"]
        self.snapshot_id = "analytic-inputs-test-snapshot"
        self.plan = {"payload": payload, "payload_sha256": digest(payload)}
        self.pdf_calls = 0
        self.alpha_calls = 0

    @classmethod
    def density(cls, pid, x, mu):
        return cls.normalizations[pid] * x * (1.0 - x) * (1.0 + 0.01 * math.log(mu))

    def f(self, pid, x, mu):
        self.pdf_calls += 1
        return self.density(pid, x, mu)

    def alpha_s(self, mu):
        self.alpha_calls += 1
        return self.alpha0 * (1.0 + self.slope * math.log(mu))


def tiny_plan():
    # These three weighted nodes define a small finite-quadrature fixture;
    # they are not advertised as an accurate physical Fourier integration.
    nodes = [(0.01, 0.003), (0.3, 0.6), (1.2, 2.4)]
    endpoints = {20.0, 30.0, 40.0, *(profile_mu(b) for b, _ in nodes)}
    partial = {}
    for mu in endpoints:
        high = math.log(mu)
        midpoint = high / 2.0
        offset = high / (2.0 * math.sqrt(3.0))
        partial[mu.hex()] = {
            "lower_knot_index": 0,
            "nodes": [[math.exp(t).hex(), (high / 2.0).hex(), t.hex()]
                      for t in (midpoint - offset, midpoint + offset)],
        }
    table = {"full": [], "partial": partial}
    points = []
    for Q in (20.0, 30.0, 40.0):
        for fraction in (0.025, 0.05, 0.1):
            point = {"Q_GeV": Q, "qT_GeV": fraction * Q,
                     "x_a": Q * math.exp(0.3) / 200.0,
                     "x_b": Q * math.exp(-0.3) / 200.0}
            points.append({key: value.hex() for key, value in point.items()})
    return {
        "provider_id": "analytic-inputs-test-provider",
        "points": points,
        "scale_plans": {"R4": table, "R8": table},
        "b_plans": {"nominal": {
            "edges_hex": [(0.0001).hex(), (8.0).hex()],
            "variants": {
                name: [[b.hex(), weight.hex()] for b, weight in nodes]
                for name in ("R16", "R32", "R64")},
        }},
    }


def closed_tmd(pid, x, b, Q, theta, lam):
    """Closed integral for c(t)=c0*(1+slope*t), independent of moment helpers."""
    a, g2 = theta
    mu_b = profile_mu(b)
    length = math.log(Q / mu_b)
    c0 = (4.0 / 3.0) * AnalyticInputs.alpha0 / math.pi
    c_at_boundary = c0 * (1.0 + AnalyticInputs.slope * math.log(mu_b))
    c_slope = c0 * AnalyticInputs.slope
    perturbative = (
        c_at_boundary * (1.5 * lam * length - length * length)
        + c_slope * (0.75 * lam * length * length - length ** 3 / 3.0))
    exponent = perturbative - a * b * b - g2 * b * b * length
    return AnalyticInputs.density(pid, x, mu_b) * math.exp(exponent)


def closed_weighted_response(cache, plan, theta, lam):
    nodes = [(float.fromhex(b), float.fromhex(w))
             for b, w in plan["b_plans"]["nominal"]["variants"]["R64"]]
    result = []
    for point in cache.targets:
        terms = []
        for b, weight in nodes:
            luminosity = 0.0
            for pid, charge in ((1, 1.0 / 9), (2, 4.0 / 9), (3, 1.0 / 9)):
                first = (closed_tmd(pid, point.x_a, b, point.Q_GeV, theta, lam) *
                         closed_tmd(-pid, point.x_b, b, point.Q_GeV, theta, lam))
                second = (closed_tmd(-pid, point.x_a, b, point.Q_GeV, theta, lam) *
                          closed_tmd(pid, point.x_b, b, point.Q_GeV, theta, lam))
                luminosity += charge * (first + second)
            terms.append(weight * b * j0(b * point.qT_GeV) * luminosity /
                         (2.0 * math.pi))
        result.append(math.fsum(terms))
    return np.asarray(result)


class CanonicalReferenceTests(unittest.TestCase):
    def setUp(self):
        self.plan = tiny_plan()
        self.provider = AnalyticInputs(self.plan)

    def test_scalar_signed_zero_and_reversed_matching_integrals(self):
        reference = CanonicalReference(self.provider, self.plan)
        theta = (0.27, 0.036)
        for model in (APPROVED, CONTROL):
            for b in (0.01, 1.2):
                for Q in (20.0, 30.0, 40.0):
                    for pid in (-1, 2, 3):
                        with self.subTest(model=model.coefficient_id, b=b, Q=Q, pid=pid):
                            expected = closed_tmd(pid, 0.2, b, Q, theta, model.lam)
                            actual = reference.tmd(pid, 0.2, b, Q, theta, model)
                            self.assertAlmostEqual(actual, expected, delta=2e-14 * max(1.0, abs(expected)))
                            if pid == -1:
                                self.assertLess(actual, 0.0)
                            elif pid == 3:
                                self.assertEqual(actual, 0.0)
        self.assertGreater(profile_mu(0.01), 40.0)
        self.assertLess(profile_mu(1.2), 20.0)

    def test_weighted_per_leg_response_does_not_call_production(self):
        with patch("typed_tmd.extraction.compile_window",
                   side_effect=AssertionError("production compiler used")), \
             patch("typed_tmd.qcd_forward.ProductionMoments",
                   side_effect=AssertionError("production moments used")):
            reference = compile_reference_window(self.provider, self.plan)
            for model in (APPROVED, CONTROL):
                actual = reference.response((0.27, 0.036), Chart("A"), model)[0]
                expected = closed_weighted_response(reference, self.plan, (0.27, 0.036), model.lam)
                np.testing.assert_allclose(actual, expected, rtol=3e-14, atol=1e-16)
                self.assertTrue(np.any(actual < 0.0))
        self.assertEqual(reference.identity["snapshot_id"], self.provider.snapshot_id)
        self.assertEqual(reference.identity["plan_payload_sha256"],
                         self.provider.plan["payload_sha256"])
        self.assertEqual(json.loads(json.dumps(reference.identity))["snapshot_id"],
                         self.provider.snapshot_id)
        with self.assertRaisesRegex(TypeError, "immutable"):
            reference.identity["snapshot_id"] = "changed"
        with self.assertRaisesRegex(TypeError, "immutable"):
            reference.identity["targets"][0]["Q_GeV"] = 99.0

    def test_canonical_chart_and_coefficient_derivatives(self):
        reference = compile_reference_window(self.provider, self.plan, Q_values=(30.0,))
        theta = np.array([0.27, 0.036])
        step = 1e-6
        for model in (APPROVED, CONTROL):
            value_a, jac_a, lambda_a = reference.response(theta, Chart("A"), model)
            beta = Chart("B").coordinates(theta)
            value_b, jac_b, lambda_b = reference.response(beta, Chart("B"), model)
            expected_jac = np.column_stack([
                (closed_weighted_response(reference, self.plan,
                                          theta + step * np.eye(2)[column], model.lam) -
                 closed_weighted_response(reference, self.plan,
                                          theta - step * np.eye(2)[column], model.lam)) / (2 * step)
                for column in range(2)])
            expected_lambda = (
                closed_weighted_response(reference, self.plan, theta, model.lam + step) -
                closed_weighted_response(reference, self.plan, theta, model.lam - step)) / (2 * step)
            np.testing.assert_allclose(jac_a, expected_jac, rtol=2e-8, atol=2e-13)
            np.testing.assert_allclose(lambda_a, expected_lambda, rtol=2e-8, atol=2e-13)
            np.testing.assert_allclose(value_a, value_b, rtol=2e-14, atol=1e-16)
            np.testing.assert_allclose(jac_b[:, 0], jac_a[:, 0], rtol=2e-14, atol=1e-16)
            np.testing.assert_allclose(jac_b[:, 1],
                                       jac_a[:, 1] - math.log(2.0) * jac_a[:, 0],
                                       rtol=2e-14, atol=1e-16)
            np.testing.assert_allclose(lambda_a, lambda_b, rtol=2e-14, atol=1e-16)

    def test_parameter_changes_do_not_trigger_native_queries(self):
        reference = compile_reference_window(self.provider, self.plan)
        before = (self.provider.pdf_calls, self.provider.alpha_calls)
        for theta in ((0.1, 0.0), (0.5, 0.1), (0.27, 0.036)):
            for model in (APPROVED, CONTROL):
                for chart in (Chart("A"), Chart("B")):
                    reference.response(chart.coordinates(theta), chart, model)
        self.assertEqual((self.provider.pdf_calls, self.provider.alpha_calls), before)

    def test_invalid_plan_window_or_grid_fails_before_native_queries(self):
        with self.assertRaisesRegex(ContractError, "plan_provider_mismatch"):
            compile_reference_window(self.provider, dict(self.plan))
        self.plan["b_plans"]["nominal"]["edges_hex"][-1] = (10.0).hex()
        with self.assertRaisesRegex(ContractError, "window_mismatch"):
            compile_reference_window(self.provider, self.plan)
        self.plan["b_plans"]["nominal"]["edges_hex"][-1] = (8.0).hex()
        self.plan["points"][0], self.plan["points"][1] = self.plan["points"][1], self.plan["points"][0]
        with self.assertRaisesRegex(ContractError, "kinematics_mismatch"):
            compile_reference_window(self.provider, self.plan)
        self.assertEqual((self.provider.pdf_calls, self.provider.alpha_calls), (0, 0))

    def test_invalid_scalar_model_fails_before_lazy_native_lookup(self):
        reference = CanonicalReference(self.provider, self.plan)
        counterfeit = SimpleNamespace(coefficient_id="approved", lam=0.8)
        with self.assertRaisesRegex(ContractError, "model_type"):
            reference.tmd(2, 0.2, 0.3, 30.0, (0.25, 0.04), counterfeit)
        self.assertEqual((self.provider.pdf_calls, self.provider.alpha_calls), (0, 0))


if __name__ == "__main__":
    unittest.main()

