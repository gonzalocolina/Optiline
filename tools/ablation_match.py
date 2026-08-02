#!/usr/bin/env python3
"""Ablation matches: same binary, two UCI configs, equal movetime.

Writes report under experiments/YYYYMMDD/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from uci_common import UciEngine, elo_from_score, load_openings  # noqa: E402


def play_game(
    white: UciEngine,
    black: UciEngine,
    fen: str,
    movetime: int,
    max_plies: int,
) -> tuple[str, dict]:
    """Return result from white's POV: '1-0', '0-1', '1/2-1/2'."""
    white.new_game()
    black.new_game()
    moves: list[str] = []
    nodes_w = 0
    nodes_b = 0
    last_score_white_pov = 0
    for ply in range(max_plies):
        engine = white if ply % 2 == 0 else black
        mv = engine.go_movetime(fen, moves, movetime)
        # Parse last cp from engine by a tiny depth probe on white for adjudication later
        if ply % 2 == 0:
            nodes_w += engine.last_nodes
        else:
            nodes_b += engine.last_nodes
        if mv in ("0000", "(none)", "none"):
            break
        moves.append(mv)
        st = white.status(fen, moves)
        if st == "checkmate":
            return ("1-0" if ply % 2 == 0 else "0-1"), {
                "moves": moves,
                "nodes_w": nodes_w,
                "nodes_b": nodes_b,
                "plies": len(moves),
            }
        if st in ("stalemate", "draw"):
            return "1/2-1/2", {
                "moves": moves,
                "nodes_w": nodes_w,
                "nodes_b": nodes_b,
                "plies": len(moves),
            }

    # Adjudicate by a short search from white's perspective
    white.set_position(fen, moves)
    white._send("go depth 3")
    lines = white._wait_for("bestmove", timeout=30.0)
    score_cp = 0
    for line in lines:
        if " score cp " in line:
            parts = line.split()
            if "cp" in parts:
                score_cp = int(parts[parts.index("cp") + 1])
                # score is stm-relative; convert to white POV
                stm_black = len(moves) % 2 == 1
                last_score_white_pov = -score_cp if stm_black else score_cp
    if last_score_white_pov > 200:
        res = "1-0"
    elif last_score_white_pov < -200:
        res = "0-1"
    else:
        res = "1/2-1/2"
    return res, {
        "moves": moves,
        "nodes_w": nodes_w,
        "nodes_b": nodes_b,
        "plies": len(moves),
        "adjudicated_cp_white": last_score_white_pov,
    }


def match(
    engine_path: Path,
    cfg_a: Path,
    cfg_b: Path,
    name_a: str,
    name_b: str,
    games: int,
    movetime: int,
    openings: list[str],
    max_plies: int,
) -> dict:
    a = UciEngine([str(engine_path)], name_a)
    b = UciEngine([str(engine_path)], name_b)
    try:
        a.apply_uci_file(cfg_a)
        b.apply_uci_file(cfg_b)
        w = d = l = 0
        total_nodes_a = total_nodes_b = 0
        games_log = []
        for i in range(games):
            fen = openings[i % len(openings)]
            if i % 2 == 0:
                res, meta = play_game(a, b, fen, movetime, max_plies)
                # a is white
                if res == "1-0":
                    w += 1
                elif res == "0-1":
                    l += 1
                else:
                    d += 1
                total_nodes_a += meta["nodes_w"]
                total_nodes_b += meta["nodes_b"]
            else:
                res, meta = play_game(b, a, fen, movetime, max_plies)
                # a is black
                if res == "0-1":
                    w += 1
                elif res == "1-0":
                    l += 1
                else:
                    d += 1
                total_nodes_a += meta["nodes_b"]
                total_nodes_b += meta["nodes_w"]
            games_log.append({"i": i, "result_from_a": res if i % 2 == 0 else {"1-0": "0-1", "0-1": "1-0", "1/2-1/2": "1/2-1/2"}[res], "plies": meta["plies"]})
            print(f"  game {i+1}/{games}: A_score so far {w}+{d}/2 / {i+1}")

        score = (w + 0.5 * d) / games
        elo, err = elo_from_score(score, games)
        return {
            "name_a": name_a,
            "name_b": name_b,
            "cfg_a": str(cfg_a),
            "cfg_b": str(cfg_b),
            "games": games,
            "movetime_ms": movetime,
            "W": w,
            "D": d,
            "L": l,
            "score": score,
            "elo_diff_a_minus_b": elo,
            "elo_err_95": err,
            "nodes_per_game_a": total_nodes_a / games,
            "nodes_per_game_b": total_nodes_b / games,
            "overruns_a": a.overruns,
            "overruns_b": b.overruns,
            "games_log": games_log,
        }
    finally:
        a.close()
        b.close()


def positive_signal(result: dict) -> bool:
    # A is baseline; positive for challenger means baseline loses => elo_diff < 0 with margin
    # For matrix we compare baseline (A) vs challenger (B). Signal that challenger helps:
    # score of A < 0.5 with CI not covering strong A win — use score_b = 1-score > 0.5 and elo_a < 0
    return result["elo_diff_a_minus_b"] < -10 and result["score"] < 0.48


