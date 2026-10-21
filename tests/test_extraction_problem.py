import math
import unittest

import numpy as np

from typed_tmd.contracts import ContractError
from typed_tmd.extraction import APPROVED, CONTROL, Chart, ObservationTarget
from typed_tmd.extraction_problem import FitProblem, FrozenDataset


def target(q=20., fraction=.025):
    return ObservationTarget(q, q*fraction, q*math.exp(.3)/200., q*math.exp(-.3)/200.)


class CountingResponse:
    def __init__(self, targets, snapshot_id="snapshot-A"):
        self.targets = targets
        self.identity = {"snapshot_id": snapshot_id}
        self.calls = 0

    def response(self, coordinates, chart, model):
        self.calls += 1
        theta = chart.canonical(coordinates)
        values = np.asarray([theta[0]+2*theta[1], 3*theta[0]-theta[1]])
        canonical_jac = np.asarray([[1.,2.],[3.,-1.]])
        return values, canonical_jac@chart.jacobian_to_canonical(), np.zeros(2)


class TypedFitProblemTests(unittest.TestCase):
    def setUp(self):
        self.targets = (target(), target(fraction=.05))
        self.response = CountingResponse(self.targets)
        self.data = FrozenDataset(self.targets, [1.,2.], [.1,.2], "draw-0", "snapshot-A")

    def test_undeclared_coefficient_change_rejected_before_evaluation(self):
        with self.assertRaisesRegex(ContractError, "coefficient_identity"):
            FitProblem(self.response,self.data,Chart("A"),CONTROL)
        self.assertEqual(self.response.calls,0)

    def test_declared_control_comparison_is_distinct_and_executable(self):
        problem = FitProblem(self.response,self.data,Chart("A"),CONTROL,"declared_coefficient_control")
        problem.residual(np.asarray([.3,.4]))
        self.assertEqual(self.response.calls,1)
        self.assertEqual(problem.model,CONTROL)

    def test_changed_provider_rejected_before_evaluation(self):
        wrong = CountingResponse(self.targets,"snapshot-B")
        with self.assertRaisesRegex(ContractError,"snapshot_mismatch"):
            FitProblem(wrong,self.data,Chart("A"),APPROVED)
        self.assertEqual(wrong.calls,0)

    def test_changed_observable_rejected_before_evaluation(self):
        wrong = CountingResponse((target(),target(fraction=.1)))
        with self.assertRaisesRegex(ContractError,"observation_mismatch"):
            FitProblem(wrong,self.data,Chart("A"),APPROVED)
        self.assertEqual(wrong.calls,0)

    def test_reordered_observations_are_not_silently_reinterpreted(self):
        with self.assertRaisesRegex(ContractError,"order_or_duplicate"):
            FrozenDataset(tuple(reversed(self.targets)),[1.,2.],[.1,.2],"draw-0","snapshot-A")

    def test_bad_covariance_and_wrong_beam_x_rejected(self):
        with self.assertRaisesRegex(ContractError,"nonpositive"):
            FrozenDataset(self.targets,[1.,2.],[.1,0.],"draw-0","snapshot-A")
        wrong = ObservationTarget(20.,.5,.7,.8)
        with self.assertRaisesRegex(ContractError,"beam_kinematics"):
            FrozenDataset((wrong,),[1.],[.1],"draw-0","snapshot-A")

    def test_dataset_copies_input_and_remains_immutable(self):
        values = np.asarray([1.,2.])
        data = FrozenDataset(self.targets,values,[.1,.2],"draw-0","snapshot-A")
        values[0] = 99.
        self.assertEqual(data.values[0],1.)
        with self.assertRaises(ValueError):
            data.values.setflags(write=True)

    def test_chart_chain_rule_reaches_same_residual_and_solver_jacobian(self):
        A = FitProblem(self.response,self.data,Chart("A"),APPROVED)
        B = FitProblem(self.response,self.data,Chart("B"),APPROVED)
        u = np.asarray([.3,.4])
        np.testing.assert_allclose(A.residual(u),B.residual(u),rtol=0,atol=1e-14)
        np.testing.assert_allclose(A.residual_jacobian(u),B.residual_jacobian(u),rtol=0,atol=1e-14)
        h = 1e-6
        finite = np.column_stack([(B.residual(u+np.eye(2)[k]*h)-B.residual(u-np.eye(2)[k]*h))/(2*h)
                                  for k in range(2)])
        np.testing.assert_allclose(B.residual_jacobian(u),finite,rtol=1e-8,atol=1e-8)


if __name__ == "__main__":
    unittest.main()
