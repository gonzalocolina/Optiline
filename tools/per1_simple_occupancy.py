#!/usr/bin/env python3
"""FT + output occupancy for the simple (768→512)×2 → 1 graph.

A neuron is stuck when its accumulator is outside (0, qa) on ≥99.5% of the
sample. The linear output fails when every FEN gets the same centipawn, or
the stdev is ~0. Distill nets must not be a constant.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from per1_float_ref import Per1Net, load_fens, pieces_from_fen  # noqa: E402

SAT = 0.005


def _bucket(z: int, lo: int, hi: int) -> str:
    if z <= lo:
        return "low"
    if z >= hi:
        return "high"
    return "mid"


def _tally(rows: list[list[int]], lo: int, hi: int) -> tuple[list[int], list[int], list[int]]:
    width = len(rows[0])
    low = [0] * width
    mid = [0] * width
    high = [0] * width
    for row in rows:
        for j, z in enumerate(row):
            kind = _bucket(z, lo, hi)
            if kind == "low":
                low[j] += 1
            elif kind == "high":
                high[j] += 1
            else:
                mid[j] += 1
    return low, mid, high


def _stuck(mid: list[int], n: int) -> list[int]:
    return [j for j, m in enumerate(mid) if m / n < SAT]


def _mass(low: list[int], mid: list[int], high: list[int], n: int) -> str:
    total = n * len(mid)
    return (
        f"mass low/mid/high "
        f"{100.0 * sum(low) / total:.1f}/"
        f"{100.0 * sum(mid) / total:.1f}/"
        f"{100.0 * sum(high) / total:.1f}%"
    )


def measure(net: Per1Net, fens: list[str]) -> dict:
    if not net.simple:
        raise ValueError("net is not the simple graph")
    qa = net.qa
    stm_rows: list[list[int]] = []
    nstm_rows: list[list[int]] = []
    cps: list[int] = []
    for fen in fens:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = net._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        stm_rows.append(list(stm_acc))
        nstm_rows.append(list(nstm_acc))
        cps.append(net._simple_int(stm_acc, nstm_acc))
    n = len(fens)
    return {
        "n": n,
        "stm": _tally(stm_rows, 0, qa),
        "nstm": _tally(nstm_rows, 0, qa),
        "cps": cps,
    }


def format_report(stats: dict) -> str:
    n = stats["n"]
    lines = [f"n={n}"]
    stuck_any = False
    for name, (low, mid, high) in (("FT stm", stats["stm"]), ("FT nstm", stats["nstm"])):
        stuck = _stuck(mid, n)
        stuck_any = stuck_any or bool(stuck)
        lines.append(
            f"{name}: stuck {len(stuck)}/{len(mid)}  {_mass(low, mid, high, n)}  ids={stuck[:16]}"
        )
    cps = stats["cps"]
    uniq = len(set(cps))
    mean = sum(cps) / n
    var = sum((c - mean) ** 2 for c in cps) / n
    stdev = math.sqrt(var)
    lines.append(f"OUT: unique={uniq} std={stdev:.1f} min={min(cps)} max={max(cps)}")
    ok = uniq > 1 and stdev >= 1.0
    lines.append("GATE pass" if ok else "GATE fail")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", type=Path, required=True)
    parser.add_argument(
        "--fens",
        type=Path,
        default=ROOT / "train/data/nsce_search_mix_40k.jsonl",
    )
    parser.add_argument("--n", type=int, default=1024)
    args = parser.parse_args()
    net = Per1Net(args.net)
    fens = load_fens(args.fens, args.n)
    print(args.net, flush=True)
    report = format_report(measure(net, fens))
    print(report, flush=True)
    return 0 if report.endswith("GATE pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
