#!/usr/bin/env python3
"""Reproduce bounded H007 runtime evidence; never substitutes it for Lean proofs."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import sys
import time

import numpy as np
from typed_tmd.finite_plan import (Algebra, Plan, PreparedPlan, canonical, digest, decode, check_wire,
                                  prepare_wire, lean_certificate, run_lean_certificate)
from typed_tmd.finite_plan_bridge import (kernel_cache_fixture, observation_packet,
                                        bind_observation_packet, production_window_packet)
from typed_tmd.observations import DYBin, ObservationContract
from typed_tmd.observation_quadrature import integrate_point_density


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--h004-provider-dir',type=Path)
    ap.add_argument('--lean',action='store_true')
    args=ap.parse_args()
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    evidence={"scope":"finite-plan runtime tests; no native arTeMiDe execution; no new fit",
              "python":platform.python_version(),"numpy":np.__version__,"platform":platform.platform(),
              "lean_status":"not_executed", "source_identity":{}}
    source_dir=Path(__import__('typed_tmd').__file__).resolve().parent
    for name in ('finite_plan.py','finite_plan_bridge.py','observations.py','observation_quadrature.py'):
        p=source_dir/name;evidence['source_identity'][name]=hashlib.sha256(p.read_bytes()).hexdigest()
    good,_=kernel_cache_fixture();bad,_=kernel_cache_fixture(freeze_dynamic=True)
    for name,doc in [('good',good),('bad',bad)]:
        save(out/f'{name}.json',doc)
        (out/f'{name}.lean').write_text(lean_certificate(doc,expect_accept=(name=='good')))
    rejection=None
    try:check_wire(bad,expected_context=bad['context'])
    except ValueError as e:rejection=str(e)
    if rejection is None:raise RuntimeError('bad fitted-parameter cache accepted')
    p=prepare_wire(good,expected_context=good['context'],unary_ops=(math.exp,),
                   binary_ops=(lambda a,b:a+b,lambda a,b:a*b),unary_symbols=('exp',),binary_symbols=('add','mul'))
    a,g=.25,.04;b=1.3;L=math.log(4.);h=1e-6
    f=lambda x:p.evaluate((a,x),context_identity=digest(good['context']))[0]
    v=f(g);dg=(f(g+h)-f(g-h))/(2*h)
    cache={"rejected_before_evaluation":rejection,"reference_value":v,"frozen_reference_value":v,
           "correct_g_derivative_exact_formula":-b*b*L*v,
           "correct_g_derivative_centered_difference":dg,
           "incorrect_g_derivative":0.,"off_reference_g":g+.01,
           "correct_off_reference_value":f(g+.01),"frozen_off_reference_value":v}
    save(out/'cache_counterexample.json',cache)

    # Real H006 geometry; analytic point kernel, explicitly NOT native physics.
    config=args.project/'configs/006/observation_contract.json'
    if not config.exists():config=args.project/'configs/external/observation_contract.json'
    doc=json.loads(config.read_text())
    cd=doc['contract']; rows=[]
    for r in cd['bins']:
        v=dict(r)
        for key in ('qT','Q','y','process','cuts'):v[key]=tuple(v[key])
        rows.append(DYBin(**v))
    contract=ObservationContract(tuple(rows),cd['physics_identity'],cd['measure'])
    orders=(8,8,4);breaks=(80.,86.,89.,91.,93.,96.,102.)
    obs=observation_packet(contract,orders,breaks)
    with gzip.open(out/'H006_geometry_plan.json.gz','wb') as s:s.write(canonical(obs))
    calls=[0]
    def point(row,q,Q,y,c0):
        calls[0]+=1
        return (1+c0*q*q)*(1+.0001*Q+.02*y)
    prepared=bind_observation_packet(obs,contract,point)
    if calls[0]!=0:raise RuntimeError('parameter-dependent native calls during cache initialization')
    comparisons=[]
    for c0 in (.001,.029551,.079022,.1):
        values=prepared.evaluate((c0,),context_identity=digest(obs['context']))
        direct=[]
        for row in rows:
            direct.append(integrate_point_density(lambda row,q,Q,y:(1+c0*q*q)*(1+.0001*Q+.02*y),
                          row,orders,breaks)*row.average_factor(contract.measure))
        err=max(abs(x-y) for x,y in zip(values,direct))
        rel=max(abs(x-y)/max(1.,abs(y)) for x,y in zip(values,direct))
        if rel>2e-13:raise RuntimeError('lowered observation plan mismatch')
        comparisons.append({'c0':c0,'plan_values':list(values),'H006_numpy_quadrature':direct,
                            'max_absolute_difference':err,'max_scaled_difference':rel})
    evidence['observation_bridge']={'geometry_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
         'point_kernel':'analytic polynomial fixture; NOT arTeMiDe', 'orders':orders,
         'bins':len(rows),'sample_count':len(obs['context']['samples']),
         'expression_nodes':len(obs['expressions']),'plan_nodes':len(obs['plans']),
         'comparisons':comparisons,'status':'passed'}
    save(out/'observation_bridge.json',evidence['observation_bridge'])

    if args.h004_provider_dir:
        from typed_tmd.provider_replay import document, ReplayProvider
        from typed_tmd.extraction_production import compile_production_window
        from typed_tmd.extraction import Chart, APPROVED
        inputs=args.h004_provider_dir
        print('H004: loading immutable provider inputs',flush=True)
        ins=document(inputs/'provider_inspection.json')
        plan=document(inputs/'provider_query_plan.json.gz')
        snap=document(inputs/'provider_snapshot.json.gz')
        provider=ReplayProvider(ins,plan,snap)
        print('H004: compiling existing accepted P32/P32 finite window',flush=True)
        window=compile_production_window(provider,plan['payload'],b_variant='P32',scale_variant='P32',Q_values=(20.,30.,40.))
        results=[]
        for name in ('A','B'):
            chart=Chart(name)
            wire=production_window_packet(window,chart,APPROVED)
            with gzip.open(out/f'H004_{name}_finite_plan.json.gz','wb') as s:s.write(canonical(wire))
            runtime=prepare_wire(wire,expected_context=wire['context'],unary_ops=(math.exp,),
                           binary_ops=(lambda a,b:a+b,lambda a,b:a*b),
                           unary_symbols=('exp',),binary_symbols=('add','mul'))
            for theta in ((.25,.04),(.15163591,.08229233),(.1,0.),(.5,.1)):
                coordinates=chart.coordinates(theta)
                original=window.response(coordinates,chart,APPROVED)[0]
                checked=np.array(runtime.evaluate(coordinates,context_identity=digest(wire['context'])))
                residual=float(np.max(np.abs(original-checked)))
                ratio=float(np.max(np.abs(original-checked)/(1e-13+1e-11*np.abs(original))))
                if ratio>1:raise RuntimeError('H004 finite-plan bridge tolerance')
                results.append({'chart':name,'canonical':list(theta),'original':original.tolist(),
                      'finite_plan':checked.tolist(),'max_abs_difference':residual,'max_tolerance_ratio':ratio})
        evidence['H004_bridge']={'status':'passed','targets':len(window.targets),'b_nodes':len(window.b),
                'snapshot_sha256':snap['payload_sha256'],'plan_sha256':plan['payload_sha256'],
                'new_fits':0,'new_native_queries':0,'comparisons':results,
                'scope':'frozen production coefficients; exact plan theorem does not verify their QCD/continuum origin'}
        save(out/'H004_bridge.json',evidence['H004_bridge'])
    else:
        evidence['H004_bridge']={'status':'not_requested','reason':'provider companion not supplied to this command'}

    if args.lean:
        lean_dir=args.project/'formal/007'
        try:
            evidence['lean_receipt']=run_lean_certificate(good,lean_dir,out/'kernel_good')
            evidence['lean_status']='kernel_checked_good_literal'
        except Exception as exc:
            evidence['lean_status']='blocked_or_failed';evidence['lean_error']=str(exc)
    evidence['elapsed_seconds']=time.perf_counter()-start
    save(out/'SUMMARY.json',evidence)
    print(json.dumps({k:evidence[k] for k in ('lean_status','elapsed_seconds')},indent=2))
    if args.lean and evidence['lean_status']!='kernel_checked_good_literal':return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
