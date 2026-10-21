"""Scientific contract checks for the H003 parameter charts and evaluator."""
import math
import unittest

import numpy as np

from typed_tmd.contracts import ContractError
from typed_tmd.extraction import APPROVED, CONTROL, Chart, CompiledWindow, ModelTemplate, ObservationTarget


class ExtractionContractTests(unittest.TestCase):
    def test_chart_roundtrip_and_slanted_domain(self):
        theta = np.array([0.25, 0.04])
        beta = Chart("B").coordinates(theta)
        np.testing.assert_allclose(Chart("B").canonical(beta), theta, atol=1e-15)
        self.assertAlmostEqual(beta[0], 0.25 + 0.04 * math.log(2))
        with self.assertRaisesRegex(ContractError, "mapped_domain"):
            Chart("B").canonical([0.1, 0.1])

    def test_coefficients_cannot_masquerade_as_compatible(self):
        with self.assertRaisesRegex(ContractError, "coefficient_identity_mismatch"):
            APPROVED.compatible_with(CONTROL)
        with self.assertRaisesRegex(ContractError, "coefficient_identity_mismatch"):
            ModelTemplate("approved", 0.8)

    def test_signed_response_and_chart_derivative(self):
        targets = tuple(ObservationTarget(20, q, .13, .07) for q in (.5, 1., 2.))
        b = np.array([0.2, 0.6])
        compiled = CompiledWindow(targets, b, np.ones((3, 2)),
                                  np.array([[1., -0.1]] * 3),
                                  np.broadcast_to(b*b, (3, 2)),
                                  np.broadcast_to(np.array([.7, .9]), (3, 2)),
                                  np.broadcast_to(np.array([.1, .2]), (3, 2)))
        t = np.array([.25, .04])
        A, ja, _ = compiled.response(t, Chart("A"), APPROVED)
        B, jb, _ = compiled.response(Chart("B").coordinates(t), Chart("B"), APPROVED)
        np.testing.assert_allclose(A, B, rtol=1e-14)
        np.testing.assert_allclose(jb[:, 0], ja[:, 0])
        np.testing.assert_allclose(jb[:, 1], ja[:, 1]-math.log(2)*ja[:, 0])
        self.assertTrue(np.all(np.isfinite(A)))

    def test_target_rejects_wrong_measure(self):
        with self.assertRaisesRegex(ContractError, "unsupported_observation_target"):
            ObservationTarget(20, .5, .13, .07, measure="dqT")


if __name__ == "__main__":
    unittest.main()
