#!/usr/bin/env python3
"""Compare all retained campaign fields except elapsed wall-clock times."""
import argparse
import hashlib
import json
from pathlib import Path

FILES = ("data.json", "fits.json", "rank_check.json", "consequences.json", "rejection.json")


def without_times(value):
    if isinstance(value, dict):
        return {k: without_times(v) for k, v in value.items() if k != "elapsed_seconds"}
    if isinstance(value, list):
        return [without_times(v) for v in value]
    return value


def compare(reference, replay):
    records = []
    for name in FILES:
        left, right = (reference/name).read_bytes(), (replay/name).read_bytes()
        a, b = without_times(json.loads(left)), without_times(json.loads(right))
        # float.hex preserves binary64 identity, including signed zero.
        def binary(value):
            if isinstance(value, float):
                return ("float64", value.hex())
            if isinstance(value, dict):
                return {k: binary(v) for k, v in value.items()}
            if isinstance(value, list):
                return [binary(v) for v in value]
            return value
        records.append({"file": name, "reference_sha256": hashlib.sha256(left).hexdigest(),
            "replay_sha256": hashlib.sha256(right).hexdigest(), "binary_values_equal_except_elapsed_seconds": binary(a) == binary(b)})
    return {"status": "passed" if all(r["binary_values_equal_except_elapsed_seconds"] for r in records) else "failed",
        "scope": "all data, fit histories, selected fits, rank diagnostics, consequences and rejection fields; exclude only elapsed_seconds",
        "tolerance": "exact binary64 and nonnumerical field equality", "files": records}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = compare(args.reference, args.replay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(result["status"])
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
