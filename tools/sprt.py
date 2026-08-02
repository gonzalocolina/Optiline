#!/usr/bin/env python3
"""SPRT helper for NSCE vs baseline (same binary, two configs).

Uses sequential probability ratio test for H1: elo_diff >= elo0 vs H0: elo_diff <= elo1
with simplified logistic model (cutechess-style defaults).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ablation_match import play_game  # noqa: E402
from uci_common import UciEngine, load_openings  # noqa: E402


def llr(wins: int, losses: int, draws: int, elo0: float, elo1: float) -> float:
    """Log-likelihood ratio for score model."""
    n = wins + losses + draws
    if n == 0:
        return 0.0
    # Convert elo bounds to expected scores
    def score(elo: float) -> float:
        return 1.0 / (1.0 + 10 ** (-elo / 400.0))

    s0, s1 = score(elo0), score(elo1)
    # draw model: fraction of draws estimated from data
    dfrac = draws / n
    # Simplified: each game contributes based on outcome probabilities under Bernoulli score
    # Use expected score likelihood
    s = (wins + 0.5 * draws) / n
    # LLR ~ n * (s log(s1/s0) + (1-s) log((1-s1)/(1-s0))) with clamping
    s = min(max(s, 1e-6), 1 - 1e-6)
    s0 = min(max(s0, 1e-6), 1 - 1e-6)
    s1 = min(max(s1, 1e-6), 1 - 1e-6)
    return n * (s * math.log(s1 / s0) + (1 - s) * math.log((1 - s1) / (1 - s0)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--cfg-a", default=str(ROOT / "tools/configs/baseline.uci"), help="H0 / baseline")
    ap.add_argument("--cfg-b", default=str(ROOT / "tools/configs/controller.uci"), help="H1 candidate")
    ap.add_argument("--name-a", default="baseline")
    ap.add_argument("--name-b", default="candidate")
    ap.add_argument("--elo0", type=float, default=0.0, help="H0: elo_b - elo_a <= elo0")
    ap.add_argument("--elo1", type=float, default=5.0, help="H1: elo_b - elo_a >= elo1")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument("--max-games", type=int, default=40)
    ap.add_argument("--max-plies", type=int, default=60)
    ap.add_argument("--outdir", default="")
    args = ap.parse_args()

    engine = Path(args.engine)
    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")
    outdir.mkdir(parents=True, exist_ok=True)
    openings = load_openings(ROOT / "tools" / "openings.epd")

    a = UciEngine([str(engine)], args.name_a)
    b = UciEngine([str(engine)], args.name_b)
    a.apply_uci_file(Path(args.cfg_a))
    b.apply_uci_file(Path(args.cfg_b))

    # Bounds: accept H1 if LLR >= A, accept H0 if LLR <= B
    A = math.log((1 - args.beta) / args.alpha)
    B = math.log(args.beta / (1 - args.alpha))

    # SPRT on (elo_b - elo_a): we track results from B's perspective as wins
    w = d = l = 0
    decision = "inconclusive"
    history = []
    try:
        for i in range(args.max_games):
            fen = openings[i % len(openings)]
            if i % 2 == 0:
                res, meta = play_game(a, b, fen, args.movetime, args.max_plies)
                # a white: 1-0 => A win => B loss
                if res == "1-0":
                    l += 1
                elif res == "0-1":
                    w += 1
                else:
                    d += 1
            else:
                res, meta = play_game(b, a, fen, args.movetime, args.max_plies)
                # b white
                if res == "1-0":
                    w += 1
                elif res == "0-1":
                    l += 1
                else:
                    d += 1
            # LLR for candidate advantage: elo0/elo1 are for elo_b - elo_a
            ratio = llr(w, l, d, args.elo0, args.elo1)
            history.append({"game": i + 1, "W": w, "D": d, "L": l, "llr": ratio})
            print(f"SPRT game {i+1}: WDL={w}-{d}-{l} llr={ratio:.3f} bounds=[{B:.3f},{A:.3f}]")
            if ratio >= A:
                decision = "accept_H1_candidate_stronger"
                break
            if ratio <= B:
                decision = "accept_H0_baseline_not_worse"
                break
    finally:
        a.close()
        b.close()

    out = {
        "decision": decision,
        "W": w,
        "D": d,
        "L": l,
        "elo0": args.elo0,
        "elo1": args.elo1,
        "cfg_a": args.cfg_a,
        "cfg_b": args.cfg_b,
        "history": history,
    }
    (outdir / f"sprt_{args.name_b}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("decision", "W", "D", "L")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
