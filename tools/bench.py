#!/usr/bin/env python3
"""Repeat the fixed-work benchmark and report robust speed statistics."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_result(line: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for token in line.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            values[key] = float(value)
        except ValueError:
            continue
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", default=str(ROOT / "build" / "nsce_bench"))
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--eval-file", default="internal")
    parser.add_argument("--state", choices=("cold", "warm"), default="cold")
    args = parser.parse_args()
    if args.runs <= 0:
        parser.error("--runs must be positive")

    command = [
        args.bench,
        str(args.depth),
        str(args.threads),
        str(args.repetitions),
        args.eval_file,
        "0",
        args.state,
    ]
    results = []
    for _ in range(args.runs):
        completed = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
        result = parse_result(completed.stdout.strip().splitlines()[-1])
        if "nps" not in result:
            raise RuntimeError(f"benchmark did not report nps: {completed.stdout}")
        results.append(result)

    nps = [result["nps"] for result in results]
    median = statistics.median(nps)
    mad = statistics.median(abs(value - median) for value in nps)
    report = {
        "command": command,
        "runs": args.runs,
        "nps_median": median,
        "nps_mad": mad,
        "nps_min": min(nps),
        "nps_max": max(nps),
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "samples": results,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
