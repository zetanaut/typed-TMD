"""Focused tests of scientific failure modes, not an extraction validation."""

from dataclasses import FrozenInstanceError, replace
import importlib.util
import math
import unittest

from typed_tmd import (
    AccuracySpec, CoefficientOrders, ContractError, ContextMismatchError,
    DomainCompatibilityError, DomainViolationError, DYKinematics, DYTerm,
    EvolutionConsistencyError, EvolutionGenerators, GaussianParameters,
    InventoryMismatchError, LHAPDFProvider, Polynomial, ScalePoint,
    SyntheticGaussianModel, describe_expression, gaussian_fourier_analytic,
    radial_fourier, require_compatible,
)


class ContextContractTests(unittest.TestCase):
    def setUp(self):
        self.model = SyntheticGaussianModel()
        self.A = ScalePoint(2, 4)
        self.B = ScalePoint(4, 16)
        self.T = ScalePoint(5, 25)

    def test_context_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.model.context.process = "sidis"

    def test_invalid_scales_and_domain_are_rejected(self):
        for mu, zeta in ((0, 4), (2, -1), (math.inf, 4), (2, math.nan)):
            with self.assertRaises(ContractError):
                ScalePoint(mu, zeta)
        with self.assertRaises(DomainViolationError):
            self.model.dy_expression(DYKinematics(5, 1.01, 0.2, 0.3))
        with self.assertRaises(DomainViolationError):
            self.model.evaluate(self.model.reference(2), 0.2, -0.1)

    def test_wrong_endpoint_is_rejected(self):
        boundary = self.model.reference(2)
        with self.assertRaises(ContractError):
            self.model.evolution(self.B, self.T).apply(boundary)
        with self.assertRaises(ContractError):
            self.model.evolution(self.A, self.B).compose(self.model.evolution(self.A, self.T))

    def test_convention_and_definition_mismatches_are_rejected(self):
        base = self.model.evolution(self.A, self.T)
        contexts = (
            replace(self.model.context, conventions=replace(self.model.context.conventions, provider_quantity="xf")),
            replace(self.model.context, definition=replace(self.model.context.definition, rapidity_scheme="another")),
        )
        for context in contexts:
            with self.assertRaises(ContextMismatchError):
                replace(base, context=context).apply(self.model.reference(2))

    def test_different_domains_are_not_silently_intersected(self):
        narrow = replace(self.model.context.domain, x_min=0.1)
        transport = replace(self.model.evolution(self.A, self.T),
                            context=replace(self.model.context, domain=narrow))
        with self.assertRaises(DomainCompatibilityError):
            transport.apply(self.model.reference(2))

    def test_perturbative_inventory_mismatch_is_not_a_conversion(self):
        # Metadata-only examples: the synthetic evaluator never executes these.
        inventory = CoefficientOrders(H=1, C=1, K=2, gamma=2, cusp=3, P=2, beta=3)
        accuracy = AccuracySpec("perturbative_manifest", "metadata test only", "alpha_s/(4*pi)", inventory)
        first = replace(self.model.context, accuracy=accuracy)
        second = replace(first, accuracy=replace(accuracy, coefficients=replace(inventory, C=2)))
        with self.assertRaises(InventoryMismatchError):
            require_compatible(first, second)

    def test_synthetic_evaluator_refuses_qcd_labels(self):
        qcd = replace(self.model.context, definition=replace(self.model.context.definition,
                      name="QCD-TMD", operator="renormalized bilocal quark operator"))
        with self.assertRaises(ContractError):
            SyntheticGaussianModel(context=qcd)
        with self.assertRaises(ContractError):
            AccuracySpec(coefficients=CoefficientOrders(H=0))

    def test_dy_rejects_wrong_flavor_or_rapidity_partition(self):
        def leg(pid, scale):
            return self.model.evolution(self.A, scale).apply(self.model.reference(pid))
        with self.assertRaises(ContractError):
            DYTerm(leg(1, self.T), leg(-2, self.T), -1 / 3, 5)
        with self.assertRaises(ContractError):
            DYTerm(leg(1, self.T), leg(-1, ScalePoint(5, 16)), -1 / 3, 5)


