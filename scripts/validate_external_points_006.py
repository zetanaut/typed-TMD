#!/usr/bin/env python3
"""Run fixed validation points in isolated processes and verify exact coverage.

Only execution scheduling changes: every process owns a fresh native engine
with the same frozen settings. Not used for checking-overhead measurement.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


def read(p):
    return json.loads(p.read_text())


def write(p, x):
    p.write_text(json.dumps(x, indent=2, sort_keys=True, allow_nan=False)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("validate", "refine_selected"), required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.workers <= 5:
        raise ValueError("Use between one and five isolated workers")
    previous, out = args.previous.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    if args.stage == "validate":
        labels = ["truth", *sorted(read(previous/"fits.json")), "geometry"]
        products = ["selected_validation_arrays.json", "selected_validation_checks.json"]
    else:
        labels = list(read(previous/"selected_validation_arrays.json"))
        products = ["native_refinement_arrays.json", "native_refinement_checks.json"]
    write(out/"schedule.json", {"stage": args.stage, "labels": labels, "workers": args.workers,
        "isolation": "separate subprocess/native state for every point; no IPC or scientific response cache",
        "time_scope": "parallel validation throughput, not checking overhead", "start_utc": datetime.now(timezone.utc).isoformat()})

    def run(label):
        argv = [sys.executable, "-u", str(Path(__file__).with_name("run_external_006.py")),
            "--stage", args.stage, "--build", str(args.build.resolve()), "--previous", str(previous),
            "--output", str(out/label), "--plan", str(args.plan.resolve()), "--point-label", label]
        start = time.perf_counter()
        with (out/(label+".log")).open("w") as log:
            result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
        receipt = {"label": label, "command": argv, "exit_code": result.returncode, "elapsed_seconds": time.perf_counter()-start}
        write(out/(label+"_command.json"), receipt)
        print(label, result.returncode, flush=True)
        return receipt

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        receipts = list(pool.map(run, labels))
    write(out/"commands.json", receipts)
    for name in products:
        merged = {}
        for label in labels:
            p = out/label/name
            if p.exists():
                value = read(p)
                if set(merged) & set(value):
                    raise ValueError("Duplicate validation result")
                merged.update(value)
        expected = set(labels)-({"geometry"} if "arrays" in name else set())
        if set(merged) != expected:
            write(out/"summary.json", {"status": "failed", "missing_product": name, "expected": sorted(expected), "found": sorted(merged)})
            raise ValueError("Missing required validation points")
        write(out/name, merged)
    if args.stage == "validate" and (out/"geometry/geometry_arrays.json").exists():
        write(out/"geometry_arrays.json", read(out/"geometry/geometry_arrays.json"))
    passed = all(r["exit_code"] == 0 and read(out/r["label"]/"summary.json")["status"] == "passed" for r in receipts)
    write(out/"summary.json", {"status": "passed" if passed else "failed", "stage": args.stage,
        "point_count": len(labels), "all_required_points_present": True, "isolated_workers": args.workers})
    if not passed:
        raise RuntimeError("Validation failed; results retained")


if __name__ == "__main__":
    main()
