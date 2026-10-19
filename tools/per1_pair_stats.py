#!/usr/bin/env python3
"""Pair-product and saturation rates for a packed 512/32/32 net.

z = a * b sends no gradient to a when b is 0. This reports, over FENs, the
fraction of FT pairs whose product is 0 and the fraction of those CReLU halves
that sit at 0 or QA. It also reports L2 CReLU saturation. Quantised checkpoints
do not contain gradient tensors; this does not invent them.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from pack_nsceper1 import pack_from_quantised, write_per1  # noqa: E402
from per1_float_ref import Per1Net, load_fens, pieces_from_fen  # noqa: E402

CHECKPOINTS = (10, 20, 30, 50)


def pair_stats(net: Per1Net, fens: list[str]) -> dict[str, float]:
    if net.simple or net.hl:
        raise ValueError("pair stats require the bucketed 512/32/32 MLP")
    qa = net.qa
    half = net.hidden // 2
    factor_zero = 0
    quant_zero = 0
    saturated = 0
    pairs = 0
    halves = 0
    l2_sat = 0
    l2_n = 0
    for fen in fens:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = net._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        for acc in (stm_acc, nstm_acc):
            for i in range(half):
                x0 = max(0, min(qa, acc[i]))
                x1 = max(0, min(qa, acc[half + i]))
                pairs += 1
                # dz/da = b. A zero factor blocks that branch. A product that
                # truncates to 0 is dead in the integer net even if both
                # factors are positive.
                if x0 == 0 or x1 == 0:
                    factor_zero += 1
                if x0 * x1 // qa == 0:
                    quant_zero += 1
                for x in (x0, x1):
                    halves += 1
                    if x == 0 or x == qa:
                        saturated += 1
        crelu = net.l2_crelu(fen)
        l2_n += len(crelu)
        l2_sat += sum(1 for x in crelu if x == 0 or x == qa)
    return {
        "n": float(len(fens)),
        "pair_factor_zero": factor_zero / pairs if pairs else 0.0,
        "pair_quant_zero": quant_zero / pairs if pairs else 0.0,
        "half_saturated": saturated / halves if halves else 0.0,
        "l2_saturated": l2_sat / l2_n if l2_n else 0.0,
    }


def format_report(label: str, stats: dict[str, float]) -> str:
    return (
        f"{label} n={int(stats['n'])} "
        f"pair_factor_zero={stats['pair_factor_zero']:.4f} "
        f"pair_quant_zero={stats['pair_quant_zero']:.4f} "
        f"half_saturated={stats['half_saturated']:.4f} "
        f"l2_saturated={stats['l2_saturated']:.4f}"
    )


def _packed(quantised: Path, dest: Path) -> None:
    write_per1(dest, *pack_from_quantised(quantised.read_bytes()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", type=Path)
    parser.add_argument("--checkpoints", type=Path)
    parser.add_argument("--fens", type=Path, default=ROOT / "tools/openings_balanced.epd")
    parser.add_argument("--n", type=int, default=256)
    args = parser.parse_args()
    if args.net is None and args.checkpoints is None:
        parser.error("need --net or --checkpoints")
    fens = load_fens(args.fens, args.n)
    if args.net is not None:
        print(format_report(str(args.net), pair_stats(Per1Net(args.net), fens)), flush=True)
    if args.checkpoints is not None:
        found = False
        for n in CHECKPOINTS:
            quantised = args.checkpoints / f"nsce-{n}" / "quantised.bin"
            if not quantised.is_file():
                print(f"nsce-{n} missing", flush=True)
                continue
            found = True
            with tempfile.TemporaryDirectory() as tmp:
                packed = Path(tmp) / "net.bin"
                _packed(quantised, packed)
                print(format_report(f"nsce-{n}", pair_stats(Per1Net(packed), fens)), flush=True)
        if not found:
            print("no quantised nsce-10/20/30/50 checkpoint", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
