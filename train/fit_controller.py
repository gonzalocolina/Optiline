#!/usr/bin/env python3
"""Fit NSCECTL2 search-budget weights from LMR telemetry.

Target: reduce less when a reduced search needed a research; reduce more when
the reduced search already cut. Features are the same ones the C++ controller
uses (depth, index, hist, improving, cut_node, quiet). Export is MIT-clean.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("NumPy is required: python3 -m pip install numpy", flush=True)
    raise


def load_rows(path: Path) -> np.ndarray:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("key"):
                continue
            parts = line.split(",")
            if len(parts) < 11:
                continue
            # key,depth,index,R,score,cutoff,hist,improving,cut_node,quiet,researched
            depth = int(parts[1])
            index = int(parts[2])
            cutoff = int(parts[5])
            hist = int(parts[6])
            improving = int(parts[7])
            cut_node = int(parts[8])
            quiet = int(parts[9])
            researched = int(parts[10])
            if researched:
                target = -1.0
            elif cutoff:
                target = 1.0
            else:
                target = 0.0
            rows.append(
                (
                    depth / 8.0,
                    index / 4.0,
                    max(-2000, min(2000, hist)) / 200.0,
                    float(improving),
                    float(cut_node),
                    float(quiet),
                    1.0,
                    target,
                )
            )
    if not rows:
        raise ValueError(f"no telemetry rows in {path}")
    return np.asarray(rows, dtype=np.float64)


def fit(features: np.ndarray, target: np.ndarray) -> np.ndarray:
    # Ridge so a small sample cannot explode the integer weights.
    lam = 1e-2
    gram = features.T @ features + lam * np.eye(features.shape[1])
    return np.linalg.solve(gram, features.T @ target)


def export_nscectl2(path: Path, weights: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = struct.pack(
        "<8s10i",
        b"NSCECTL2",
        weights["w_depth"],
        weights["w_index"],
        weights["w_eval_gap"],
        weights["w_quiet"],
        weights["w_policy"],
        weights["bias"],
        weights["w_hist"],
        weights["w_improving"],
        weights["w_cut"],
        weights["w_see"],
    )
    path.write_bytes(packed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry", default="train/data/lmr_telemetry.csv")
    parser.add_argument("--output", default="nets/controller_fitted.bin")
    parser.add_argument("--scale", type=float, default=250.0, help="matches C++ raw/250 mapping")
    args = parser.parse_args()

    table = load_rows(Path(args.telemetry))
    x = table[:, :-1]
    y = table[:, -1] * args.scale
    coef = fit(x, y)
    # Map least-squares coeffs onto the integer controller fields.
    # Feature layout: depth/8, index/4, hist/200, improving, cut, quiet, bias.
    weights = {
        "w_depth": int(np.clip(np.rint(coef[0]), -4000, 4000)),
        "w_index": int(np.clip(np.rint(coef[1]), -4000, 4000)),
        "w_eval_gap": 1,
        "w_quiet": int(np.clip(np.rint(coef[5]), -4000, 4000)),
        "w_policy": -1,
        "bias": int(np.clip(np.rint(coef[6]), -4000, 4000)),
        "w_hist": int(np.clip(np.rint(coef[2]), -4000, 4000)),
        "w_improving": int(np.clip(np.rint(coef[3]), -4000, 4000)),
        "w_cut": int(np.clip(np.rint(coef[4]), -4000, 4000)),
        "w_see": 0,
    }
    export_nscectl2(Path(args.output), weights)
    pred = x @ coef
    mae = float(np.mean(np.abs(pred - y)))
    print(
        {
            "rows": int(len(table)),
            "mae_raw": mae,
            "weights": weights,
            "output": str(args.output),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
