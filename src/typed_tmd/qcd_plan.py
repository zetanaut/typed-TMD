"""Deterministic finite H002 quadrature and native-query planner."""
from __future__ import annotations

import bisect
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .provider_replay import digest, hex_float, parse_hex, query_id, write_document

PIDS = (-3, -2, -1, 1, 2, 3)


def profile_mu(b: float, bmax: float = 0.5) -> float:
    c0 = 2 * math.exp(-math.euler_gamma) if hasattr(math, "euler_gamma") else 2 * math.exp(-0.5772156649015329)
    return c0 * math.sqrt(1 + (b / bmax) ** 2) / b


def mapped_b(mu: float, bmax: float = 0.5) -> float | None:
    c0 = 2 * math.exp(-0.5772156649015329)
    radicand = mu * mu - (c0 / bmax) ** 2
    return c0 / math.sqrt(radicand) if radicand > 0 else None


def physical_points(config: dict) -> list[dict]:
    process = config["process"]
    points = []
    for Q in process["Q_GeV"]:
        xa = Q * math.exp(process["rapidity_y"]) / process["sqrt_s_GeV"]
        xb = Q * math.exp(-process["rapidity_y"]) / process["sqrt_s_GeV"]
        for fraction in process["qT_over_Q"]:
            points.append({"Q_GeV": Q, "qT_GeV": Q * fraction, "x_a": xa, "x_b": xb})
    return points


def gl_panel(left: float, right: float, order: int) -> list[list[str]]:
    roots, weights = np.polynomial.legendre.leggauss(order)
    return [[hex_float((left + right) / 2 + (right - left) * float(r) / 2),
             hex_float((right - left) * float(w) / 2)] for r, w in zip(roots, weights)]


def composite_panel(left: float, right: float, divisions: int) -> list[list[str]]:
    nodes = []
    for j in range(divisions):
        a = left + (right - left) * j / divisions
        b = left + (right - left) * (j + 1) / divisions
        m, h = (a + b) / 2, (b - a) / (2 * math.sqrt(3))
        nodes.extend([[hex_float(m - h), hex_float((b - a) / 2)],
                      [hex_float(m + h), hex_float((b - a) / 2)]])
    return nodes


def scale_panel(lo: float, hi: float, variant: str) -> list[list[str]]:
    if variant.startswith("P"):
        pairs = gl_panel(math.log(lo), math.log(hi), int(variant[1:]))
    else:
        pairs = composite_panel(math.log(lo), math.log(hi), int(variant[1:]))
    return [[hex_float(math.exp(parse_hex(t))), w, t] for t, w in pairs]


