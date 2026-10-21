"""Analytic adapter fixtures; these tests do not execute an external engine."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import unittest

from typed_tmd.contracts import ContractError
from typed_tmd.observations import DYBin, ObservationContract, ObservationMismatch, ObservedFitProblem, convert_averages

try:
    import numpy as np
    from typed_tmd.artemide_adapter import ArtemideSession
except ImportError:
    np = None


class PolynomialNative:
    """h(q,Q,y) = 1+c0*q^2, differential in dq^2 dQ^2 dy."""
    def __init__(self):
        self.DY = self
        self.count = 0
        self.parameters = None

    def setNPparameters(self, values):
        self.parameters = values

    def xSec(self, process, s, qt, mass, rapidity, cuts, cut_params):
        self.count += 1
        a, b = qt
        return ((b*b-a*a)+self.parameters[1]/2*(b**4-a**4)) * (mass[1]**2-mass[0]**2) * (rapidity[1]-rapidity[0])

    def xSecListBINLESS(self, process, s, qt, mass, rapidity, cuts, cut_params):
        self.count += 1
        return 1+self.parameters[1]*np.asarray(qt)**2


@unittest.skipUnless(np is not None, "NumPy required for analytic adapter fixtures")
class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.native = PolynomialNative()
        self.session = ArtemideSession(self.native, "fixture-source", (1., .03, .2, 9., 347., 2.5, -5.7, 0., 0.), (.001, .1),
                                       orders=(5, 5, 4), mass_breaks=())
        self.row = DYBin("fixture", (0., 2.), (3., 5.), (-.5, .5), 10000., (1, 1, 5), False, (0., 0., 0., 0.), 2.)
        self.contract = ObservationContract((self.row,), self.session.identity)

    def test_same_units_point_refused_before_backend_or_optimizer(self):
        point = self.session.plan(self.contract, operation="qT_point_density")
        self.assertEqual(point.meaning.units, self.contract.units)
        with self.assertRaises(ObservationMismatch) as error:
            ObservedFitProblem(self.contract, point, (10.,), (1.,))
        self.assertEqual(error.exception.diagnostic["stage"], "fit_problem_construction")
        self.assertEqual(self.native.count, 0)
        self.assertTrue(all(n == 0 for n in self.session.calls.values()))

    def test_corrected_and_independent_quadrature_recover_exact_yield(self):
        correct = self.session.plan(self.contract)
        reference = self.session.plan(self.contract, operation="independent_bin_average")
        truth = (64. + 128.*.03,)
        self.assertTrue(np.allclose(correct.evaluate((.03,)), truth, rtol=1e-13))
        self.assertTrue(np.allclose(reference.evaluate((.03,)), truth, rtol=1e-13))
        fit = ObservedFitProblem(self.contract, correct, truth, (.2,))
        self.assertLess(abs(fit.residuals((.03,))[0]), 1e-12)
        self.assertGreater(abs(fit.residuals((.05,))[0]), 1.)

    def test_native_parameter_change_and_reset_has_no_stale_values(self):
        plan = self.session.plan(self.contract)
        first, changed, reset = [plan.evaluate((v,)) for v in (.02, .06, .02)]
        self.assertNotEqual(first, changed)
        self.assertEqual(first, reset)
        self.assertEqual(plan.parameter_dependencies, ("SV19.c0",))

    def test_provider_invalidation_precedes_backend_calls(self):
        plan = self.session.plan(self.contract)
        self.session.invalidate("provider identity changed")
        with self.assertRaisesRegex(ContractError, "Stale native state"):
            plan.evaluate((.03,))
        self.assertEqual(self.native.count, 0)
        self.assertEqual(self.session.calls["parameter_sets"], 0)

    def test_two_sessions_cannot_race_process_global_native_parameters(self):
        entered, release = Event(), Event()
        original = self.native.xSec

        def held_call(*args):
            if not entered.is_set():
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("Fixture release timed out")
            return original(*args)

        self.native.xSec = held_call
        other = ArtemideSession(self.native, "fixture-source", (1., .03, .2, 9., 347., 2.5, -5.7, 0., 0.), (.001, .1))
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.session.plan(self.contract).evaluate, (.02,))
            self.assertTrue(entered.wait(2))
            second = pool.submit(other.plan(self.contract).evaluate, (.06,))
            time.sleep(.02)
            release.set()
            a, b = first.result(), second.result()
        self.assertAlmostEqual(a[0], 64.+128.*.02, places=10)
        self.assertAlmostEqual(b[0], 64.+128.*.06, places=10)

    def test_fixed_parameter_change_has_distinct_identity(self):
        changed = ArtemideSession(self.native, "fixture-source", (1., .03, .3, 9., 347., 2.5, -5.7, 0., 0.), (.001, .1))
        self.assertNotEqual(changed.identity, self.session.identity)
        with self.assertRaisesRegex(ContractError, "identity differs"):
            changed.plan(self.contract)
        other = ObservationContract((self.row,), changed.identity)
        ObservedFitProblem(other, changed.plan(other), (10.,), (1.,))

    def test_bin_splitting_and_average_conversion(self):
        one = self.session.plan(self.contract).evaluate((.03,))[0]
        rows = (replace(self.row, name="left", qT=(0., .7)), replace(self.row, name="right", qT=(.7, 2.)))
        split = ObservationContract(rows, self.session.identity)
        values = self.session.plan(split, operation="independent_bin_average").evaluate((.03,))
        self.assertAlmostEqual(one*2, values[0]*.7+values[1]*1.3, places=10)
        target = replace(split, measure="dqT2")
        mapped = convert_averages(values, split, target)
        self.assertTrue(np.allclose(mapped, self.session.plan(target).evaluate((.03,)), rtol=1e-13))
        self.assertTrue(np.allclose(convert_averages(mapped, target, split), values, rtol=1e-13))

    def test_observation_covariance_requires_same_linear_map_as_data(self):
        rows = (self.row, replace(self.row, name="wide", qT=(2., 5.)))
        source = ObservationContract(rows, self.session.identity)
        target = replace(source, measure="dqT2")
        prediction = np.array(self.session.plan(source).evaluate((.03,)))
        data = prediction + np.array([.5, -2.])
        covariance = np.array([[1., .2], [.2, 4.]])
        factors = np.array(convert_averages((1., 1.), source, target))
        transformed = covariance * factors[:, None] * factors[None, :]
        residual = prediction-data
        original = residual @ np.linalg.solve(covariance, residual)
        mapped = factors*residual
        self.assertAlmostEqual(original, mapped @ np.linalg.solve(transformed, mapped), places=12)
        self.assertNotAlmostEqual(original, mapped @ np.linalg.solve(covariance, mapped), places=5)

    def test_invalid_geometry_and_unsupported_maps_fail(self):
        with self.assertRaises(ContractError):
            replace(self.row, qT=(2., 1.))
        with self.assertRaises(ContractError):
            replace(self.contract, measure="d2qT")
        other = replace(self.contract, bins=(replace(self.row, qT=(1., 2.)),))
        with self.assertRaises(ContractError):
            convert_averages((1.,), self.contract, other)

    def test_plan_retains_numerical_settings_and_data_cannot_mutate(self):
        plan = self.session.plan(self.contract)
        record = plan.record()
        self.session.orders = (10, 10, 8)
        self.assertEqual(record, plan.record())
        self.assertNotEqual(record["plan_identity"], self.session.plan(self.contract).record()["plan_identity"])
        values, errors = [1.], [2.]
        fit = ObservedFitProblem(self.contract, plan, values, errors)
        values[0], errors[0] = 100., -1.
        self.assertEqual(fit.data, (1.,))
        self.assertEqual(fit.sigma, (2.,))
