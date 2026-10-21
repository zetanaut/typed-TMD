#!/usr/bin/env python3
"""Mandatory fresh Lean build, theorem audit, full selected roots and replay.

Missing Lean or fixtures produces a nonzero exit, never a runtime-only success.
Raw local logs are retained. PORTABLE.json contains relative evidence links.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from typed_tmd.finite_plan import digest
from typed_tmd.finite_plan_bridge import kernel_cache_fixture
from replay_finite_plans import load_fixtures, replay

ROOT = Path(__file__).resolve().parents[1]


def theorem_inventory(formal):
    records = []
    for source in sorted((formal/'TypedTMDPlan').glob('*.lean')):
        stack = []
        for number, line in enumerate(source.read_text().splitlines(), 1):
            match = re.match(r'namespace ([\w.]+)', line)
            if match:
                stack.append(match[1])
            elif re.match(r'end(?:\s|$)', line):
                stack.pop()
            else:
                match = re.match(r'theorem (\w+)', line)
                if match:
                    records.append({'name': '.'.join(stack+[match[1]]),
                        'source': str(source.relative_to(formal.parent.parent)), 'line': number,
                        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    if len(records) != 24:
        raise ValueError('expected the accepted inventory of 24 theorem statements')
    return records


def audit_axioms(text, names):
    records = {}
    for name in names:
        match = re.search(r"'"+re.escape(name)+r"' (?:depends on axioms:\s*\[([^\]]*)\]|does not depend on any axioms)", text, re.S)
        if match is None:
            raise ValueError('missing axiom report: '+name)
        axioms = [x.strip() for x in (match[1] or '').split(',') if x.strip()]
        if set(axioms)-{'propext', 'Quot.sound'}:
            raise ValueError('unexpected logical dependency: '+repr(axioms))
        records[name] = axioms
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, default=ROOT/'evidence/formal/fixtures')
    parser.add_argument('--lake', default='lake')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = {'status': 'pending', 'scope': 'exact finite-plan semantics; no QCD/decoder/IEEE proof'}
    try:
        manifest, docs = load_fixtures(args.fixtures)
        # The accepted runner generates these two literals: bind their identity
        # to the shipped snapshot before invoking it.
        for filename, freeze in [('good.json', False), ('bad.json', True)]:
            if digest(kernel_cache_fixture(freeze_dynamic=freeze)[0]) != digest(docs[filename]):
                raise ValueError('generated kernel literal differs from public fixture')
        command = [sys.executable, str(ROOT/'scripts/check_formal_007.py'), '--project', str(ROOT),
            '--runtime-dir', str(args.fixtures.resolve()), '--output-dir', str(out/'selected'), '--lake', args.lake]
        proc = subprocess.run(command, text=True, capture_output=True)
        (out/'selected_command.log').write_text(proc.stdout+proc.stderr)
        if proc.returncode:
            raise RuntimeError('selected proof runner failed; see selected/SUMMARY.json')
        formal = ROOT/'formal/007'
        inventory = theorem_inventory(formal)
        audit = out/'TheoremInventory.lean'
        audit.write_text('import TypedTMDPlan\nset_option pp.universes true\n'+''.join(
            '#check '+row['name']+'\n#print axioms '+row['name']+'\n' for row in inventory))
        proc = subprocess.run([args.lake, 'env', 'lean', '--tstack=65536', str(audit)],
                              cwd=formal, text=True, capture_output=True)
        (out/'theorem_inventory.log').write_text(proc.stdout+proc.stderr)
        if proc.returncode:
            raise RuntimeError('theorem inventory failed')
        axioms = audit_axioms(proc.stdout, [row['name'] for row in inventory])
        for row in inventory:
            row['axioms'] = axioms[row['name']]
        selected = json.loads((out/'selected/SUMMARY.json').read_text())
        roots = []
        filenames = ['good.json', 'H004_A_finite_plan.json.gz', 'H004_B_finite_plan.json.gz', 'H006_geometry_plan.json.gz']
        cases = ['kernel_fixture', 'H004_A', 'H004_B', 'H006_observation']
        for case, filename, receipt in zip(cases, filenames, selected['proofs']):
            wire = json.loads(gzip.decompress((out/'selected'/f'{case}.json.gz').read_bytes()))
            log = (out/'selected'/case/'certificate.log').read_text()
            audit_axioms(log, ['WireCertificate.preservation_0'])
            roots.append({'case': case, 'parent_fixture': filename, 'parent_wire_sha256': digest(docs[filename]),
                'selected_output': 0, 'wire_sha256': digest(wire),
                'expression_nodes': len(wire['expressions']), 'plan_nodes': len(wire['plans']),
                'certificate': f'selected/{case}/Certificate.lean',
                'certificate_sha256': receipt['certificate_sha256'],
                'status': receipt['status'], 'theory_sources': receipt['theory_sources'],
                'thread_stack_kb': receipt['thread_stack_kb']})
        if len(roots) != 4 or any(r['status'] != 'kernel_checked' for r in roots):
            raise ValueError('incomplete positive certificate set')
        negative = out/'NegativeAxioms.lean'
        negative.write_text((out/'selected/negative.lean').read_text()+'\n#print axioms WireCertificate.accepted_0\n')
        proc = subprocess.run([args.lake, 'env', 'lean', '--tstack=65536', str(negative)],
                              cwd=formal, text=True, capture_output=True)
        (out/'negative_axioms.log').write_text(proc.stdout+proc.stderr)
        if proc.returncode:
            raise RuntimeError('negative literal audit failed')
        audit_axioms(proc.stdout, ['WireCertificate.accepted_0'])
        # Dense regression is mandatory here; unittest's optional skip is only
        # useful for the separate runtime-only route.
        code = ('import sys,unittest; sys.path.insert(0,"tests"); '
                'from test_finite_plan import DenseKernelCertificateTests as T; '
                'r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(T)); '
                'sys.exit(0 if r.wasSuccessful() and not r.skipped else 2)')
        proc = subprocess.run([sys.executable, '-c', code], cwd=ROOT, text=True, capture_output=True)
        (out/'dense_regression.log').write_text(proc.stdout+proc.stderr)
        if proc.returncode:
            raise RuntimeError('mandatory dense certificate regression failed or skipped')
        numerical = replay(args.fixtures)
        (out/'replay.json').write_text(json.dumps(numerical, indent=2, sort_keys=True)+'\n')
        result.update(status='kernel_checked', lean='4.21.0', theorem_count=len(inventory),
            theorems=inventory, axioms=sorted(set(x for values in axioms.values() for x in values)),
            selected_roots=roots, negative_status=selected['negative_status'],
            negative_parent_wire_sha256=digest(docs['bad.json']),
            negative_certificate_sha256=hashlib.sha256((out/'selected/negative.lean').read_bytes()).hexdigest(),
            same_plan_evaluations=selected['evaluator_checks'], dense_regression='passed_no_skip',
            full_runtime_replay={'status': numerical['status'], 'scalar_comparisons': numerical['scalar_comparisons']},
            fixture_manifest_sha256=hashlib.sha256((args.fixtures/'MANIFEST.json').read_bytes()).hexdigest())
    except Exception as exc:
        result.update(status='failed_or_blocked', reason=str(exc))
    (out/'PORTABLE.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: result.get(k) for k in ('status', 'theorem_count', 'reason')}))
    return 0 if result['status'] == 'kernel_checked' else 2


if __name__ == '__main__':
    raise SystemExit(main())