def build_plan(inspection: dict, config: dict, config_bytes: bytes) -> dict:
    if inspection["schema"] != "typed_tmd.provider_inspection.v1":
        raise ValueError("wrong_inspection_schema")
    ip = inspection["payload"]
    if ip["set"] != "CT18NNLO" or ip["member"] != 0 or ip["effective"]["AlphaS_Type"]["value"] != "ipol":
        raise ValueError("wrong_native_profile")
    knots = [parse_hex(x) for x in ip["alpha_qs_hex"]]
    if any(a > b for a, b in zip(knots, knots[1:])):
        raise ValueError("unordered_native_coupling_knots")
    unique_knots = sorted(set(knots))
    points = physical_points(config)
    xs = sorted({point[key] for point in points for key in ("x_a", "x_b")})
    windows = config["fourier_windows_GeV_inv"]
    base = config["numerical_initial_plan"]["base_b_breakpoints_GeV_inv"]
    # The observed bottom threshold is a useful b-panel join. Scale
    # integrations independently split at every native coupling knot.
    join_scales = [4.75]
    mapped = [b for mu in join_scales if (b := mapped_b(mu)) is not None]
    b_variants = ("P16", "P32", "R16", "R32", "R64")
    scale_variants = ("P16", "P32", "R4", "R8")
    b_plans = {}
    all_b: dict[str, set[str]] = {}
    for window in windows:
        low, high = float(window["lower"]), float(window["upper"])
        edges = sorted({low, high, *(x for x in base + mapped if low < x < high)})
        if low <= 0 or high <= low:
            raise ValueError("invalid_window")
        b_plans[window["id"]] = {"edges_hex": [hex_float(x) for x in edges], "variants": {}}
        for variant in b_variants:
            nodes = []
            for lo, hi in zip(edges, edges[1:]):
                nodes.extend(gl_panel(lo, hi, int(variant[1:])) if variant.startswith("P")
                             else composite_panel(lo, hi, int(variant[1:])))
            b_plans[window["id"]]["variants"][variant] = nodes
            for b_hex, _ in nodes:
                all_b.setdefault(b_hex, set()).add("production" if variant.startswith("P") else "reference")
                if variant in ("P16", "R16"):
                    all_b[b_hex].add("refinement")
    for b in config["b_point_grid_GeV_inv"]:
        all_b.setdefault(hex_float(b), set()).add("pointwise")
    mu_values = {hex_float(profile_mu(parse_hex(bh))) for bh in all_b}
    mu_values.update(hex_float(x) for x in (5.0, 10.0, *config["process"]["Q_GeV"]))
    scale_plans = {}
    for variant in scale_variants:
        full = []
        for lo, hi in zip(unique_knots, unique_knots[1:]):
            full.append({"lo_hex": hex_float(lo), "hi_hex": hex_float(hi),
                         "nodes": scale_panel(lo, hi, variant)})
        partial = {}
        for mh in sorted(mu_values):
            mu = parse_hex(mh)
            index = bisect.bisect_right(unique_knots, mu) - 1
            if index < 0 or mu > unique_knots[-1]:
                raise ValueError("matching_or_fixed_scale_outside_coupling_support: " + mh)
            lo = unique_knots[index]
            partial[mh] = {"lower_knot_index": index,
                           "nodes": [] if mu == lo else scale_panel(lo, mu, variant)}
        scale_plans[variant] = {"full": full, "partial": partial}
    requests: dict[str, dict] = {}

    def request(kind: str, coords: dict, role: str) -> None:
        qid = query_id(kind, coords)
        if qid not in requests:
            requests[qid] = {"query_id": qid, "kind": kind, "coordinates": coords, "roles": set()}
        requests[qid]["roles"].add(role)

    for bh, roles in all_b.items():
        mu = profile_mu(parse_hex(bh))
        for x in xs:
            for pid in PIDS:
                coords = {"pid": pid, "x_hex": hex_float(x), "mu_GeV_hex": hex_float(mu)}
                for role in roles:
                    request("pdf_value", coords, role)
    for variant, table in scale_plans.items():
        role = "production" if variant.startswith("P") else "reference"
        for panel in table["full"]:
            for mh, _, _ in panel["nodes"]:
                request("alpha_s_value", {"mu_GeV_hex": mh}, role)
        for part in table["partial"].values():
            for mh, _, _ in part["nodes"]:
                request("alpha_s_value", {"mu_GeV_hex": mh}, role)
    # A fresh native subset tests every current flavor/x, plus both profile ends.
    for point in points:
        for x in (point["x_a"], point["x_b"]):
            for pid in PIDS:
                request("pdf_value", {"pid": pid, "x_hex": hex_float(x),
                                      "mu_GeV_hex": hex_float(point["Q_GeV"])}, "audit")
    for b in (12.0, 0.000025):
        for pid in (2, -2):
            request("pdf_value", {"pid": pid, "x_hex": hex_float(points[0]["x_a"]),
                                  "mu_GeV_hex": hex_float(profile_mu(b))}, "audit")
    for mu in (profile_mu(12.0), 5.0, 10.0, *config["process"]["Q_GeV"], profile_mu(0.000025)):
        request("alpha_s_value", {"mu_GeV_hex": hex_float(mu)}, "audit")
    for x in xs:
        for pid in PIDS:
            request("pdf_value", {"pid": pid, "x_hex": hex_float(x),
                                  "mu_GeV_hex": hex_float(10.0)}, "wrong_boundary_control")
    for q in requests.values():
        q["roles"] = sorted(q["roles"])
    provider_id = digest({"set": ip["set"], "member": ip["member"],
                          "files": ip["files"], "effective": ip["effective"]})
    payload = {"set": "CT18NNLO", "member": 0, "provider_id": provider_id,
               "inspection_sha256": inspection["payload_sha256"],
               "benchmark_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
               "points": [{key: hex_float(value) for key, value in p.items()} for p in points],
               "x_values_hex": [hex_float(x) for x in xs],
               "b_plans": b_plans, "scale_plans": scale_plans,
               "alpha_knots_hex": [hex_float(x) for x in unique_knots],
               "query_counts": {"pdf": sum(q["kind"] == "pdf_value" for q in requests.values()),
                                "alpha_s": sum(q["kind"] == "alpha_s_value" for q in requests.values())},
               "queries": sorted(requests.values(), key=lambda q: q["query_id"]),
               "support_policy": "native inRangeXQ plus scalar bounds; alpha_s within native ipol knots; no extrapolation",
               "pdf_knot_api": "unavailable_in_observed_binding; b convergence measured independently",
               "quadrature_backend": {"production": "numpy.polynomial.legendre.leggauss", "numpy": np.__version__,
                                       "reference": "hard-coded composite two-point Gauss"}}
    return payload


def main() -> None:
    import argparse
    from .provider_replay import document
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    inspection = document(Path(args.inspection))
    data = Path(args.config).read_bytes()
    payload = build_plan(inspection, json.loads(data), data)
    doc = write_document(Path(args.output), "typed_tmd.provider_query_plan.v1", payload)
    print(json.dumps({"payload_sha256": doc["payload_sha256"], **payload["query_counts"]}))


if __name__ == "__main__":
    main()
