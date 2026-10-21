"""Executable H007 tests. None is mislabeled a kernel-checked Lean proof."""
import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from typed_tmd.contracts import ContractError
from typed_tmd.finite_plan import (
    Expr, Plan, Algebra, PreparedPlan, atom, var, unary, binary, dependencies,
    cacheable, check, propose, erase, substitute, compose, respects_variation,
    encode, decode, digest, canonical, read_wire, check_wire, prepare_wire,
    lean_certificate, run_lean_certificate, prepare_certified)
from typed_tmd.finite_plan_bridge import kernel_cache_fixture, observation_packet, bind_observation_packet, balanced_sum
from typed_tmd.observations import DYBin, ObservationContract

OPS = (lambda a,b:a+b, lambda a,b:a*b)


class FinitePlanTests(unittest.TestCase):
    def setUp(self):
        self.good,_ = kernel_cache_fixture()
        self.bad,_ = kernel_cache_fixture(freeze_dynamic=True)

    def bind(self,doc=None):
        doc = self.good if doc is None else doc
        return prepare_wire(doc,expected_context=doc['context'],unary_ops=(math.exp,),binary_ops=OPS,
                            unary_symbols=('exp',),binary_symbols=('add','mul'))

    def test_good_actual_plan_equals_source_at_off_reference_values(self):
        p=self.bind()
        for theta in ((.25,.04),(.15,.01),(.4,.08),(.25,.0)):
            value=p.evaluate(theta,context_identity=digest(self.good['context']))
            expected=tuple(p.algebra.eval(e,theta) for e in p.source)
            self.assertEqual(value,expected)
        self.assertEqual(p.receipt['status'],'runtime_checked_only')

    def test_invalid_cache_fails_before_any_primitive_call(self):
        calls=[]
        with self.assertRaisesRegex(ContractError,'cache_depends'):
            prepare_wire(self.bad,expected_context=self.bad['context'],
                         unary_ops=(lambda x:calls.append(x) or math.exp(x),),
                         binary_ops=OPS,unary_symbols=('exp',),binary_symbols=('add','mul'))
        self.assertEqual(calls,[])

    def test_value_closure_passes_but_frozen_kernel_sensitivity_is_wrong(self):
        good=self.bind(); a,g=.25,.04; ctx=digest(self.good['context'])
        b, L, R=1.3, math.log(4.),.2
        f=lambda gg:good.evaluate((a,gg),context_identity=ctx)[0]
        wrong=lambda gg:math.exp(R-g*b*b*L)*math.exp(-a*b*b)
        self.assertEqual(f(g),wrong(g))
        step=1e-6
        derivative=(f(g+step)-f(g-step))/(2*step)
        self.assertAlmostEqual(derivative,-b*b*L*f(g),places=8)
        self.assertEqual(wrong(g+step),wrong(g-step))
        self.assertNotEqual(f(g+.01),wrong(g+.01))

    def test_explicit_fixed_model_is_permitted_with_fixed_environment_guard(self):
        doc=copy.deepcopy(self.bad);doc['parameters']['varying']=[True,False]
        p=self.bind(doc)
        p.evaluate((.35,.04),context_identity=digest(doc['context']))
        with self.assertRaisesRegex(ContractError,'fixed_parameter'):
            p.evaluate((.35,.041),context_identity=digest(doc['context']))

    def test_changed_context_prevents_cache_reuse(self):
        p=self.bind()
        with self.assertRaisesRegex(ContractError,'cache_context_changed'):
            p.evaluate((.25,.04),context_identity='other-provider-or-resolution')

    def test_runtime_plan_and_cache_are_immutable(self):
        p=self.bind()
        with self.assertRaises(AttributeError):p.plans=()
        with self.assertRaises(TypeError):p._cache[atom(0)]=8.

    def test_erasure_rejects_changed_coefficient_or_operation(self):
        src,plans,_=decode(self.good)
        wrong=Plan('binary',ident=0,children=plans[0].children)
        with self.assertRaisesRegex(ContractError,'erasure'):
            check(src[0],wrong,(True,True))

    def test_support_is_conservative_under_cancellation(self):
        e=binary(0,var(0),unary(1,var(0)))
        self.assertEqual(dependencies(e),frozenset({0}))
        self.assertFalse(cacheable(e,(True,)))

    def test_substitution_identity_and_associativity(self):
        e=binary(0,var(0),unary(0,var(1)))
        f=(binary(1,var(0),atom(0)),var(1))
        g=(unary(0,var(1)),binary(0,var(0),atom(1)))
        self.assertEqual(substitute(e,(var(0),var(1))),e)
        self.assertEqual(substitute(substitute(e,f),g),substitute(e,compose(g,f)))

    def test_substitution_interpretation(self):
        e=binary(0,var(0),unary(0,var(1)))
        f=(binary(1,var(0),atom(0)),var(1))
        M=Algebra((2.,3.),(math.exp,),OPS)
        for theta in ((.2,.3),(.4,.1)):
            self.assertEqual(M.eval(substitute(e,f),theta),M.eval(e,tuple(M.eval(x,theta) for x in f)))

    def test_mask_transport_rejects_new_dependency_in_fixed_coordinate(self):
        chart=(binary(0,var(0),binary(1,atom(0),var(1))),var(1))
        self.assertFalse(respects_variation(chart,(True,True),(False,True)))
        self.assertTrue(respects_variation(chart,(True,True),(True,True)))

    def test_checked_composition_transports_reference_environment(self):
        M=Algebra((2.,),(lambda x:x*x,),OPS)
        f=(binary(0,var(0),atom(0)),unary(0,var(1)))
        g=(binary(1,var(0),var(1)),)
        vX=(True,False);vY=(True,False)
        self.assertTrue(respects_variation(f,vX,vY))
        theta0=(.2,.3);theta=(.4,.3)
        pf=PreparedPlan(f,tuple(propose(e,vX) for e in f),vX,theta0,M,context_identity='X')
        mid0=tuple(M.eval(e,theta0) for e in f)
        pg=PreparedPlan(g,tuple(propose(e,vY) for e in g),vY,mid0,M,context_identity='Y')
        got=pg.evaluate(pf.evaluate(theta,context_identity='X'),context_identity='Y')
        self.assertEqual(got,tuple(M.eval(e,theta) for e in compose(f,g)))

    def test_untransported_reference_is_rejected_at_composition(self):
        M=Algebra((2.,),(lambda x:x*x,),OPS)
        f=(binary(0,var(0),atom(0)),unary(0,var(1)))
        g=(binary(1,var(0),var(1)),)
        mask=(True,False);theta0=(.2,.3);theta=(.4,.3)
        pf=PreparedPlan(f,tuple(propose(e,mask) for e in f),mask,theta0,M,context_identity='X')
        # Individually well checked, but initialized at the WRONG target slice.
        pg=PreparedPlan(g,tuple(propose(e,mask) for e in g),mask,theta0,M,context_identity='Y')
        with self.assertRaisesRegex(ContractError,'fixed_parameter_changed'):
            pg.evaluate(pf.evaluate(theta,context_identity='X'),context_identity='Y')

    def test_runtime_preservation_random_supported_terms(self):
        r=random.Random(7007);M=Algebra((.2,.3),(lambda x:x*x,),OPS)
        def gen(depth):
            if depth==0:return var(r.randrange(2)) if r.random()<.5 else atom(r.randrange(2))
            return unary(0,gen(depth-1)) if r.random()<.25 else binary(r.randrange(2),gen(depth-1),gen(depth-1))
        for _ in range(80):
            e=gen(3);mask=(r.choice((True,False)),r.choice((True,False)))
            theta0=(.2,.3);theta=tuple(.4 if v else theta0[i] for i,v in enumerate(mask))
            p=PreparedPlan((e,),(propose(e,mask),),mask,theta0,M,context_identity='random-fixed-model')
            self.assertEqual(p.evaluate(theta,context_identity='random-fixed-model'),(M.eval(e,theta),))

    def test_wire_roundtrip_is_identity(self):
        s,p,a=decode(self.good)
        restored=json.loads(canonical(self.good))
        self.assertEqual(decode(restored),(s,p,a))
        self.assertEqual(digest(restored),digest(self.good))

    def test_unknown_wire_fields_rejected(self):
        d=copy.deepcopy(self.good);d['trusted']=True
        with self.assertRaises(ContractError):decode(d)

    def test_noncanonical_numeric_or_nonfinite_atom_rejected(self):
        for x in ('nan','inf','0.2','0x1.0p+0'):
            d=copy.deepcopy(self.good);d['atoms_hex'][0]=x
            with self.assertRaises(ContractError):decode(d)

    def test_duplicate_parameter_or_primitive_names_rejected(self):
        d=copy.deepcopy(self.good);d['parameters']['names']=['g','g']
        with self.assertRaises(ContractError):decode(d)
        d=copy.deepcopy(self.good);d['unary_symbols']=['exp','exp']
        with self.assertRaises(ContractError):decode(d)

    def test_forward_reference_or_cycle_rejected(self):
        d=copy.deepcopy(self.good);d['expressions'][0]={'tag':'unary','id':0,'args':[0]}
        with self.assertRaises(ContractError):decode(d)

    def test_invalid_variable_arity_rejected(self):
        d=copy.deepcopy(self.good)
        next(row for row in d['expressions'] if row['tag']=='var')['id']=2
        with self.assertRaises(ContractError):decode(d)

    def test_boolean_index_rejected(self):
        d=copy.deepcopy(self.good);d['source_roots']=[True]
        with self.assertRaises(ContractError):decode(d)

    def test_output_shape_rejected(self):
        d=copy.deepcopy(self.good);d['plan_roots']*=2
        with self.assertRaises(ContractError):decode(d)

    def test_primitive_binding_identity_checked(self):
        with self.assertRaisesRegex(ContractError,'registry'):
            prepare_wire(self.good,expected_context=self.good['context'],unary_ops=(math.exp,),
                         binary_ops=OPS,unary_symbols=('different-exp',),binary_symbols=('add','mul'))

    def test_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"schema":1,"schema":2}')
            with self.assertRaisesRegex(ContractError,'duplicate_json'):
                read_wire(p)

    def test_lean_export_contains_literal_check_and_preservation_theorem(self):
        text=lean_certificate(self.good)
        self.assertIn('check varies',text)
        self.assertIn('by decide',text)
        self.assertIn('check_sound',text)
        self.assertIn(digest(self.good),text)
        self.assertNotIn('native_decide',text)
        self.assertNotIn('sorry',text)

    def test_missing_lean_is_blocked_never_runtime_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'proof'
            with self.assertRaisesRegex(ContractError,'did not pass'):
                run_lean_certificate(self.good,tmp,out,lake='/definitely/missing/lake')
            receipt=json.loads((out/'receipt.json').read_text())
            self.assertEqual(receipt['status'],'blocked')


    def test_nonleaf_cannot_carry_unused_expression_payload(self):
        with self.assertRaisesRegex(ContractError,'plan_leaf_expression'):
            Plan('unary',expr=7,ident=0,children=(Plan('live',var(0)),))

    def test_binding_scope_checked_before_any_cached_call(self):
        calls=[]
        first=unary(0,atom(0)); second=unary(1,var(0))
        M=Algebra((1.,),(lambda x:calls.append(x) or x,),OPS)
        with self.assertRaisesRegex(ContractError,'binding_scope'):
            PreparedPlan((first,second),(Plan('cache',first),Plan('live',second)),
                         (True,),(.2,),M,context_identity='test')
        self.assertEqual(calls,[])

    def test_bad_registry_and_reference_types_fail_closed(self):
        for key,value in [('unary_symbols',[{}]),('reference_hex',None)]:
            doc=copy.deepcopy(self.good)
            if key=='reference_hex':doc['parameters'][key]=value
            else:doc[key]=value
            with self.assertRaises(ContractError):decode(doc)

    def test_out_of_scope_atom_is_rejected_before_evaluation(self):
        e=atom(5)
        with self.assertRaisesRegex(ContractError,'binding_scope'):
            PreparedPlan((e,),(Plan('cache',e),),(True,),(.2,),
                         Algebra((1.,),(math.exp,),OPS),context_identity='test')


