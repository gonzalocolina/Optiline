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
from experiment_common import attach_frozen_targets, build_manifest, paired_schedule, sha256_file, write_manifest  # noqa: E402
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


def pentanomial_llr(counts: list[int], elo0: float, elo1: float) -> float:
    """Pair-level normal SPRT over scores {0, .25, .5, .75, 1}.

    Each observation is the candidate's average score over one color-reversed
    opening pair. The empirical variance is a nuisance estimate, matching the
    standard pentanomial approximation used for paired engine testing.

    A single unanimous pair has empirical variance 0 and would otherwise explode
    the LLR past the bounds after two games. Floor per-pair variance at a typical
    chess-pair value so early stopping requires a real sample.
    """
    if len(counts) != 5:
        raise ValueError("pentanomial counts must have five buckets")
    n = sum(counts)
    if n == 0:
        return 0.0
    values = (0.0, 0.25, 0.5, 0.75, 1.0)
    mean = sum(count * value for count, value in zip(counts, values)) / n
    variance = sum(count * (value - mean) ** 2 for count, value in zip(counts, values)) / n
    # Chess pair scores typically vary ~0.04–0.08. 1e-6 made one 0.75 pair
    # produce LLR ≈ 3500 and a false H1 after two games.
    variance = max(variance, 0.04)

    def score(elo: float) -> float:
        return 1.0 / (1.0 + 10 ** (-elo / 400.0))

    score0, score1 = score(elo0), score(elo1)
    midpoint = 0.5 * (score0 + score1)
    return n * (score1 - score0) * (mean - midpoint) / variance


def candidate_game_score(result: str, candidate_is_white: bool) -> float:
    if result == "1/2-1/2":
        return 0.5
    return 1.0 if (result == "1-0") == candidate_is_white else 0.0


