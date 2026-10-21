#!/usr/bin/env python3
"""Build the isolated Lean library, check literal plans, and bind accepted plans.

Requires the user's existing Lean 4.21.0 toolchain. No global installation change.
Every run gets a fresh directory. Nonzero exit is retained in its summary.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from typed_tmd.finite_plan import (canonical, decode, digest, encode, lean_certificate,
    prepare_certified, run_lean_certificate, LEAN_STACK_KB)
from typed_tmd.finite_plan_bridge import kernel_cache_fixture

ALLOWED_AXIOMS={'propext','Quot.sound','Classical.choice'}


def command(argv,cwd,path,timeout=900):
    p=subprocess.run(argv,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    path.write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(f'command failed ({p.returncode}): {argv}; see {path}')
    return p.stdout+p.stderr


def axiom_audit(text):
    if any(x in text for x in ('sorryAx','ofReduceBool','native_decide','debug.skipKernelTC')):
        raise RuntimeError('unapproved axiom/trust shortcut in proof output')
    names=[]
    for match in re.finditer(r'depends on axioms:\s*\[([^\]]*)\]',text,re.S):
        for name in match.group(1).split(','):
            name=name.strip()
            if name and name not in ALLOWED_AXIOMS:
                raise RuntimeError('unapproved axiom: '+name)
            if name:names.append(name)
    if not re.search(r'depends on axioms|does not depend on any axioms',text):
        raise RuntimeError('no theorem axiom reports found')
    return sorted(set(names))


def first_output(doc):
    source,plans,atoms=decode(doc)
    p=doc['parameters']
    return encode((source[0],),(plans[0],),names=p['names'],varying=p['varying'],
                  theta0=tuple(float.fromhex(x) for x in p['reference_hex']),atom_values=atoms,
                  unary_symbols=doc['unary_symbols'],binary_symbols=doc['binary_symbols'],
                  context=doc['context'])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--runtime-dir',type=Path,required=True,
                    help='A run_formal_007 output or the handoff evidence/runtime_007_final directory')
    ap.add_argument('--lake',default='lake')
    args=ap.parse_args()
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    root=args.project.resolve();formal=root/'formal/007'
    report={'status':'pending','kernel_status':'not_run','scope':'finite-plan semantics only',
            'trust_boundary':['Python decoder/code generator','mapping of frozen primitives',
                              'Python/Fortran numerical evaluator','IEEE rounding and quadrature'],
            'proofs':[],'evaluator_checks':[]}
    start=time.perf_counter()
    try:
        if shutil.which(args.lake) is None:raise FileNotFoundError('pinned lake/Lean executable unavailable')
        version=command([args.lake,'env','lean','--version'],formal,out/'version.log',30)
        if not re.search(r'version 4\.21\.0(?:,|\s|\))',version):raise RuntimeError('requires Lean 4.21.0')
        # Capture exactly the theorem source whose compiled modules are rebuilt.
        files=sorted(formal.rglob('*.lean'))+[formal/'lakefile.toml',formal/'lean-toolchain']
        files=[p for p in files if '.lake' not in p.relative_to(formal).parts]
        sources={str(p.relative_to(formal)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        for p in files:
            if p.suffix!='.lean':continue
            text=p.read_text()
            if re.search(r'^\s*(?:axiom|unsafe|partial)\b',text,re.M) or re.search(
                r'\bsorry\b|\badmit\b|\bnative_decide\b|implemented_by|skipKernelTC',
                re.sub(r'/\-.*?\-/|--[^\n]*','',text,flags=re.S)):
                raise RuntimeError('source review required for forbidden proof shortcut: '+str(p))
        report['theory_sources']=sources;report['theory_source_digest']=digest(sources)
        # Only the new formal/007 build output is cleaned. Do not touch old lean/.
        command([args.lake,'clean'],formal,out/'clean.log')
        build=command([args.lake,'build'],formal,out/'build.log')
        report['axioms']=axiom_audit(build)
        # Positive and negative reference literals are both kernel-reduced.
        good,_=kernel_cache_fixture();bad,_=kernel_cache_fixture(freeze_dynamic=True)
        path=out/'negative.lean';path.write_text(lean_certificate(bad,expect_accept=False))
        command([args.lake,'env','lean',f'--tstack={LEAN_STACK_KB}',str(path)],formal,out/'negative.log')
        report['negative_status']='kernel_checked_false'
        cases=[('kernel_fixture',good)]
        for name,filename in [('H004_A','H004_A_finite_plan.json.gz'),
                              ('H004_B','H004_B_finite_plan.json.gz'),
                              ('H006_observation','H006_geometry_plan.json.gz')]:
            f=args.runtime_dir/filename
            if not f.exists():raise FileNotFoundError('required executed plan missing: '+str(f))
            with gzip.open(f,'rt') as h:doc=json.load(h)
            selected=first_output(doc)
            selected['context']['certificate_projection']={'output':0,'parent_wire_sha256':digest(doc)}
            cases.append((name,selected))
        for name,doc in cases:
            # This helper invokes fresh Lean checking, then evaluates exactly the
            # decoded accepted terms. There is no successful runtime-only fallback.
            if name=='H006_observation':
                samples=doc['context']['samples']
                callbacks=[]
                for s in samples:
                    q,Q,y=(float.fromhex(s[k]) for k in ('qT_hex','Q_hex','y_hex'))
                    callbacks.append(lambda c,q=q,Q=Q,y=y:(1+c*q*q)*(1+.0001*Q+.02*y))
                ops=tuple(callbacks)
                thetas=((.029551,),(.079022,))
            else:
                ops=(math.exp,)
                thetas=((.25,.04),(.15163591,.08229233))
                if name=='H004_B':thetas=tuple((a+g*math.log(2),g) for a,g in thetas)
            docpath=out/(name+'.json.gz')
            with gzip.open(docpath,'wb') as h:h.write(canonical(doc))
            prepared=prepare_certified(doc,expected_context=doc['context'],unary_ops=ops,
                 binary_ops=(lambda x,y:x+y,lambda x,y:x*y),
                 unary_symbols=doc['unary_symbols'],binary_symbols=doc['binary_symbols'],
                 project_dir=formal,output_dir=out/name,lake=args.lake)
            log=(out/name/'certificate.log').read_text()
            axiom_audit(log)
            report['proofs'].append(dict(prepared.receipt))
            for theta in thetas:
                got=prepared.evaluate(theta,context_identity=digest(doc['context']))
                expected=tuple(prepared.algebra.eval(e,theta) for e in prepared.source)
                if got!=expected:raise RuntimeError('accepted plan execution differs from source interpreter')
                report['evaluator_checks'].append({'case':name,'theta':theta,'value':got,
                                                    'interpreter_value':expected})
        report.update(status='passed',kernel_status='kernel_checked',negative_status='kernel_checked_false')
    except FileNotFoundError as exc:
        report.update(status='blocked',reason=str(exc))
    except Exception as exc:
        report.update(status='failed',reason=str(exc))
    report['elapsed_seconds']=time.perf_counter()-start
    (out/'SUMMARY.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report.get(k) for k in ('status','kernel_status','reason')},indent=2))
    return 0 if report['status']=='passed' else 2

if __name__=='__main__':raise SystemExit(main())