class SymbolicTransportTests(unittest.TestCase):
    def setUp(self):
        self.model = SyntheticGaussianModel()
        self.A, self.B, self.T = ScalePoint(2, 4), ScalePoint(4, 16), ScalePoint(5, 25)

    def test_symbolic_generators_match_independent_closed_forms(self):
        u, v, b = 0.37, 0.83, 1.7
        p = self.model.parameters
        generators = self.model.generators
        self.assertTrue(generators.curvature.is_zero)
        self.assertAlmostEqual(generators.gamma.evaluate(u=u, v=v, b=b), p.gamma0 + p.gamma_K * (u - v))
        self.assertAlmostEqual(generators.kernel.evaluate(u=u, v=v, b=b), -p.gamma_K * u - p.g2_GeV2 * b * b)
        # Numerical differentiation checks that the evaluator and derivative AST agree.
        step = 1e-5
        f = self.model.potential
        numerical = (f.evaluate(u=u + step, v=v, b=b) - f.evaluate(u=u - step, v=v, b=b)) / (2 * step)
        self.assertAlmostEqual(numerical, generators.gamma.evaluate(u=u, v=v, b=b), places=9)

    def test_inconsistent_generator_is_detected_exactly(self):
        generators = self.model.generators
        bad_kernel = generators.kernel + Polynomial.from_terms((("0.01", (1, 0, 0)),))
        bad = EvolutionGenerators(generators.gamma, bad_kernel)
        self.assertFalse(bad.curvature.is_zero)
        with self.assertRaises(EvolutionConsistencyError):
            bad.require_exact_flatness()

    def test_transport_rebase_and_inverse_close(self):
        reference = self.model.reference(2)
        rebased = self.model.boundary_transport(self.B).apply(reference)
        direct = self.model.evolution(self.A, self.T).apply(reference)
        via = self.model.evolution(self.B, self.T).apply(rebased)
        inverse = self.model.evolution(self.T, self.A).apply(direct)
        composed = self.model.evolution(self.B, self.T).compose(self.model.evolution(self.A, self.B)).apply(reference)
        for b in (0, 0.4, 1.3, 3.2):
            target = self.model.evaluate(direct, 0.2, b)
            self.assertAlmostEqual(target, self.model.evaluate(via, 0.2, b), places=13)
            self.assertAlmostEqual(target, self.model.evaluate(composed, 0.2, b), places=13)
            self.assertAlmostEqual(self.model.evaluate(reference, 0.2, b), self.model.evaluate(inverse, 0.2, b), places=13)
        tree = describe_expression(via)
        self.assertEqual(tree["operand"]["node"], "TransportedBoundary")
        self.assertEqual(tree["operand"]["operand"]["model_id"], reference.model_id)
        history = describe_expression(composed)["transport"]["components_in_application_order"]
        self.assertEqual(history[0]["target"], {"mu_GeV": 4.0, "zeta_GeV2": 16.0})
        self.assertEqual(history[1]["source"], history[0]["target"])

    def test_legitimate_model_difference_is_allowed_and_preserved(self):
        other = SyntheticGaussianModel(parameters=replace(self.model.parameters, width_GeV2=0.35))
        require_compatible(self.model.context, other.context)
        self.assertEqual(self.model.evolution_id, other.evolution_id)
        self.assertNotEqual(self.model.model_id, other.model_id)
        point = DYKinematics(5, 0.5, 0.2, 0.3)
        first = self.model.dy_analytic(self.model.dy_expression(point))
        second = other.dy_analytic(other.dy_expression(point))
        self.assertGreater(abs(first - second), 1e-4)
        with self.assertRaises(ContractError):
            self.model.evaluate(other.reference(2), 0.2, 1)