def pentanomial_from_history(history: list[dict]) -> list[int]:
    counts = [0, 0, 0, 0, 0]
    for first, second in zip(history[::2], history[1::2]):
        pair_score = candidate_game_score(first["result"], first["candidate_is_white"])
        pair_score += candidate_game_score(second["result"], second["candidate_is_white"])
        counts[int(round(pair_score * 2))] += 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--engine-b", default="", help="optional second binary (candidate)")
    ap.add_argument("--cfg-a", default=str(ROOT / "tools/configs/baseline.uci"), help="H0 / baseline")
    ap.add_argument("--cfg-b", default=str(ROOT / "tools/configs/controller.uci"), help="H1 candidate")
    ap.add_argument("--name-a", default="baseline")
    ap.add_argument("--name-b", default="candidate")
    ap.add_argument("--elo0", type=float, default=-5.0, help="H0: elo_b - elo_a <= elo0")
    ap.add_argument("--elo1", type=float, default=5.0, help="H1: elo_b - elo_a >= elo1")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument("--allow-short-tc", action="store_true", help="allow exploratory movetime below 50 ms")
    ap.add_argument("--max-games", type=int, default=200, help="positive even number")
    ap.add_argument(
        "--min-games",
        type=int,
        default=40,
        help="do not accept H0/H1 before this many games (even, pair-aligned)",
    )
    ap.add_argument("--max-plies", type=int, default=60)
    ap.add_argument("--openings", default=str(ROOT / "tools/openings_balanced.epd"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--adjudication-cp", type=int, default=800)
    ap.add_argument("--adjudication-plies", type=int, default=6)
    ap.add_argument("--outdir", default="")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="continue from outdir/sprt_<name-b>.json if present (same seed/schedule)",
    )
    ap.add_argument(
        "--frozen-targets",
        default=str(ROOT / "experiments/frozen-targets/manifest.json"),
        help="pin Stockfish/NSCE identities into the experiment manifest",
    )
    args = ap.parse_args()

    engine = Path(args.engine)
    engine_b = Path(args.engine_b) if args.engine_b else engine
    if args.max_games <= 0 or args.max_games % 2:
        print("--max-games must be a positive even number", file=sys.stderr)
        return 1
    if args.min_games <= 0 or args.min_games % 2:
        print("--min-games must be a positive even number", file=sys.stderr)
        return 1
    if args.min_games > args.max_games:
        print("--min-games cannot exceed --max-games", file=sys.stderr)
        return 1
    if args.movetime < 50 and not args.allow_short_tc:
        print("movetime below 50 ms is too noisy for SPRT; use --allow-short-tc only for smoke tests", file=sys.stderr)
        return 1
    if not engine.exists():
        print(f"engine not found: {engine}", file=sys.stderr)
        return 1
    if not engine_b.exists():
        print(f"engine-b not found: {engine_b}", file=sys.stderr)
        return 1
    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")
    outdir.mkdir(parents=True, exist_ok=True)
    openings_path = Path(args.openings)
    openings = load_openings(openings_path)
    schedule = paired_schedule(openings, args.max_games, args.seed)
    config_identity = {
        "cfg_a_sha256": sha256_file(Path(args.cfg_a)),
        "cfg_b_sha256": sha256_file(Path(args.cfg_b)),
        "openings_sha256": sha256_file(openings_path),
        "engine_sha256": sha256_file(engine),
        "engine_b_sha256": sha256_file(engine_b),
        "max_plies": args.max_plies,
        "adjudication_cp": args.adjudication_cp,
        "adjudication_plies": args.adjudication_plies,
        "elo0": args.elo0,
        "elo1": args.elo1,
        "alpha": args.alpha,
        "beta": args.beta,
    }

    # Bounds: accept H1 if LLR >= A, accept H0 if LLR <= B
    A = math.log((1 - args.beta) / args.alpha)
    B = math.log(args.beta / (1 - args.alpha))

    # SPRT on (elo_b - elo_a): we track results from B's perspective as wins
    w = d = l = 0
    pentanomial = [0, 0, 0, 0, 0]
    pending_pair_score = 0.0
    decision = "inconclusive"
    history: list[dict] = []
    output_path = outdir / f"sprt_{args.name_b}.json"
    start_index = 0

    if args.resume and output_path.exists():
        prior = json.loads(output_path.read_text())
        if prior.get("llr_model") != "pair_normal_pentanomial":
            print("--resume file uses an incompatible pre-pentanomial LLR model", file=sys.stderr)
            return 1
        if prior.get("seed") != args.seed:
            print(f"--resume seed mismatch: file={prior.get('seed')} args={args.seed}", file=sys.stderr)
            return 1
        if prior.get("movetime_ms") != args.movetime:
            print("--resume movetime mismatch", file=sys.stderr)
            return 1
        for key, expected in config_identity.items():
            if prior.get("identity", {}).get(key) != expected:
                print(f"--resume identity mismatch: {key}", file=sys.stderr)
                return 1
        history = list(prior.get("history", []))
        # Only resume from an even game count so opening/color pairs stay balanced.
        if len(history) % 2:
            history = history[:-1]
        if history:
            w, d, l = int(history[-1]["W"]), int(history[-1]["D"]), int(history[-1]["L"])
        else:
            w = d = l = 0
        decision = prior.get("decision", "inconclusive")
        pentanomial = pentanomial_from_history(history)
        start_index = len(history)
        print(f"Resuming from game {start_index + 1}/{args.max_games} WDL={w}-{d}-{l}")
        if decision != "inconclusive" or start_index >= args.max_games:
            print(json.dumps({"decision": decision, "W": w, "D": d, "L": l}, indent=2))
            return 0

    a = UciEngine([str(engine)], args.name_a)
    b = UciEngine([str(engine_b)], args.name_b)
    a.apply_uci_file(Path(args.cfg_a))
    b.apply_uci_file(Path(args.cfg_b))

    def snapshot() -> dict:
        out = {
            "decision": decision,
            "W": w,
            "D": d,
            "L": l,
            "pentanomial": pentanomial,
            "llr_model": "pair_normal_pentanomial",
            "elo0": args.elo0,
            "elo1": args.elo1,
            "alpha": args.alpha,
            "beta": args.beta,
            "bounds": {"lower": B, "upper": A},
            "min_games": args.min_games,
            "seed": args.seed,
            "movetime_ms": args.movetime,
            "max_plies": args.max_plies,
            "exploratory_short_tc": args.movetime < 50,
            "adjudication_cp": args.adjudication_cp,
            "adjudication_plies": args.adjudication_plies,
            "identity": config_identity,
            "cfg_a": args.cfg_a,
            "cfg_b": args.cfg_b,
            "history": history,
        }
        output_path.write_text(json.dumps(out, indent=2) + "\n")
        return out

    manifest_extra = {
        "kind": "sprt",
        "max_games": args.max_games,
        "min_games": args.min_games,
        "movetime_ms": args.movetime,
        "exploratory_short_tc": args.movetime < 50,
        "max_plies": args.max_plies,
        "elo0": args.elo0,
        "elo1": args.elo1,
        "alpha": args.alpha,
        "beta": args.beta,
        "adjudication_cp": args.adjudication_cp,
        "adjudication_plies": args.adjudication_plies,
        "openings": str(openings_path),
        "llr_model": "pair_normal_pentanomial",
        "engine_b": str(engine_b),
    }

    def write_current_manifest() -> None:
        write_manifest(
            outdir / "manifest.json",
            attach_frozen_targets(
                build_manifest(ROOT, engine, [Path(args.cfg_a), Path(args.cfg_b)], openings_path, args.seed, manifest_extra),
                Path(args.frozen_targets) if args.frozen_targets else None,
            ),
        )

    try:
        for i, (pair_id, fen, b_is_black) in enumerate(schedule):
            if i < start_index:
                continue
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
            candidate_is_white = not b_is_black
            pending_pair_score += candidate_game_score(res, candidate_is_white)
            if (i + 1) % 2 == 0:
                pentanomial[int(round(pending_pair_score * 2))] += 1
                pending_pair_score = 0.0
            # Pair-level LLR; it only changes at complete opening-pair boundaries.
            ratio = pentanomial_llr(pentanomial, args.elo0, args.elo1)
            history.append(
                {
                    "game": i + 1,
                    "pair_id": pair_id,
                    "fen": fen,
                    "candidate_is_white": candidate_is_white,
                    "result": res,
                    "termination": meta["termination"],
                    "overruns": meta.get("overruns_w", 0) + meta.get("overruns_b", 0),
                    "moves": meta.get("moves", []),
                    "plies": meta.get("plies", 0),
                    "nodes_w": meta.get("nodes_w", 0),
                    "nodes_b": meta.get("nodes_b", 0),
                    "time_w_ms": meta.get("time_w_ms", 0),
                    "time_b_ms": meta.get("time_b_ms", 0),
                    "W": w,
                    "D": d,
                    "L": l,
                    "llr": ratio,
                }
            )
            print(f"SPRT game {i+1}: WDL={w}-{d}-{l} llr={ratio:.3f} bounds=[{B:.3f},{A:.3f}]", flush=True)
            # Persist every game so interrupted runs can resume without losing odd games.
            # Stop only at pair boundaries to preserve opening/color balance.
            if (i + 1) % 2 == 0 and (i + 1) >= args.min_games:
                if ratio >= A:
                    decision = "accept_H1_candidate_stronger"
                elif ratio <= B:
                    decision = "accept_H0_baseline_not_worse"
            snapshot()
            if decision != "inconclusive" and (i + 1) % 2 == 0:
                break
    finally:
        a.close()
        b.close()
        snapshot()
        write_current_manifest()

    out = snapshot()
    print(json.dumps({k: out[k] for k in ("decision", "W", "D", "L")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
