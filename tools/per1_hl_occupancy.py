#!/usr/bin/env python3
"""FT and hidden SCReLU occupancy for the HL graph (768→512)×2 → 32 → 1.

A neuron is saturated when its pre-activation is outside the open interval on
at least 99.5% of the sample. FT uses the accumulator in QA units, open
interval (0, qa), measured on both perspectives. Hidden pre-activation is
trunc_div(dot, qa) + bias, open interval (0, qa*qb). The linear output has
no clip; it fails only when every position gets the same centipawn value.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from pack_nsceper1 import HL  # noqa: E402
from per1_float_ref import Per1Net, load_fens, pieces_from_fen, trunc_div  # noqa: E402

SAT = 0.005


def _bucket(n: int, z: int, lo: int, hi: int) -> str:
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
            kind = _bucket(0, z, lo, hi)
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
    if not net.hl:
        raise ValueError("net is not the HL graph")
    qa, qb = net.qa, net.qb
    stm_rows: list[list[int]] = []
    nstm_rows: list[list[int]] = []
    hid_rows: list[list[int]] = []
    cps: list[int] = []
    width = 2 * net.hidden
    for fen in fens:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = net._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        stm_rows.append(list(stm_acc))
        nstm_rows.append(list(nstm_acc))
        act = net._hl_act(stm_acc, nstm_acc)
        pre = [0] * HL
        for j in range(HL):
            s = 0
            base = j * width
            for i in range(width):
                s += act[i] * net.hl_w1[base + i]
            pre[j] = trunc_div(s, qa) + net.hl_b1[j]
        hid_rows.append(pre)
        cps.append(net._hl_int(stm_acc, nstm_acc))
    n = len(fens)
    stm = _tally(stm_rows, 0, qa)
    nstm = _tally(nstm_rows, 0, qa)
    hid = _tally(hid_rows, 0, qa * qb)
    return {
        "n": n,
        "stm": stm,
        "nstm": nstm,
        "hid": hid,
        "cps": cps,
    }


def format_report(stats: dict) -> str:
    n = stats["n"]
    lines = [f"n={n}"]
    labels = (("FT stm", stats["stm"]), ("FT nstm", stats["nstm"]), ("HL", stats["hid"]))
    stuck_any = False
    for name, (low, mid, high) in labels:
        stuck = _stuck(mid, n)
        stuck_any = stuck_any or bool(stuck)
        lines.append(
            f"{name}: stuck {len(stuck)}/{len(mid)}  {_mass(low, mid, high, n)}  ids={stuck}"
        )
    cps = stats["cps"]
    uniq = len(set(cps))
    mean = sum(cps) / n
    var = sum((c - mean) ** 2 for c in cps) / n
    lines.append(
        f"OUT: unique={uniq} std={var ** 0.5:.1f} min={min(cps)} max={max(cps)}"
    )
    constant = uniq <= 1
    ok = not stuck_any and not constant
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
    print(format_report(measure(net, fens)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
