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


def cp_to_wdl(cp: float, scale: float) -> float:
    cp = max(-8000.0, min(8000.0, cp))
    return 1.0 / (1.0 + math.exp(-cp / scale))


def affine_fit(x: list[int], y: list[int]) -> dict[str, float]:
    """OLS y ≈ slope * x + intercept, plus through-origin scale and std ratio."""
    n = len(x)
    if n == 0:
        return {
            "samples": 0,
            "slope": 0.0,
            "intercept": 0.0,
            "origin_scale": 0.0,
            "std_x": 0.0,
            "std_y": 0.0,
            "std_ratio_y_over_x": 0.0,
            "eval_scale_permille": 1000,
        }
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    var_x = sum((value - mean_x) ** 2 for value in x)
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    slope = cov / var_x if var_x else 0.0
    intercept = mean_y - slope * mean_x
    xx = sum(value * value for value in x)
    origin_scale = sum(xi * yi for xi, yi in zip(x, y)) / xx if xx else 0.0
    std_x = (var_x / n) ** 0.5
    std_y = (sum((value - mean_y) ** 2 for value in y) / n) ** 0.5
    return {
        "samples": n,
        "slope": slope,
        "intercept": intercept,
        "origin_scale": origin_scale,
        "std_x": std_x,
        "std_y": std_y,
        "std_ratio_y_over_x": (std_y / std_x) if std_x else 0.0,
        "eval_scale_permille": int(max(250, min(4000, round(1000.0 * origin_scale)))),
    }


def summarize(predictions: list[int], targets: list[int], wdl_scale: float) -> dict[str, float]:
    errors = [prediction - target for prediction, target in zip(predictions, targets)]
    return {
        "samples": len(errors),
        "mae_cp": sum(abs(error) for error in errors) / len(errors),
        "rmse_cp": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "sign_accuracy": sum(
            (prediction >= 0) == (target >= 0)
            for prediction, target in zip(predictions, targets)
        )
        / len(errors),
        "wdl_mae": sum(
            abs(cp_to_wdl(prediction, wdl_scale) - cp_to_wdl(target, wdl_scale))
            for prediction, target in zip(predictions, targets)
        )
        / len(errors),
    }


def group_key(record: dict) -> str:
    for key in ("source_game", "game_id", "opening", "source"):
        if record.get(key):
            value = str(record[key])
            if value not in {"self_play", "random_walk"}:
                return f"{key}:{value}"
    return "fen:" + record.get("fen", "")


def phase_key(record: dict) -> str:
    if record.get("phase"):
        return str(record["phase"])
    board = record.get("fen", "").split(" ", 1)[0]
    weights = {"q": 4, "r": 2, "b": 1, "n": 1}
    phase = sum(weights.get(piece.lower(), 0) for piece in board)
    return "opening" if phase >= 14 else "middlegame" if phase >= 7 else "endgame"


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
    parser.add_argument("--target-mode", choices=("cp", "wdl"), default="cp")
    parser.add_argument("--wdl-scale", type=float, default=400.0)
    args = parser.parse_args()

    records = []
    for line in Path(args.data).read_text().splitlines():
        record = json.loads(line)
        fen = record.get("fen", "")
        if record.get("score_cp") is None:
            continue
        digest = hashlib.sha256(group_key(record).encode()).digest()
        if int.from_bytes(digest[:4], "little") % 10 == 0:
            records.append(record)
    if not records:
        raise RuntimeError("held-out split is empty")

    baseline = UciEngine([args.engine], "baseline")
    trained = UciEngine([args.engine], "trained")
    extras = "true" if args.use_extras else "false"
    baseline.apply_options({"EvalFile": "internal", "UseExtras": "true"})
    trained.apply_options({"EvalFile": args.network, "UseExtras": extras})
    targets: list[int] = []
    baseline_values: list[int] = []
    trained_values: list[int] = []
    composite_deltas: list[int] = []
    phases: dict[str, dict[str, list[int]]] = {}
    try:
        for record in records:
            target = int(record["score_cp"])
            baseline_value = baseline.evaluate(record["fen"])
            trained_value = trained.evaluate(record["fen"])
            details = trained.evaluate_details(record["fen"])
            targets.append(target)
            baseline_values.append(baseline_value)
            trained_values.append(trained_value)
            composite_deltas.append(trained_value - details.get("eval", trained_value))
            phase = phase_key(record)
            bucket = phases.setdefault(phase, {"targets": [], "baseline": [], "trained": []})
            bucket["targets"].append(target)
            bucket["baseline"].append(baseline_value)
            bucket["trained"].append(trained_value)
    finally:
        baseline.close()
        trained.close()

    report = {
        "split": "sha256(source-game/opening group) modulo 10 == 0",
        "dataset_sha256": hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(args.engine).read_bytes()).hexdigest(),
        "network_sha256": hashlib.sha256(Path(args.network).read_bytes()).hexdigest(),
        "baseline_options": {"EvalFile": "internal", "UseExtras": True},
        "trained_options": {
            "EvalFile": str(Path(args.network).resolve()),
            "UseExtras": bool(args.use_extras),
        },
        "baseline": summarize(baseline_values, targets, args.wdl_scale),
        "trained": summarize(trained_values, targets, args.wdl_scale),
        "phase_metrics": {
            phase: {
                "baseline": summarize(values["baseline"], values["targets"], args.wdl_scale),
                "trained": summarize(values["trained"], values["targets"], args.wdl_scale),
            }
            for phase, values in sorted(phases.items())
        },
        "runtime_composite": {
            "max_abs_delta_cp": max(abs(delta) for delta in composite_deltas),
            "samples": len(composite_deltas),
        },
        "target_contract": {"mode": args.target_mode, "wdl_scale": args.wdl_scale},
        "affine": {
            "baseline_from_trained": affine_fit(trained_values, baseline_values),
            "labels_from_baseline": affine_fit(baseline_values, targets),
            "labels_from_trained": affine_fit(trained_values, targets),
        },
    }
    report["mae_improvement_cp"] = report["baseline"]["mae_cp"] - report["trained"]["mae_cp"]
    report["mae_improvement_percent"] = (
        100.0 * report["mae_improvement_cp"] / report["baseline"]["mae_cp"]
        if report["baseline"]["mae_cp"]
        else 0.0
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
