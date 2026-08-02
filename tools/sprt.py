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
from experiment_common import build_manifest, paired_schedule, write_manifest  # noqa: E402
from uci_common import UciEngine, load_openings  # noqa: E402


def llr(wins: int, losses: int, draws: int, elo0: float, elo1: float) -> float:
    """Trinomial W/D/L log-likelihood ratio with an estimated draw rate."""
    n = wins + losses + draws
    if n == 0:
        return 0.0
    # Convert elo bounds to expected scores
    def score(elo: float) -> float:
        return 1.0 / (1.0 + 10 ** (-elo / 400.0))

    s0, s1 = score(elo0), score(elo1)
    draw_rate = (draws + 0.5) / (n + 1.5)

    def probabilities(expected_score: float) -> tuple[float, float, float]:
        # E[score] = p(win) + 0.5 p(draw); clamp the nuisance draw rate to a valid simplex.
        draw = min(draw_rate, 2 * min(expected_score, 1 - expected_score) - 1e-9)
        win = expected_score - 0.5 * draw
        loss = 1 - expected_score - 0.5 * draw
        return tuple(max(value, 1e-12) for value in (win, draw, loss))

    p0 = probabilities(s0)
    p1 = probabilities(s1)
    return (
        wins * math.log(p1[0] / p0[0])
        + draws * math.log(p1[1] / p0[1])
        + losses * math.log(p1[2] / p0[2])
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--cfg-a", default=str(ROOT / "tools/configs/baseline.uci"), help="H0 / baseline")
    ap.add_argument("--cfg-b", default=str(ROOT / "tools/configs/controller.uci"), help="H1 candidate")
    ap.add_argument("--name-a", default="baseline")
    ap.add_argument("--name-b", default="candidate")
    ap.add_argument("--elo0", type=float, default=-5.0, help="H0: elo_b - elo_a <= elo0")
    ap.add_argument("--elo1", type=float, default=5.0, help="H1: elo_b - elo_a >= elo1")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument("--max-games", type=int, default=200, help="positive even number")
    ap.add_argument("--max-plies", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--adjudication-cp", type=int, default=800)
    ap.add_argument("--adjudication-plies", type=int, default=6)
    ap.add_argument("--outdir", default="")
    args = ap.parse_args()

    engine = Path(args.engine)
    if args.max_games <= 0 or args.max_games % 2:
        print("--max-games must be a positive even number", file=sys.stderr)
        return 1
    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")
    outdir.mkdir(parents=True, exist_ok=True)
    openings = load_openings(ROOT / "tools" / "openings.epd")
    schedule = paired_schedule(openings, args.max_games, args.seed)

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
    output_path = outdir / f"sprt_{args.name_b}.json"

    def snapshot() -> dict:
        out = {
            "decision": decision,
            "W": w,
            "D": d,
            "L": l,
            "elo0": args.elo0,
            "elo1": args.elo1,
            "alpha": args.alpha,
            "beta": args.beta,
            "bounds": {"lower": B, "upper": A},
            "seed": args.seed,
            "movetime_ms": args.movetime,
            "adjudication_cp": args.adjudication_cp,
            "adjudication_plies": args.adjudication_plies,
            "cfg_a": args.cfg_a,
            "cfg_b": args.cfg_b,
            "history": history,
        }
        output_path.write_text(json.dumps(out, indent=2) + "\n")
        return out

    try:
        for i, (pair_id, fen, b_is_black) in enumerate(schedule):
            if b_is_black:
                res, meta = play_game(
                    a,
                    b,
                    fen,
                    args.movetime,
                    args.max_plies,
                    args.adjudication_cp,
                    args.adjudication_plies,
                )
                # a white: 1-0 => A win => B loss
                if res == "1-0":
                    l += 1
                elif res == "0-1":
                    w += 1
                else:
                    d += 1
            else:
                res, meta = play_game(
                    b,
                    a,
                    fen,
                    args.movetime,
                    args.max_plies,
                    args.adjudication_cp,
                    args.adjudication_plies,
                )
                # b white
                if res == "1-0":
                    w += 1
                elif res == "0-1":
                    l += 1
                else:
                    d += 1
            # LLR for candidate advantage: elo0/elo1 are for elo_b - elo_a
            ratio = llr(w, l, d, args.elo0, args.elo1)
            history.append(
                {
                    "game": i + 1,
                    "pair_id": pair_id,
                    "fen": fen,
                    "candidate_is_white": not b_is_black,
                    "result": res,
                    "termination": meta["termination"],
                    "W": w,
                    "D": d,
                    "L": l,
                    "llr": ratio,
                }
            )
            print(f"SPRT game {i+1}: WDL={w}-{d}-{l} llr={ratio:.3f} bounds=[{B:.3f},{A:.3f}]")
            # Stop only at pair boundaries to preserve opening/color balance.
            if (i + 1) % 2 == 0:
                if ratio >= A:
                    decision = "accept_H1_candidate_stronger"
                elif ratio <= B:
                    decision = "accept_H0_baseline_not_worse"
                snapshot()
                if decision != "inconclusive":
                    break
    finally:
        a.close()
        b.close()

    out = snapshot()
    manifest = build_manifest(
        ROOT,
        engine,
        [Path(args.cfg_a), Path(args.cfg_b)],
        ROOT / "tools" / "openings.epd",
        args.seed,
        {
            "kind": "sprt",
            "max_games": args.max_games,
            "movetime_ms": args.movetime,
            "max_plies": args.max_plies,
            "elo0": args.elo0,
            "elo1": args.elo1,
            "alpha": args.alpha,
            "beta": args.beta,
            "adjudication_cp": args.adjudication_cp,
            "adjudication_plies": args.adjudication_plies,
        },
    )
    write_manifest(outdir / "manifest.json", manifest)
    print(json.dumps({k: out[k] for k in ("decision", "W", "D", "L")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
