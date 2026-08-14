#!/usr/bin/env python3
"""Compare internal HCE-distilled and trained NNUE on the held-out FEN split."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine  # noqa: E402


def summarize(errors: list[int]) -> dict[str, float]:
    return {
        "samples": len(errors),
        "mae_cp": sum(abs(error) for error in errors) / len(errors),
        "rmse_cp": math.sqrt(sum(error * error for error in errors) / len(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    parser.add_argument("--data", default=str(ROOT / "train/data/nnue_stockfish_d8.jsonl"))
    parser.add_argument("--network", default=str(ROOT / "nets/nnue_trained.bin"))
    parser.add_argument("--output", default=str(ROOT / "nets/nnue_validation.json"))
    parser.add_argument(
        "--use-extras",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="UseExtras on the candidate net (KAT should pass --no-use-extras)",
    )
    args = parser.parse_args()

    records = []
    for line in Path(args.data).read_text().splitlines():
        record = json.loads(line)
        fen = record.get("fen", "")
        if record.get("score_cp") is None:
            continue
        digest = hashlib.sha256(fen.encode()).digest()
        if int.from_bytes(digest[:4], "little") % 10 == 0:
            records.append(record)
    if not records:
        raise RuntimeError("held-out split is empty")

    baseline = UciEngine([args.engine], "baseline")
    trained = UciEngine([args.engine], "trained")
    extras = "true" if args.use_extras else "false"
    baseline.apply_options({"EvalFile": "internal", "UseExtras": "true"})
    trained.apply_options({"EvalFile": args.network, "UseExtras": extras})
    baseline_errors: list[int] = []
    trained_errors: list[int] = []
    try:
        for record in records:
            target = int(record["score_cp"])
            baseline_errors.append(baseline.evaluate(record["fen"]) - target)
            trained_errors.append(trained.evaluate(record["fen"]) - target)
    finally:
        baseline.close()
        trained.close()

    report = {
        "split": "sha256(fen) modulo 10 == 0",
        "dataset_sha256": hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(args.engine).read_bytes()).hexdigest(),
        "network_sha256": hashlib.sha256(Path(args.network).read_bytes()).hexdigest(),
        "baseline_options": {"EvalFile": "internal", "UseExtras": True},
        "trained_options": {
            "EvalFile": str(Path(args.network).resolve()),
            "UseExtras": bool(args.use_extras),
        },
        "baseline": summarize(baseline_errors),
        "trained": summarize(trained_errors),
    }
    report["mae_improvement_cp"] = report["baseline"]["mae_cp"] - report["trained"]["mae_cp"]
    report["mae_improvement_percent"] = (
        100.0 * report["mae_improvement_cp"] / report["baseline"]["mae_cp"]
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