class FiniteObservationTests(unittest.TestCase):
    def setUp(self):
        self.row=DYBin('bridge',(0.,2.),(3.,5.),(-.5,.5),10000.,(1,1,5),False,(0.,0.,0.,0.),2.)
        self.contract=ObservationContract((self.row,), 'analytic-test-only')

    def test_lowered_plan_uses_same_real_H006_quadrature_functions(self):
        doc=observation_packet(self.contract,(3,3,2),())
        p=bind_observation_packet(doc,self.contract,lambda row,q,Q,y,c:1+c*q*q)
        for c in (.02,.03,.06):
            value=p.evaluate((c,),context_identity=digest(doc['context']))[0]
            self.assertAlmostEqual(value,64+128*c,places=10)
        self.assertEqual(dependencies(p.source[0]),frozenset({0}))

    def test_native_output_cannot_be_cached_as_parameter_independent(self):
        doc=observation_packet(self.contract,(2,2,2),())
        root=doc['source_roots'][0]
        doc['plans']=[{'tag':'cache','id':0,'expr':root,'args':[]}];doc['plan_roots']=[0]
        calls=[]
        with self.assertRaisesRegex(ContractError,'cache_depends'):
            bind_observation_packet(doc,self.contract,lambda *a:calls.append(a) or 1.)
        self.assertEqual(calls,[])

    def test_forged_point_as_bin_source_is_rejected(self):
        doc=observation_packet(self.contract,(2,2,2),())
        doc['context']['expected_kind']='point_density'
        with self.assertRaisesRegex(ContractError,'binding'):
            bind_observation_packet(doc,self.contract,lambda *a:1.)

    def test_same_tag_altered_geometry_source_is_rejected(self):
        doc=observation_packet(self.contract,(2,2,2),())
        doc['atoms_hex'][1]=(7.).hex()
        with self.assertRaisesRegex(ContractError,'lowering'):
            bind_observation_packet(doc,self.contract,lambda *a:1.)

    def test_parameter_removed_from_native_signature_is_rejected(self):
        doc=observation_packet(self.contract,(2,2,2),())
        doc['parameters']['varying']=[False]
        with self.assertRaisesRegex(ContractError,'dependency'):
            bind_observation_packet(doc,self.contract,lambda *a:1.)

    def test_both_observation_measures_use_same_bin_yield(self):
        for measure in ('dqT','dqT2'):
            contract=replace(self.contract,measure=measure)
            doc=observation_packet(contract,(3,3,2),())
            p=bind_observation_packet(doc,contract,lambda row,q,Q,y,c:1+c*q*q)
            expected=(64+128*.03)/(1 if measure=='dqT' else 2)
            self.assertAlmostEqual(p.evaluate((.03,),context_identity=digest(doc['context']))[0],expected,places=10)

class DenseKernelCertificateTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lake") and
        (Path(__file__).resolve().parents[1]/"formal/007/.lake/build/lib/lean/TypedTMDPlan/Core.olean").exists(),
        "optional integration regression needs the built pinned Lean library")
    def test_dense_literal_plan_is_kernel_checked_and_the_same_plan_executes(self):
        # A balanced real-sized expression exposes the default-stack failure;
        # reducing a small proxy would not exercise this certificate path.
        coefficients=tuple((i+1)/4096 for i in range(512))
        terms=[binary(1,atom(i),unary(0,binary(1,var(0),atom(i)))) for i in range(512)]
        source=balanced_sum(terms,atom(0))
        doc=encode((source,),(propose(source,(True,)),),names=("g",),varying=(True,),
                   theta0=(.1,),atom_values=coefficients,unary_symbols=("exp",),
                   binary_symbols=("add","mul"),context={"test":"dense-certificate-resource-regression"})
        formal=Path(__file__).resolve().parents[1]/"formal/007"
        with tempfile.TemporaryDirectory() as tmp:
            prepared=prepare_certified(doc,expected_context=doc["context"],unary_ops=(math.exp,),
                binary_ops=OPS,unary_symbols=("exp",),binary_symbols=("add","mul"),
                project_dir=formal,output_dir=Path(tmp)/"proof")
            self.assertEqual(prepared.receipt["status"],"kernel_checked")
            self.assertEqual(prepared.receipt["wire_sha256"],digest(doc))
            self.assertEqual(prepared.plans,decode(doc)[1])
            for theta in ((.1,),(.3,)):
                self.assertEqual(prepared.evaluate(theta,context_identity=digest(doc["context"])),
                                 (prepared.algebra.eval(source,theta),))


if __name__=='__main__':unittest.main()
