#!/usr/bin/env python3
"""Dataset-wide L2 pre-activation occupancy for NSCEPER1 MLP nets.

Single-FEN L2sat (units at 0 or qa after CReLU) does not say whether a neuron
is dead. This counts, over many FENs, P(z<=0) / P(0<z<1) / P(z>=1) on the L2
affine *before* CReLU. Integer z in (0, qa*qb) is the open unit interval.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from pack_nsceper1 import L2  # noqa: E402
from per1_float_ref import Per1Net, load_fens  # noqa: E402


def occupancy(net: Per1Net, fens: list[str]) -> dict:
    hi = net.qa * net.qb
    low = [0] * L2
    mid = [0] * L2
    high = [0] * L2
    mid_pos = []
    for fen in fens:
        pre = net.l2_preacts(fen)
        n_mid = 0
        for j, z in enumerate(pre):
            if z <= 0:
                low[j] += 1
            elif z >= hi:
                high[j] += 1
            else:
                mid[j] += 1
                n_mid += 1
        mid_pos.append(n_mid)
    n = len(fens)
    return {
        "n": n,
        "low": low,
        "mid": mid,
        "high": high,
        "mean_l2mid": sum(mid_pos) / n if n else 0.0,
        "min_l2mid": min(mid_pos) if mid_pos else 0,
        "max_l2mid": max(mid_pos) if mid_pos else 0,
    }


def _pct(count: int, n: int) -> float:
    return 100.0 * count / n if n else 0.0


def format_report(stats: dict) -> str:
    n = stats["n"]
    lines = [
        f"n={n}  mean L2mid={stats['mean_l2mid']:.1f}/32  "
        f"min={stats['min_l2mid']}/32  max={stats['max_l2mid']}/32",
        f"{'j':>4}  {'low':>7}  {'mid':>7}  {'high':>7}",
    ]
    dead = 0
    for j in range(L2):
        pl, pm, ph = (_pct(stats["low"][j], n), _pct(stats["mid"][j], n), _pct(stats["high"][j], n))
        if pm < 0.5:
            dead += 1
        lines.append(f"{j:4d}  {pl:6.1f}%  {pm:6.1f}%  {ph:6.1f}%")
    lines.append(f"neurons with mid < 0.5% over the set: {dead}/32")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", type=Path, required=True)
    parser.add_argument("--fens", type=Path, default=ROOT / "tools/openings_uho.epd")
    parser.add_argument("--n", type=int, default=1024)
    args = parser.parse_args()
    net = Per1Net(args.net)
    fens = load_fens(args.fens, args.n)
    print(args.net, flush=True)
    print(format_report(occupancy(net, fens)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