class NumericalPhysicsFixtureTests(unittest.TestCase):
    def setUp(self):
        self.model = SyntheticGaussianModel()
        self.point = DYKinematics(5, 0.5, 0.2, 0.3)

    def test_flavor_sum_and_gaussian_against_independent_formula(self):
        expression = self.model.dy_expression(self.point)
        self.assertEqual(len(expression.terms), 4)  # two flavors, both beam orderings
        h = lambda x: x ** 0.3 * (1 - x) ** 3
        luminosity = (68 / 45) * h(0.2) * h(0.3)
        L = math.log(2.5)
        width = 2 * (0.25 + 0.04 * L)
        amplitude = luminosity * math.exp(0.36 * L - 0.24 * L * L)
        expected = amplitude / (4 * math.pi * width) * math.exp(-0.25 / (4 * width))
        self.assertAlmostEqual(self.model.dy_analytic(expression), expected, places=14)
        self.assertAlmostEqual(expected, 0.016147803424369757, places=14)
        for b in (0, 0.7, 2):
            self.assertAlmostEqual(self.model.dy_b_space(expression, b), amplitude * math.exp(-width * b * b), places=13)

    def test_off_canonical_mu_and_rapidity_partition_cancel(self):
        base = self.model.dy_expression(self.point)
        altered = self.model.dy_expression(self.point, mu_GeV=7,
                                          zeta_a_GeV2=25 * math.exp(0.6), via_boundary=ScalePoint(4, 16))
        for b in (0, 0.7, 2):
            self.assertAlmostEqual(self.model.dy_b_space(base, b), self.model.dy_b_space(altered, b), places=13)

    def test_standard_library_fourier_is_independent_of_closed_form(self):
        amplitude, width, k = 1.7, 0.6, 0.4
        result = radial_fourier(lambda b: amplitude * math.exp(-width * b * b), k,
                                bound_amplitude=amplitude, bound_width_GeV2=width,
                                abs_tol=1e-9, rel_tol=1e-7, backend="stdlib")
        expected = gaussian_fourier_analytic(amplitude, width, k)
        self.assertLess(abs(result.value - expected), 1e-8)
        self.assertEqual(result.backend, "stdlib_simpson_angular_j0")

    def test_full_dy_transform_closes_with_standard_library(self):
        expression = self.model.dy_expression(self.point, via_boundary=ScalePoint(4, 16))
        result = self.model.dy_numerical(expression, abs_tol=1e-9, rel_tol=1e-7, backend="stdlib")
        self.assertLess(abs(result.value - self.model.dy_analytic(expression)), 2e-9)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "Optional SciPy is not installed")
    def test_scipy_transform_matches_the_independent_analytic_result(self):
        expression = self.model.dy_expression(self.point)
        result = self.model.dy_numerical(expression, abs_tol=1e-10, rel_tol=1e-8, backend="scipy")
        self.assertLess(abs(result.value - self.model.dy_analytic(expression)), 2e-10)

    def test_finite_b_domain_cannot_claim_an_infinite_transform(self):
        context = replace(self.model.context, domain=replace(self.model.context.domain, b_max_GeV_inv=4))
        model = SyntheticGaussianModel(context=context)
        with self.assertRaises(ContractError):
            model.dy_numerical(model.dy_expression(self.point))

    def test_analytic_evaluator_rejects_invalid_boundary_and_rapidity_scale(self):
        invalid_partition = self.model.dy_expression(self.point, zeta_a_GeV2=4 * math.exp(-20))
        with self.assertRaises(ContractError):
            self.model.dy_analytic(invalid_partition)
        original = self.model.dy_expression(self.point)
        term = original.terms[0]
        fake_boundary = replace(self.model.reference(term.left.flavor), scale=term.left.scale)
        wrong = replace(original, terms=(replace(term, left=fake_boundary),))
        with self.assertRaises(ContractError):
            self.model.dy_analytic(wrong)


class ProviderTests(unittest.TestCase):
    def test_lhapdf_q2_only_bounds_convert_to_q_and_reject_extrapolation(self):
        class Q2OnlyPDF:
            xMin, xMax = 0.01, 0.99
            q2Min, q2Max = 4.0, 100.0

            def flavors(self):
                return [2]

            def xfxQ(self, pid, x, mu):
                return x * (pid + mu)

        provider = LHAPDFProvider.from_object(Q2OnlyPDF(), "q2-only-grid")
        self.assertEqual(provider.support.q_min_GeV, 2.0)
        self.assertEqual(provider.support.q_max_GeV, 10.0)
        self.assertEqual(provider.f(2, 0.2, 5.0), 7.0)
        for q in (1.99, 10.01):
            with self.assertRaises(ContractError):
                provider.f(2, 0.2, q)

    def test_lhapdf_adapter_divides_xfxq_by_x_exactly_once(self):
        class FakeNativePDF:
            xMin, xMax = 0.01, 0.99
            qMin, qMax = 1.0, 100.0

            def flavors(self):
                return [-2, -1, 1, 2, 21]

            def __init__(self):
                self.calls = []

            def xfxQ(self, pid, x, mu):
                self.calls.append((pid, x, mu))
                return x * (pid + mu)

        native = FakeNativePDF()
        provider = LHAPDFProvider.from_object(native, "test-double-not-LHAPDF-data")
        self.assertEqual(provider.quantity, "f")
        self.assertAlmostEqual(provider.f(2, 0.2, 5), 7)
        self.assertEqual(native.calls, [(2, 0.2, 5.0)])
        with self.assertRaises(ContractError):
            provider.f(2, 0, 5)
        for pid, x, mu in ((3, 0.2, 5), (2, 0.001, 5), (2, 0.2, 101)):
            with self.assertRaises(ContractError):
                provider.f(pid, x, mu)
        self.assertTrue(provider.support.known)

    def test_unknown_lhapdf_support_requires_explicit_opt_in_and_f_is_finite(self):
        class UnknownSupport:
            def xfxQ(self, pid, x, mu):
                return 1.0

        provider = LHAPDFProvider.from_object(UnknownSupport(), "unknown-support-test")
        self.assertFalse(provider.support.known)
        with self.assertRaises(ContractError):
            provider.f(2, 0.2, 5)
        permitted = LHAPDFProvider.from_object(UnknownSupport(), "unknown-support-test", allow_unknown_support=True)
        self.assertIn("explicitly_allowed", permitted.support_policy)
        self.assertEqual(permitted.f(2, 0.2, 5), 5)
        with self.assertRaises(ContractError):
            permitted.f(2, 1e-320, 5)


if __name__ == "__main__":
    unittest.main()
