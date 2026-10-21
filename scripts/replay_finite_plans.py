#!/usr/bin/env python3
"""Replay the published finite coefficients; no provider grid or native engine."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from typed_tmd.finite_plan import decode, digest, prepare_wire

ROOT = Path(__file__).resolve().parents[1]


def load_fixtures(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'MANIFEST.json').read_text())
    documents = {}
    for entry in manifest['files']:
        name = entry['path']
        if Path(name).name != name:
            raise ValueError('fixture path must be a basename')
        raw = (directory/name).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('fixture byte identity mismatch: '+name)
        if entry.get('canonical_wire_sha256'):
            doc = json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)
            if digest(doc) != entry['canonical_wire_sha256']:
                raise ValueError('canonical wire identity mismatch: '+name)
            decode(doc)
            documents[name] = doc
    return manifest, documents


def bind(doc):
    if doc['context'].get('samples'):
        callbacks = []
        for sample in doc['context']['samples']:
            q, Q, y = (float.fromhex(sample[k]) for k in ('qT_hex', 'Q_hex', 'y_hex'))
            callbacks.append(lambda c, q=q, Q=Q, y=y: (1+c*q*q)*(1+.0001*Q+.02*y))
        unary_ops = tuple(callbacks)
    else:
        unary_ops = (math.exp,)
    return prepare_wire(doc, expected_context=doc['context'], unary_ops=unary_ops,
        binary_ops=(lambda x, y: x+y, lambda x, y: x*y),
        unary_symbols=doc['unary_symbols'], binary_symbols=doc['binary_symbols'])


def replay(directory):
    manifest, docs = load_fixtures(directory)
    comparisons = []
    for row in manifest['comparisons']:
        doc = docs[row['fixture']]
        prepared = bind(doc)
        theta = tuple(row['theta'])
        values = prepared.evaluate(theta, context_identity=digest(doc['context']))
        source = tuple(prepared.algebra.eval(e, theta) for e in prepared.source)
        if values != source:
            raise ValueError('same-plan/source interpreter disagreement')
        targets = row['target_values']
        if len(values) != len(targets):
            raise ValueError('target arity mismatch')
        budgets = ([row['scaled_tolerance']*max(1., abs(x)) for x in targets]
                   if 'scaled_tolerance' in row else
                   [row['atol']+row['rtol']*abs(x) for x in targets])
        ratios = [abs(x-y)/b for x, y, b in zip(values, targets, budgets)]
        if max(ratios) > 1:
            raise ValueError('frozen numerical target comparison failed')
        comparisons.append({'fixture': row['fixture'], 'theta': theta,
            'values': values, 'target_values': targets, 'max_tolerance_ratio': max(ratios),
            'wire_sha256': digest(doc), 'source_interpreter_exact': True})
    return {'status': 'numerically_compared', 'comparison_count': len(comparisons),
        'scalar_comparisons': sum(len(row['values']) for row in comparisons),
        'comparisons': comparisons,
        'scope': 'all 9 finite-window outputs in both charts and all 7 analytic-geometry bins; no new native calculation',
        'fixture_manifest_sha256': hashlib.sha256((Path(directory)/'MANIFEST.json').read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, default=ROOT/'evidence/formal/fixtures')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: result[k] for k in ('status', 'comparison_count', 'scalar_comparisons')}))


if __name__ == '__main__':
    main()
