#!/usr/bin/env python3
"""Within-bucket collapse diagnostics for NSCEPER1 MLP nets.

L2mid / L2sat do not decide the next graph change. This report asks whether L2
and the output still vary with the teacher *inside* a material bucket.

Targets: search-cp from a labeled JSONL (default 40k mix). Do not use UHO-only
sets: those are almost all bucket 7, which masquerades as occupancy splits.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from pack_nsceper1 import L2  # noqa: E402
from per1_float_ref import Per1Net, pieces_from_fen, per1_bucket  # noqa: E402

PROBE = [
    ("startpos", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("e4", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"),
    ("d4", "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1"),
]


def wdl(cp: float) -> float:
    x = max(-20.0, min(20.0, float(cp) / 400.0))
    return 1.0 / (1.0 + math.exp(-x))


def stdev(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))


def eta_squared(values: list[float], groups: list[int]) -> float:
    """η² = 1 - SS_within / SS_total. 0 if the neuron is constant."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    ss_tot = sum((x - mean) ** 2 for x in values)
    if ss_tot <= 1e-12:
        return 0.0
    by: dict[int, list[float]] = defaultdict(list)
    for x, g in zip(values, groups):
        by[g].append(x)
    ss_w = 0.0
    for xs in by.values():
        m = sum(xs) / len(xs)
        ss_w += sum((x - m) ** 2 for x in xs)
    return max(0.0, min(1.0, 1.0 - ss_w / ss_tot))


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-12 or dy < 1e-12:
        return float("nan")
    return num / (dx * dy)


def load_labeled(path: Path, limit: int) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if len(out) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            fen = str(row.get("fen", "")).strip()
            if not fen:
                continue
            if "score_cp" in row:
                target = float(row["score_cp"])
            elif "cp" in row:
                target = float(row["cp"])
            else:
                continue
            out.append((fen, target))
    if not out:
        raise SystemExit(f"no labeled FENs in {path}")
    return out


def l2_dist(a: list[int], b: list[int]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def collapse_report(net: Per1Net, labeled: list[tuple[str, float]], pairs: int, seed: int) -> str:
    rng = random.Random(seed)
    buckets: list[int] = []
    targets: list[float] = []
    preds: list[float] = []
    mlps: list[float] = []
    l3bs: list[float] = []
    skips: list[float] = []
    acts: list[list[int]] = []
    for fen, target in labeled:
        pieces, _ = pieces_from_fen(fen)
        buckets.append(per1_bucket(len(pieces)))
        targets.append(target)
        parts = net.eval_parts(fen)
        preds.append(float(parts["total"]))
        mlps.append(float(parts["mlp"]))
        l3bs.append(float(parts["l3b"]))
        skips.append(float(parts["skip"]))
        acts.append(net.l2_crelu(fen))

    lines = [
        f"n={len(labeled)}  pred_std={stdev(preds):.1f}cp/{stdev([wdl(x) for x in preds]):.3f}wdl  "
        f"target_std={stdev(targets):.1f}cp/{stdev([wdl(x) for x in targets]):.3f}wdl",
        f"mlp_std={stdev(mlps):.1f}cp  l3b_std={stdev(l3bs):.1f}cp  skip_std={stdev(skips):.1f}cp",
        "",
        f"{'bkt':>4}  {'n':>5}  {'tgt_std_cp':>11}  {'pred_std_cp':>12}  {'tgt_wdl':>8}  {'pred_wdl':>8}  {'pair_r':>7}",
    ]
    by_idx: dict[int, list[int]] = defaultdict(list)
    for i, b in enumerate(buckets):
        by_idx[b].append(i)

    for b in range(8):
        idx = by_idx.get(b, [])
        if len(idx) < 2:
            continue
        t = [targets[i] for i in idx]
        p = [preds[i] for i in idx]
        pair_r = float("nan")
        if len(idx) >= 8:
            dx: list[float] = []
            dy: list[float] = []
            for _ in range(min(pairs, len(idx) * (len(idx) - 1) // 2)):
                i, j = rng.sample(idx, 2)
                dx.append(l2_dist(acts[i], acts[j]))
                dy.append(abs(targets[i] - targets[j]))
            pair_r = pearson(dx, dy)
        rtxt = f"{pair_r:7.3f}" if pair_r == pair_r else f"{'nan':>7}"
        lines.append(
            f"{b:4d}  {len(idx):5d}  {stdev(t):11.1f}  {stdev(p):12.1f}  "
            f"{stdev([wdl(x) for x in t]):8.3f}  {stdev([wdl(x) for x in p]):8.3f}  {rtxt}"
        )

    lines.append("")
    lines.append(f"{'j':>4}  {'η²_bucket':>10}  {'act_std':>8}")
    cols = list(zip(*acts))
    for j in range(L2):
        col = [float(x) for x in cols[j]]
        lines.append(f"{j:4d}  {eta_squared(col, buckets):10.3f}  {stdev(col):8.2f}")

    lines.append("")
    lines.append("probe (same material bucket 7: startpos / e4 / d4)")
    lines.append(f"{'name':<8}  {'net':>6}  {'mlp':>6}  {'l3b':>6}  {'skip':>6}")
    for name, fen in PROBE:
        parts = net.eval_parts(fen)
        lines.append(
            f"{name:<8}  {parts['total']:+6d}  {parts['mlp']:+6d}  {parts['l3b']:+6d}  {parts['skip']:+6d}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", type=Path, required=True)
    parser.add_argument("--fens", type=Path, default=ROOT / "train/data/nsce_search_mix_40k.jsonl")
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--pairs", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    net = Per1Net(args.net)
    labeled = load_labeled(args.fens, args.n)
    print(args.net, flush=True)
    print(collapse_report(net, labeled, args.pairs, args.seed), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
