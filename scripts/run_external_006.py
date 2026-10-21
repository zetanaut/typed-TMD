#!/usr/bin/env python3
"""Run a frozen-scope H006 pilot or external observation experiment.

Use the isolated interpreter that built harpy. Outputs must be fresh directories.
The native backend remains process-global and exclusively owned by this run.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
import numpy as np
from typed_tmd.observations import DYBin, ObservationContract, identity
from typed_tmd.artemide_adapter import ArtemideSession


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+"\n")


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_rows(path):
    """Geometry-only selection, fixed before inspecting any injected misuse."""
    lines = Path(path).read_text().splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("Point id,"))
    rows, selected = [], []
    for record in csv.DictReader(lines[index:]):
        if float(record["qTMax[GeV]"])/float(record["Qmin[GeV]"]) > .25:
            continue
        qt = (float(record["qTMin[GeV]"]), float(record["qTMax[GeV]"]))
        factor = float(record["Th.Factor"])
        process = tuple(int(v) for v in record["process id"].split(" - "))
        row = DYBin(record["Point id"], qt,
            (float(record["Qmin[GeV]"]), float(record["Qmax[GeV]"])),
            (float(record["yMin"]), float(record["yMax"])), float(record["s[GeV^2]"]), process,
            record["FiducialCuts"] == "True",
            tuple(float(record[k]) for k in ("kCut1[GeV]", "kCut2[GeV]", "etaMin", "etaMax")),
            factor*(qt[1]-qt[0]))
        rows.append(row)
        selected.append({"row": asdict(row), "source_theory_factor": factor})
    if not 6 <= len(rows) <= 16:
        raise ValueError("Geometry rule produced an unexpected number of bins")
    return tuple(rows), selected


def initialize(build, refined=False):
    runtime, lock = load(build/"runtime.json"), load(build/"external.lock.json")
    config = Path(runtime["refined_config"] if refined else runtime["config"])
    if sha(config) != lock["refined_constants_sha256" if refined else "constants_sha256"]:
        raise ValueError("Native constants identity mismatch")
    backend = Path(runtime["backend_dir"])
    libraries = list((backend/"harpy").glob("artemide*.so"))
    if len(libraries) != 1 or sha(libraries[0]) != runtime["native_library_sha256"]:
        raise ValueError("Compiled native extension differs from build receipt")
    for entry in runtime.get("lhapdf_libraries", []):
        if sha(Path(runtime["lhapdf_prefix"])/"lib"/entry["name"]) != entry["sha256"]:
            raise ValueError("Native LHAPDF library differs from build receipt")
    for name, expected in lock["source_files"].items():
        if sha(backend/name) != expected:
            raise ValueError("Native source identity mismatch: "+name)
    for entry in lock["pdf_inputs"]:
        if sha(Path(runtime["pdf_data_path"])/lock["pdf_set"]/entry["name"]) != entry["sha256"]:
            raise ValueError("Native PDF input mismatch")
    os.environ["LHAPDF_DATA_PATH"] = runtime["pdf_data_path"]
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, str(backend/"harpy"))
    start = time.perf_counter()
    import harpy
    print("Initializing pinned SV19 native backend", flush=True)
    harpy.initialize(str(config))
    print("Configuration loaded; binding the published NP vector and native grid", flush=True)
    harpy.setNPparameters(lock["fixed_parameter_vector"])
    elapsed = time.perf_counter()-start
    print(f"Native initialization and initial grid binding completed in {elapsed:.3f} s", flush=True)
    generated = Path("aTMDe-temporary")
    if generated.exists():
        generated.rename("native_resolved_constants.txt")
    source = Path(runtime["inputs_dir"])/lock["dataset_file"]
    if sha(source) != lock["dataset_sha256"]:
        raise ValueError("Dataset identity mismatch")
    rows, selected = select_rows(source)
    # Physics identity is independent of the observation quadrature refinement.
    kernel_identity = identity(lock)
    minimum = next(item["value"] for item in lock["constant_changes"] if item["key"] == [9, "B", 2])
    session = ArtemideSession(harpy, kernel_identity, lock["fixed_parameter_vector"], (.001, .1),
                              sections=2*minimum if refined else minimum, native_config_sha256=sha(config))
    contract = ObservationContract(rows, session.identity)
    return harpy, session, contract, selected, lock, runtime, elapsed


def compare(a, b, sigma):
    a, b, sigma = map(np.asarray, (a, b, sigma))
    scale = float(np.max(abs(b)))
    allowance = 1e-8*scale+1e-4*abs(b)
    return {"max_absolute": float(np.max(abs(a-b))),
            "component_budget_max_ratio": float(np.max(abs(a-b)/allowance)),
            "whitened_norm": float(np.linalg.norm((a-b)/sigma)),
            "rtol": 1e-4, "atol": 1e-8*scale,
            "component_passed": bool(np.all(abs(a-b) <= allowance)),
            "whitened_passed": bool(np.linalg.norm((a-b)/sigma) <= .05)}


def pilot(build, out, refined=False, previous=None):
    native, session, contract, selected, lock, runtime, elapsed = initialize(build, refined)
    theta = (lock["fixed_parameter_vector"][1],)
    arrays, timings = {}, {}

    def timed(label, f):
        start = time.perf_counter()
        result = tuple(map(float, f()))
        timings[label] = time.perf_counter()-start
        arrays[label] = result
        write(out/"pilot_arrays.json", arrays)
        write(out/"pilot_timings.json", timings)
        print(label, f"{timings[label]:.3f} s", flush=True)
        return result

    native_plan = session.plan(contract)
    central = timed("native", lambda: native_plan.evaluate(theta))
    sigma = np.maximum(.02*abs(np.array(central)), 1e-4*np.max(abs(np.array(central[:-2]))))
    write(out/"candidate.json", {"selection_rule": "all A8-00y04 bins with qT_upper/Q_lower <= 0.25, original source order",
        "rows": selected, "parameter": "SV19.c0", "truth": theta, "domain": [.001, .1],
        "domain_rationale": "positive local subdomain of author fit's [0.001,5.0], with other published parameters fixed",
        "training": list(range(len(selected)-2)), "held_out": [len(selected)-2, len(selected)-1],
        "status": "precision pilot; no misuse or fit evaluated", "physics_identity": session.identity})
    if refined:
        old = load(previous/"pilot_arrays.json")["native"]
        checks = {"native_Qy_and_qT_refinement": compare(central, old, sigma)}
        checks["native_Qy_and_qT_refinement"]["refinement_passed"] = checks["native_Qy_and_qT_refinement"]["whitened_norm"] <= .05/3
        previous_arrays = load(previous/"pilot_arrays.json")
        for label, value in previous_arrays.items():
            if label.startswith("GL_"):
                checks["refined_native_vs_"+label] = compare(value, central, sigma)
        session.orders = (16, 16, 8)
        independent = session.plan(contract, operation="independent_bin_average")
        derivatives = []
        for step in (.0001, .00005):
            plus = timed("sensitivity_plus_"+str(step), lambda: independent.evaluate((theta[0]+step,)))
            minus = timed("sensitivity_minus_"+str(step), lambda: independent.evaluate((theta[0]-step,)))
            derivatives.append((np.asarray(plus)-minus)/(2*step))
        norm = float(np.linalg.norm(derivatives[-1][:-2]/sigma[:-2]))
        write(out/"rank_pilot.json", {"parameter": "SV19.c0", "singular_value": norm,
            "rank": int(norm > 1e-8), "steps": [.0001, .00005],
            "relative_step_change": float(np.linalg.norm((derivatives[0]-derivatives[1])[:-2]/sigma[:-2])/norm),
            "scope": "local training sensitivity before any misuse impact or fit"})
    else:
        # N1 is assembled directly from source rows, without typed observation
        # helpers; N2 uses the adapter on the identical native scalar requests.
        raw_checks = []
        for probe, value in enumerate((theta[0], .02, theta[0])):
            native.setNPparameters([lock["fixed_parameter_vector"][0], value, *lock["fixed_parameter_vector"][2:]])
            direct, raw = [], []
            # Full central batch plus the first source bin for off-central
            # and reset probes. The bin choice is fixed before any effect.
            request_rows = selected if probe == 0 else selected[:1]
            for item in request_rows:
                row = item["row"]
                raw.append(float(native.DY.xSec(row["process"], row["s"], row["qT"], row["Q"], row["y"],
                    row["include_cuts"], row["cuts"])))
                direct.append(raw[-1]*item["source_theory_factor"])
            typed = central if probe == 0 else session.plan(replace(contract, bins=contract.bins[:1])).evaluate((value,))
            raw_checks.append({"c0": value, "requests": request_rows, "native_raw_yields_pb": raw,
                "direct_observations": direct, "typed_observations": typed, "binary_equal": bool(np.array_equal(direct, typed))})
            write(out/"native_typed_requests_and_results.json", raw_checks)
            if not np.array_equal(direct, typed):
                raise AssertionError("Identical native/typed requests did not agree bitwise")
        checks = {"native_typed_central_offcentral_reset": {"passed": True, "binary_equal": True,
                                                          "parameters": [theta[0], .02, theta[0]]}}
        for orders in ((8, 8, 4), (16, 8, 4), (8, 16, 4), (8, 8, 8), (16, 16, 8)):
            session.orders = orders
            plan = session.plan(contract, operation="independent_bin_average")
            timed("GL_"+"_".join(map(str, orders)), lambda: plan.evaluate(theta))
        base = arrays["GL_8_8_4"]
        for label in ("GL_16_8_4", "GL_8_16_4", "GL_8_8_8"):
            checks[label+"_refinement"] = compare(arrays[label], base, sigma)
            checks[label+"_refinement"]["refinement_passed"] = checks[label+"_refinement"]["whitened_norm"] <= .05/3
        checks["native_independent"] = compare(arrays["GL_16_16_8"], central, sigma)
    write(out/"pilot_checks.json", checks)
    write(out/"environment.json", {"python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
          "initialization_seconds": elapsed, "native_runtime": runtime, "thread_count": 1})
    passed = all(all(v for k, v in check.items() if k.endswith("passed")) for check in checks.values())
    write(out/"summary.json", {"handoff_id": "typed-tmd-006", "status": "passed" if passed else "failed",
          "scope": "native semantic/precision pilot; no impact experiment", "checks": checks,
          "native_calls": session.calls, "effect_size": "not_assessed"})
    if not passed:
        raise RuntimeError("Precision pilot failed; retain arrays and diagnose before freezing")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--stage", choices=("pilot", "native_refinement", "campaign", "validate", "timing", "refine_selected"), default="pilot")
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--plan", type=Path, default=ROOT/"configs/006")
    ap.add_argument("--point-label", help="Validate one preselected point in an isolated process; does not alter the experiment")
    args = ap.parse_args()
    if args.point_label is not None and args.stage not in ("validate", "refine_selected"):
        raise ValueError("A point label is only valid for point validation stages")
    args.output, args.build = args.output.resolve(), args.build.resolve()
    if args.previous is not None:
        args.previous = args.previous.resolve()
    args.plan = args.plan.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output/"invocation.json", {"argv": sys.argv, "start_utc": datetime.now(timezone.utc).isoformat(),
          "script_sha256": sha(__file__), "interpreter": sys.executable,
          "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in
            [ROOT/"scripts/external_campaign_006.py", *sorted((ROOT/"src/typed_tmd").glob("*observation*.py")), ROOT/"src/typed_tmd/artemide_adapter.py"]}})
    os.chdir(args.output)
    try:
        if args.stage == "native_refinement" and args.previous is None:
            raise ValueError("Native refinement requires --previous pilot directory")
        if args.stage in ("pilot", "native_refinement"):
            pilot(args.build, args.output, args.stage == "native_refinement", args.previous)
        else:
            from external_campaign_006 import campaign, validate_selected, measure_overhead
            frozen = load(args.plan/"FREEZE.json")
            for filename, expected in frozen["files"].items():
                if sha(args.plan/filename) != expected:
                    raise ValueError("Frozen experiment identity mismatch: "+filename)
            if sha(args.build/"external.lock.json") != frozen["files"]["external.lock.json"]:
                raise ValueError("Build inputs differ from frozen experiment")
            specification = load(args.plan/"experiment_plan.json")
            native, session, contract, selected, lock, runtime, elapsed = initialize(args.build, args.stage == "refine_selected")
            if contract.digest != load(args.plan/"observation_contract.json")["contract_digest"]:
                raise ValueError("Runtime observation differs from frozen contract")
            write(args.output/"environment.json", {"python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
                "initialization_seconds": elapsed, "native_runtime": runtime, "thread_count": 1, "freeze": frozen})
            if args.stage == "campaign":
                _, _, fits = campaign(native, session, contract, lock, specification, args.output, write, compare)
                passed = all(f["all_starts_successful"] for f in fits.values())
            elif args.stage == "validate":
                data, fits = load(args.previous/"data.json"), load(args.previous/"fits.json")
                checks = validate_selected(session, contract, lock, specification,
                    np.asarray(data["truth"]), np.asarray(data["sigma"]), fits, args.output, write, compare, point_label=args.point_label)
                passed = all(v for point in checks.values() for check in point.values() for k,v in check.items() if k.endswith("passed"))
            elif args.stage == "refine_selected":
                previous = load(args.previous/"selected_validation_arrays.json")
                if args.point_label is not None and args.point_label not in previous:
                    raise ValueError("Unknown selected parameter point")
                sigma = np.maximum(.02*abs(np.asarray(previous["truth"]["vectors"]["native"])),
                                   1e-4*max(abs(v) for v in previous["truth"]["vectors"]["native"][:-2]))
                checks, arrays = {}, {}
                for label, record in previous.items():
                    if args.point_label is not None and label != args.point_label:
                        continue
                    print("Native refinement", label, flush=True)
                    arrays[label] = session.plan(contract).evaluate((record["c0"],))
                    check = compare(arrays[label], record["vectors"]["native"], sigma)
                    check["refinement_passed"] = check["whitened_norm"] <= .05/3
                    checks[label] = check
                    write(args.output/"native_refinement_arrays.json", arrays)
                    write(args.output/"native_refinement_checks.json", checks)
                passed = all(v for check in checks.values() for k,v in check.items() if k.endswith("passed"))
            else:
                measure_overhead(native, session, contract, lock, specification, args.output, write)
                passed = True
            write(args.output/"summary.json", {"status": "passed" if passed else "failed", "stage": args.stage,
                  "native_calls": session.calls, "freeze_identity": identity(frozen)})
            if not passed:
                raise RuntimeError(args.stage+" failed; retain all results")
    except BaseException as exc:
        write(args.output/"failure_summary.json", {"status": "failed", "error": repr(exc)})
        raise


if __name__ == "__main__":
    main()
