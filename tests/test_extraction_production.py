"""Constant-coupling analytic fixtures for the parameterized production routes.

These are software/transport tests with invented signed PDFs, not a native QCD
comparison.  The fixture's closed exponent is independent of the transport code.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import math
import unittest

import numpy as np
from scipy.special import j0

from typed_tmd.contracts import ContractError, ScalePoint
from typed_tmd.expressions import describe_expression
from typed_tmd.extraction import APPROVED, CONTROL, Chart, ModelTemplate
from typed_tmd.extraction_production import (A, B, ParameterizedProduction,
                                           compile_production_window, gamma_F)
from typed_tmd.provider_replay import digest
from typed_tmd.qcd_plan import profile_mu


class FixtureProvider:
    """Finite metadata plus analytic samples; deliberately no native-library claim."""
    quantity = "f"
    identifier = "signed-test-fixture-only"
    snapshot_id = "fixture-snapshot-1"

    def __init__(self, mutate=None):
        self.calls = []
        bounds = {"x_min": 1e-9, "x_max": 1., "q_min": 1., "q_max": 1e6,
                  "alpha_min": 1., "alpha_max": 1e6}
        ip = {"set": "analytic-test-fixture", "member": 0, "flavors": [-3,-2,-1,1,2,3],
              "bounds": {key: value.hex() for key,value in bounds.items()},
              "effective": {"OrderQCD": {"value": "fixture"}, "AlphaS_OrderQCD": {"value": "fixture"}},
              "files": {"set_info": {"sha256": "a"*64}, "member_data": {"sha256": "b"*64}},
              "alpha_table_sha256": "c"*64}
        self.inspection = {"payload": ip, "payload_sha256": digest(ip)}
        points = []
        for Q in (20., 40., 30.):
            for r in (.025, .05, .1):
                point = {"Q_GeV": Q, "qT_GeV": Q*r,
                         "x_a": Q*math.exp(.3)/200, "x_b": Q*math.exp(-.3)/200}
                points.append({key: value.hex() for key,value in point.items()})
        bs = (.2, .6, 1.4)
        scales = {5., 10., 20., 30., 40.}
        scales.update(profile_mu(b) for b in (*bs, .1, .25, .5, 1., 2.))

        def panel(mu):
            t = math.log(mu)
            return [[math.exp(t/2).hex(), t.hex(), (t/2).hex()]]

        scale = {"full": [{"nodes": panel(1e6)}],
                 "partial": {mu.hex(): {"lower_knot_index": 0, "nodes": panel(mu)} for mu in scales}}
        nodes = [[b.hex(), w.hex()] for b,w in zip(bs, (1., 2., 4.9999))]
        plan = {"provider_id": self.identifier, "set": ip["set"], "member": 0,
                "inspection_sha256": self.inspection["payload_sha256"], "points": points,
                "alpha_knots_hex": [1.0.hex(), (1e6).hex()],
                "scale_plans": {"P16": deepcopy(scale), "P32": deepcopy(scale)},
                "b_plans": {"nominal": {"edges_hex": [.0001.hex(), 8.0.hex()],
                                            "variants": {"P16": deepcopy(nodes), "P32": deepcopy(nodes)}}}}
        if mutate:
            mutate(plan)
        self.plan = {"schema": "typed_tmd.provider_query_plan.v1", "payload": plan,
                     "payload_sha256": digest(plan)}

    @staticmethod
    def value(pid, x, mu):
        normalization = {-3: -.3, -2: .4, -1: .2, 1: 2., 2: 4., 3: .5}[pid]
        return normalization * x**.3 * (1-x)**3 * (1+.025*math.log(mu))

    def f(self, pid, x, mu_GeV):
        self.calls.append(("f", pid, x, mu_GeV))
        return self.value(pid, x, mu_GeV)

    def alpha_s(self, mu_GeV):
        self.calls.append(("alpha_s", mu_GeV))
        return .2


def scalar_truth(pid, x, b, Q, theta, model):
    """Closed constant-coupling expression, independent of all moment classes."""
    a,g = theta
    mu = profile_mu(b)
    L = math.log(Q/mu)
    c = (4/3)*.2/math.pi
    exponent = c*(1.5*model.lam*L-L*L)-a*b*b-g*b*b*L
    return FixtureProvider.value(pid,x,mu)*math.exp(exponent)


class ProductionRouteTests(unittest.TestCase):
    def setUp(self):
        self.provider = FixtureProvider()
        self.plan = self.provider.plan["payload"]
        self.direct = ParameterizedProduction(self.provider,self.plan)

    def test_direct_signed_tmd_and_real_expression_history(self):
        x = 30.*math.exp(.3)/200
        for theta in ((.25,.04),(.15,.08),(.45,.02)):
            for model in (APPROVED,CONTROL):
                for route in ("A","B"):
                    chart = Chart(route)
                    coords = chart.coordinates(theta)
                    actual = self.direct.tmd(-3,x,.6,30.,coords,chart,model)
                    expected = scalar_truth(-3,x,.6,30.,theta,model)
                    self.assertLess(actual,0)
                    self.assertAlmostEqual(actual/expected,1.,places=12)
        ea,eb=self.direct.target_expressions(2,.6,30.,(.25,.04),Chart("A"),APPROVED)
        a,b=describe_expression(ea),describe_expression(eb)
        self.assertEqual(a["operand"]["boundary_id"],"A")
        self.assertEqual(b["operand"]["boundary_id"],"B")
        self.assertEqual(b["operand"]["operand"]["boundary_id"],"A")
        self.assertNotEqual(ea.transport.source,eb.transport.source)

    def test_log_transport_paths_composition_and_changing_kernel(self):
        target=ScalePoint(30.,900.)
        for theta in ((.25,.04),(.15,.08)):
            coords=Chart("B").coordinates(theta)
            for model in (APPROVED,CONTROL):
                one=self.direct.log_transport(.6,A,target,coords,Chart("B"),model)
                other=self.direct.log_transport(.6,A,target,coords,Chart("B"),model,"mu_first")
                split=(self.direct.log_transport(.6,A,B,coords,Chart("B"),model)+
                       self.direct.log_transport(.6,B,target,coords,Chart("B"),model))
                self.assertAlmostEqual(one,other,places=13)
                self.assertAlmostEqual(one,split,places=13)
        lo=self.direct.log_transport(.6,A,B,(.25,.02),Chart("A"),APPROVED)
        hi=self.direct.log_transport(.6,A,B,(.25,.08),Chart("A"),APPROVED)
        self.assertAlmostEqual(hi-lo,-.06*.6**2*math.log(2),places=14)

    def test_compiled_routes_match_uncached_typed_and_scalar_oracles(self):
        cache=compile_production_window(self.provider,self.plan,b_variant="P32",scale_variant="P32")
        for theta in ((.25,.04),(.15,.08),(.45,.02)):
            for model in (APPROVED,CONTROL):
                for route in ("A","B"):
                    chart=Chart(route);coords=chart.coordinates(theta)
                    actual=cache.response(coords,chart,model)[0]
                    direct=[];scalar=[]
                    for target in cache.targets:
                        total_typed=total_scalar=0.
                        for b_h,w_h in self.plan["b_plans"]["nominal"]["variants"]["P32"]:
                            b,w=float.fromhex(b_h),float.fromhex(w_h)
                            typed=analytic=0.
                            for pid,charge in ((1,1/9),(2,4/9),(3,1/9)):
                                for left,right in ((pid,-pid),(-pid,pid)):
                                    typed+=charge*self.direct.tmd(left,target.x_a,b,target.Q_GeV,coords,chart,model)*self.direct.tmd(right,target.x_b,b,target.Q_GeV,coords,chart,model)
                                    analytic+=charge*scalar_truth(left,target.x_a,b,target.Q_GeV,theta,model)*scalar_truth(right,target.x_b,b,target.Q_GeV,theta,model)
                            kernel=w*b*float(j0(b*target.qT_GeV))/(2*math.pi)
                            total_typed+=kernel*typed;total_scalar+=kernel*analytic
                        direct.append(total_typed);scalar.append(total_scalar)
                    np.testing.assert_allclose(actual,direct,rtol=3e-12,atol=1e-15)
                    np.testing.assert_allclose(actual,scalar,rtol=3e-12,atol=1e-15)

    def test_chart_jacobian_and_control_are_executable(self):
        cache=compile_production_window(self.provider,self.plan,b_variant="P32",scale_variant="P32")
        for model in (APPROVED,CONTROL):
            for route in ("A","B"):
                chart=Chart(route);coords=chart.coordinates((.3,.05))
                values,jac,jlam=cache.response(coords,chart,model)
                fd=np.column_stack([(cache.response(coords+np.eye(2)[i]*1e-6,chart,model)[0]-
                                     cache.response(coords-np.eye(2)[i]*1e-6,chart,model)[0])/(2e-6) for i in range(2)])
                np.testing.assert_allclose(jac,fd,rtol=2e-7,atol=1e-12)
                self.assertTrue(np.all(np.isfinite(jlam)))
        baseline=cache.response((.3,.05),Chart("A"),APPROVED)[0]
        changed=cache.response((.3,.05),Chart("A"),CONTROL)[0]
        self.assertGreater(float(np.linalg.norm(baseline-changed)),1e-7)
        expected=(4/3)*.2/math.pi*(1.5*.8-math.log(100./25.))
        self.assertAlmostEqual(gamma_F(.2,5.,100.,CONTROL),expected,places=15)

    def test_invalid_bound_expression_and_point_precede_provider_access(self):
        x=30.*math.exp(.3)/200
        with self.assertRaises(ContractError):
            self.direct.tmd(2,x,.6,30.,(.1,.1),Chart("B"),APPROVED)
        with self.assertRaises(ContractError):
            self.direct.tmd(4,x,.6,30.,(.25,.04),Chart("A"),APPROVED)
        with self.assertRaises(ContractError):
            self.direct.tmd(2,.2,.6,30.,(.25,.04),Chart("A"),APPROVED)
        with self.assertRaises(ContractError):
            self.direct.tmd(2,x,.6,30.,(.25,.04),Chart("A"),ModelTemplate("approved",True))
        expr=self.direct.target_expressions(2,.6,30.,(.25,.04),Chart("A"),APPROVED)[0]
        altered_boundary=replace(expr.operand.operand,model_id="foreign-model")
        altered=replace(expr,operand=replace(expr.operand,operand=altered_boundary))
        with self.assertRaisesRegex(ContractError,"identity_mismatch"):
            self.direct.evaluate(altered,x,.6,(.25,.04),Chart("A"),APPROVED)
        self.assertEqual(self.provider.calls,[])

    def test_grid_window_and_plan_contracts_precede_provider_access(self):
        changes=(lambda p:p["points"].reverse(),
                 lambda p:p["points"][0].__setitem__("x_a",.2.hex()),
                 lambda p:p["points"].append(deepcopy(p["points"][0])),
                 lambda p:p["b_plans"]["nominal"]["edges_hex"].__setitem__(0,.001.hex()))
        for mutate in changes:
            provider=FixtureProvider(mutate)
            with self.assertRaises(ContractError):
                compile_production_window(provider,provider.plan["payload"],b_variant="P32",scale_variant="P32")
            self.assertEqual(provider.calls,[])
        foreign=deepcopy(self.plan);foreign["provider_id"]="foreign"
        with self.assertRaisesRegex(ContractError,"plan_mismatch"):
            compile_production_window(self.provider,foreign,b_variant="P32",scale_variant="P32")
        self.assertEqual(self.provider.calls,[])

    def test_cache_is_immutable_and_provenance_distinguishes_routes_and_inputs(self):
        cache=compile_production_window(self.provider,self.plan,b_variant="P32",scale_variant="P32")
        self.assertFalse(np.shares_memory(cache.route_a.base,cache.route_b.base))
        self.assertEqual(cache.route_a.perturbative_segments.shape[-1],2)
        self.assertEqual(cache.route_b.perturbative_segments.shape[-1],3)
        for array in (cache.b,cache.route_a.base,cache.route_b.weights,cache.route_b.g2_segments):
            with self.assertRaises(ValueError):
                array.setflags(write=True)
        with self.assertRaises(FrozenInstanceError):
            cache.route_a=cache.route_b
        with self.assertRaises(TypeError):
            cache.identity["snapshot_id"]="wrong"
        self.assertEqual(cache.identity["snapshot_id"],self.provider.snapshot_id)
        other=FixtureProvider();other.snapshot_id="fixture-snapshot-2"
        another=compile_production_window(other,other.plan["payload"],b_variant="P32",scale_variant="P32")
        self.assertNotEqual(cache.identity["cache_sha256"],another.identity["cache_sha256"])
        before=len(self.provider.calls)
        for model in (APPROVED,CONTROL):
            for theta in ((.15,.02),(.45,.08)):
                cache.response(Chart("B").coordinates(theta),Chart("B"),model)
        self.assertEqual(len(self.provider.calls),before)


if __name__ == "__main__":
    unittest.main()
