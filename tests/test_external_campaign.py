"""Analytic inference controls; not evidence of external backend execution."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from typed_tmd.observations import DYBin, ObservationContract, ResponsePlan
try:
    import numpy as np
    from external_campaign_006 import fit_case
except ImportError:
    np = None


@unittest.skipUnless(np is not None, "NumPy/SciPy required for analytic inference control")
class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.contract = ObservationContract(tuple(DYBin(str(i), (float(i), float(i+1)), (3., 5.),
            (0., .4), 10000., (1, 1, 5), False, (0., 0., 0., 0.)) for i in range(3)), "analytic")
        self.plan = ResponsePlan(self.contract.expected, "analytic linear family", ("c0",), "analytic", 0,
            (), "analytic fixture", lambda theta: tuple(theta[0]*k for k in (1., 2., 3.)))
        self.spec = {"domain": [.001, .1], "start_fractions": [.125, .25, .5, .75, .875],
            "jacobian_chart_step": .001, "bound_fraction_tolerance": 1e-5,
            "solver_options": {"ftol": 1e-9, "xtol": 1e-9, "gtol": 1e-9, "max_nfev": 50}}

    def test_known_misspecified_linear_fit_shift_and_repair(self):
        data = np.array(self.plan.evaluate((.03,)));sigma = np.full(3, .01)
        fault = replace(self.plan, meaning=replace(self.plan.meaning, kind="point_density"),
                        evaluator=lambda theta: tuple((theta[0]+.01)*k for k in (1., 2., 3.)))
        correct = fit_case(self.plan, self.contract, data, sigma, self.spec)
        unchecked = fit_case(fault, self.contract, data, sigma, self.spec, unchecked=True)
        self.assertTrue(correct["all_starts_successful"] and unchecked["all_starts_successful"])
        self.assertAlmostEqual(correct["selected"]["c0"], .03, places=7)
        self.assertAlmostEqual(unchecked["selected"]["c0"], .02, places=7)
        self.assertLess(correct["selected"]["chi2"], 1e-12)
        self.assertEqual(len(correct["starts"]), 5)

    def test_failed_starts_remain_available_as_failures(self):
        spec = {**self.spec, "solver_options": {"max_nfev": 1}}
        result = fit_case(self.plan, self.contract, np.array([.03, .06, .09]), np.full(3, .01), spec)
        self.assertFalse(result["all_starts_successful"])
        self.assertFalse(result["selected"]["success"])
        self.assertIsNone(result["successful_start_chi2_range"])
        self.assertTrue(all(row["history"] for row in result["starts"]))
