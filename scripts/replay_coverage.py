#!/usr/bin/env python3
"""Replay the saved 200-vector coverage diagnostic; no refit or new noise.

The numerical routines are copied unchanged from the reviewed diagnostic.
The public input is a documented field projection of the verified private
archive, not a claim that the projected file is the complete original return.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any
import numpy as np

def box_linear_statistics(G: np.ndarray, noise: np.ndarray,
                          lo: np.ndarray, hi: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Exact active-set enumeration for a strictly convex TWO-variable LS problem.

    A minimum is either the feasible interior solution or on one of four edges.
    Each edge minimum is a one-variable least-squares solution clipped to the
    edge endpoints. The endpoints therefore include all corners.
    """
    interior = np.linalg.lstsq(G, noise.T, rcond=None)[0].T
    ratios, bound_ids = [], []
    for replica_id, z in enumerate(noise):
        candidates = []
        if np.all((interior[replica_id] >= lo) & (interior[replica_id] <= hi)):
            candidates.append(interior[replica_id])
        for fixed in range(2):
            free = 1 - fixed
            for edge in (lo[fixed], hi[fixed]):
                x = np.zeros(2)
                x[fixed] = edge
                residual = z - edge * G[:, fixed]
                x[free] = np.clip(G[:, free] @ residual / (G[:, free] @ G[:, free]),
                                  lo[free], hi[free])
                candidates.append(x)
        costs = [float(np.sum((z - G @ x)**2)) for x in candidates]
        best = int(np.argmin(costs))
        ratios.append(float(z @ z - costs[best]))
        if np.any(np.isclose(candidates[best], lo, atol=1e-12, rtol=0) |
                  np.isclose(candidates[best], hi, atol=1e-12, rtol=0)):
            bound_ids.append(replica_id)
    return np.asarray(ratios), bound_ids

def binomial_upper_tail(n: int, k: int, probability: float) -> float:
    return math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(j + 1)
        - math.lgamma(n-j+1) + j*math.log(probability)
        + (n-j)*math.log1p(-probability)) for j in range(k, n+1))

def describe(values: np.ndarray) -> dict[str, Any]:
    return {
        'n': len(values), 'mean': float(values.mean()),
        'quantile_method': 'linear',
        'empirical_q68': float(np.quantile(values, .68, method='linear')),
        'empirical_q95': float(np.quantile(values, .95, method='linear')),
        'covered_68': int(np.sum(values <= -2*math.log1p(-.68))),
        'covered_95': int(np.sum(values <= -2*math.log1p(-.95))),
    }

def calculate(inputs: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    control = inputs['coefficient_control.json']
    truth = inputs['frozen_truth.json']
    data = inputs['data.json']
    replicas = inputs['replicas.json']
    ids = [r['id'] for r in replicas]
    if ids != list(range(len(replicas))):
        raise ValueError("Replica order does not match saved noise rows")
    noise = np.array([[float.fromhex(v) for v in row] for row in data['replica_z_hex']])
    sigma = np.array([float.fromhex(v) for v in truth['sigma_hex']])
    jac = np.array(control['canonical_jacobian'], dtype=float)
    scales = np.array(control['truth_sensitivity']['column_scales_GeV2'])
    G = (jac / sigma[:, None]) * scales[None, :]
    if noise.shape != (len(replicas), 6) or G.shape != (6, 2):
        raise ValueError("Unexpected observation or parameter shape")
    if not np.all(np.isfinite(noise)) or not np.all(np.isfinite(G)):
        raise ValueError("Nonfinite input")
    if not np.allclose(G, control['truth_sensitivity']['scaled_whitened_jacobian'],
                       rtol=5e-14, atol=5e-14):
        raise ValueError("Reconstructed scaled-whitened Jacobian mismatch")
    if np.linalg.matrix_rank(G) != 2:
        raise ValueError("Rank is not two")
    Q, _ = np.linalg.qr(G, mode='reduced')
    P = Q @ Q.T
    linear = np.sum((noise @ Q)**2, axis=1)
    theta_truth = np.array([float.fromhex(v) for v in truth['truth_theta_hex']])
    lo = (np.array([.10, .00]) - theta_truth)/scales
    hi = (np.array([.50, .10]) - theta_truth)/scales
    linear_box, box_ids = box_linear_statistics(G, noise, lo, hi)
    nonlinear = np.array([r['delta_chi2'] for r in replicas], dtype=float)
    if not np.all([r['delta_chi2_valid'] for r in replicas]):
        raise ValueError("Invalid recorded likelihood ratio")
    nonlinear_ids = [r['id'] for r in replicas if r['A']['selected']['boundary_hit']]
    if np.max(linear_box - linear) > 1e-10:
        raise AssertionError("Restricted improvement exceeded unrestricted improvement")
    checks = {
        'jacobian_reconstruction': True, 'rank_two': True,
        'projector_idempotence_max_abs': float(np.max(abs(P@P-P))),
        'projector_symmetry_max_abs': float(np.max(abs(P-P.T))),
        'box_cannot_increase_improvement_max_violation': float(np.max(linear_box-linear)),
        'unconstrained_vs_nonlinear_different_95_memberships': [int(i) for i in
            np.flatnonzero((linear <= -2*math.log(.05)) != (nonlinear <= -2*math.log(.05)))],
    }
    k = int(np.sum(nonlinear > -2*math.log(.05)))
    rows = [{'id': i, 'linear_unconstrained': float(linear[i]),
             'linear_same_box': float(linear_box[i]), 'nonlinear_saved': float(nonlinear[i]),
             'linear_box_boundary': i in box_ids, 'nonlinear_boundary': i in nonlinear_ids}
            for i in ids]
    return {
        'scope': 'post-hoc saved-array diagnosis, not a new extraction or calibration',
        'provenance': provenance,
        'environment': {'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform()},
        'mathematics': {
            'G': 'Sigma^{-1/2} J_star diag(0.4,0.1)',
            'P': 'Q Q^T from reduced QR of G',
            'linear_statistic': '||Q^T z||^2',
            'distribution': 'Exactly chi-square(2) for fixed rank-2 G and z~N(0,I), no parameter bounds',
            'box_domain': 'Same canonical a and g2 bounds as H004, applied to tangent model',
        },
        'threshold_95': -2*math.log(.05),
        'summaries': {'linear_unconstrained': describe(linear),
                      'linear_same_box': describe(linear_box), 'nonlinear_saved': describe(nonlinear)},
        'linear_box_boundary_ids': box_ids, 'nonlinear_boundary_ids': nonlinear_ids,
        'checks': checks,
        'null_reference_only': {
            'n_misses': k,
            'probability_at_least_this_many_misses_if_coverage_exactly_95_percent':
                binomial_upper_tail(len(replicas), k, .05),
            'warning': 'Post-hoc tail probability, not a prespecified model-selection or calibration test',
        },
        'paired_rows': rows,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.inputs.read_bytes()
    manifest = json.loads(args.inputs.with_name("inputs.manifest.json").read_text())
    if len(raw) != manifest["bytes"] or hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
        raise ValueError("Coverage input digest mismatch")
    if args.output.exists():
        raise FileExistsError("Choose a fresh output")
    projection = json.loads(raw)
    report = calculate(projection["inputs"], projection["provenance"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report["summaries"], indent=2))


if __name__ == "__main__":
    main()