def run_matrix(engine: Path, outdir: Path, games: int, movetime: int, max_plies: int) -> None:
    configs = ROOT / "tools" / "configs"
    openings = load_openings(ROOT / "tools" / "openings.epd")
    outdir.mkdir(parents=True, exist_ok=True)

    pairs = [
        ("baseline", configs / "baseline.uci", "hce", configs / "hce.uci"),
        ("baseline", configs / "baseline.uci", "policy", configs / "policy.uci"),
        ("baseline", configs / "baseline.uci", "controller", configs / "controller.uci"),
    ]

    results = []
    policy_sig = False
    ctrl_sig = False

    for name_a, cfg_a, name_b, cfg_b in pairs:
        print(f"\n=== {name_a} vs {name_b} ===")
        r = match(engine, cfg_a, cfg_b, name_a, name_b, games, movetime, openings, max_plies)
        results.append(r)
        (outdir / f"match_{name_a}_vs_{name_b}.json").write_text(json.dumps(r, indent=2))
        if name_b == "policy" and positive_signal(r):
            # wait: positive_signal means A loses to B, i.e. challenger stronger
            policy_sig = True
        if name_b == "controller" and positive_signal(r):
            ctrl_sig = True
        # Also treat "challenger not worse" loosely for combo gate: elo_a <= 5
        if name_b == "policy" and r["elo_diff_a_minus_b"] <= 5:
            policy_sig = policy_sig or r["score"] <= 0.52
        if name_b == "controller" and r["elo_diff_a_minus_b"] <= 5:
            ctrl_sig = ctrl_sig or r["score"] <= 0.52

    # Gate for combo: if either showed non-negative challenger signal (baseline not clearly better)
    # Plan: only if 2 or 3 "ganan" — interpret as challenger Elo >= baseline within noise or better
    def challenger_ok(r: dict) -> bool:
        return r["elo_diff_a_minus_b"] <= 15  # baseline not clearly ahead

    p = next(x for x in results if x["name_b"] == "policy")
    c = next(x for x in results if x["name_b"] == "controller")
    if challenger_ok(p) or challenger_ok(c):
        print("\n=== baseline vs policy_controller ===")
        r = match(
            engine,
            configs / "baseline.uci",
            configs / "policy_controller.uci",
            "baseline",
            "policy_controller",
            games,
            movetime,
            openings,
            max_plies,
        )
        results.append(r)
        (outdir / "match_baseline_vs_policy_controller.json").write_text(json.dumps(r, indent=2))

    write_report(outdir, results, engine, games, movetime)


def write_report(outdir: Path, results: list[dict], engine: Path, games: int, movetime: int) -> None:
    lines = [
        f"# Ablation report — {outdir.name}",
        "",
        f"- Engine: `{engine}`",
        f"- Games/match: {games}",
        f"- Movetime: {movetime} ms",
        f"- Date: {date.today().isoformat()}",
        "",
        "| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['name_a']} vs {r['name_b']} | {r['W']}-{r['D']}-{r['L']} | {r['score']:.3f} | "
            f"{r['elo_diff_a_minus_b']:+.0f} ± {r['elo_err_95']:.0f} | "
            f"{r['nodes_per_game_a']:.0f} | {r['nodes_per_game_b']:.0f} | "
            f"{r['overruns_a']}+{r['overruns_b']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Positive Elo A−B ⇒ baseline stronger than challenger.",
            "- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.",
            "",
        ]
    )
    (outdir / "report.md").write_text("\n".join(lines) + "\n")
    (outdir / "ablation_summary.json").write_text(json.dumps(results, indent=2))
    print("\n".join(lines))


def try_cutechess(engine: Path, cfg_a: Path, cfg_b: Path, games: int) -> bool:
    if not subprocess.call(["which", "cutechess-cli"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return False
    # Optional path — UCI runner is default; cutechess left for ladder script
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument("--max-plies", type=int, default=60)
    ap.add_argument("--cfg-a", default="")
    ap.add_argument("--cfg-b", default="")
    ap.add_argument("--name-a", default="A")
    ap.add_argument("--name-b", default="B")
    args = ap.parse_args()

    engine = Path(args.engine)
    if not engine.exists():
        print(f"engine not found: {engine}", file=sys.stderr)
        return 1

    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")

    if args.matrix:
        run_matrix(engine, outdir, args.games, args.movetime, args.max_plies)
        return 0

    if not args.cfg_a or not args.cfg_b:
        print("need --matrix or --cfg-a/--cfg-b", file=sys.stderr)
        return 1

    openings = load_openings(ROOT / "tools" / "openings.epd")
    outdir.mkdir(parents=True, exist_ok=True)
    r = match(
        engine,
        Path(args.cfg_a),
        Path(args.cfg_b),
        args.name_a,
        args.name_b,
        args.games,
        args.movetime,
        openings,
        args.max_plies,
    )
    write_report(outdir, [r], engine, args.games, args.movetime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
