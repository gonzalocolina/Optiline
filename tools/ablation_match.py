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

from experiment_common import build_manifest, paired_schedule, sha256_file, write_manifest  # noqa: E402
from uci_common import UciEngine, elo_from_wdl, load_openings  # noqa: E402


def play_game(
    white: UciEngine,
    black: UciEngine,
    fen: str,
    movetime: int,
    max_plies: int,
    adjudication_cp: int = 800,
    adjudication_plies: int = 6,
    adjudication_min_ply: int = 20,
    nodes: int = 0,
) -> tuple[str, dict]:
    """Return result from white's POV: '1-0', '0-1', '1/2-1/2'."""
    white.new_game()
    black.new_game()
    moves: list[str] = []
    nodes_w = 0
    nodes_b = 0
    time_w_ms = 0
    time_b_ms = 0
    decisive_sign = 0
    decisive_streak = 0

    def metadata(termination: str) -> dict:
        return {
            "moves": moves,
            "nodes_w": nodes_w,
            "nodes_b": nodes_b,
            "time_w_ms": time_w_ms,
            "time_b_ms": time_b_ms,
            "overruns_w": white.overruns,
            "overruns_b": black.overruns,
            "plies": len(moves),
            "termination": termination,
        }

    for ply in range(max_plies):
        engine = white if ply % 2 == 0 else black
        mv = engine.go_nodes(fen, moves, nodes) if nodes > 0 else engine.go_movetime(fen, moves, movetime)
        if ply % 2 == 0:
            nodes_w += engine.last_nodes
            time_w_ms += engine.last_time_ms
        else:
            nodes_b += engine.last_nodes
            time_b_ms += engine.last_time_ms
        if mv in ("0000", "(none)", "none"):
            st = white.status(fen, moves)
            if st == "checkmate":
                return ("0-1" if ply % 2 == 0 else "1-0"), metadata("checkmate")
            if st in ("stalemate", "draw"):
                return "1/2-1/2", metadata(st)
            raise RuntimeError(f"{engine.name}: invalid bestmove {mv} in ongoing position")

        score_white_pov = engine.last_score_cp if ply % 2 == 0 else -engine.last_score_cp
        moves.append(mv)
        st = white.status(fen, moves)
        if st == "checkmate":
            return ("1-0" if ply % 2 == 0 else "0-1"), metadata("checkmate")
        if st in ("stalemate", "draw"):
            return "1/2-1/2", metadata(st)

        sign = 1 if score_white_pov >= adjudication_cp else -1 if score_white_pov <= -adjudication_cp else 0
        if ply + 1 >= adjudication_min_ply and sign:
            decisive_streak = decisive_streak + 1 if sign == decisive_sign else 1
            decisive_sign = sign
            if decisive_streak >= adjudication_plies:
                return ("1-0" if sign > 0 else "0-1"), metadata("consensus_eval")
        else:
            decisive_sign = 0
            decisive_streak = 0

    return "1/2-1/2", metadata("max_plies")


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
    seed: int = 1,
    adjudication_cp: int = 800,
    adjudication_plies: int = 6,
    engine_path_b: Path | None = None,
    nodes: int = 0,
) -> dict:
    engine_path_b = engine_path_b or engine_path
    a = UciEngine([str(engine_path)], name_a)
    b = UciEngine([str(engine_path_b)], name_b)
    try:
        a.apply_uci_file(cfg_a)
        b.apply_uci_file(cfg_b)
        w = d = l = 0
        total_nodes_a = total_nodes_b = 0
        total_time_a = total_time_b = 0
        games_log = []
        schedule = paired_schedule(openings, games, seed)
        for i, (pair_id, fen, a_is_white) in enumerate(schedule):
            if a_is_white:
                res, meta = play_game(
                    a, b, fen, movetime, max_plies, adjudication_cp, adjudication_plies, nodes=nodes
                )
                # a is white
                if res == "1-0":
                    w += 1
                elif res == "0-1":
                    l += 1
                else:
                    d += 1
                total_nodes_a += meta["nodes_w"]
                total_nodes_b += meta["nodes_b"]
                total_time_a += meta["time_w_ms"]
                total_time_b += meta["time_b_ms"]
            else:
                res, meta = play_game(
                    b, a, fen, movetime, max_plies, adjudication_cp, adjudication_plies, nodes=nodes
                )
                # a is black
                if res == "0-1":
                    w += 1
                elif res == "1-0":
                    l += 1
                else:
                    d += 1
                total_nodes_a += meta["nodes_b"]
                total_nodes_b += meta["nodes_w"]
                total_time_a += meta["time_b_ms"]
                total_time_b += meta["time_w_ms"]
            result_from_a = (
                res
                if a_is_white
                else {"1-0": "0-1", "0-1": "1-0", "1/2-1/2": "1/2-1/2"}[res]
            )
            games_log.append(
                {
                    "i": i,
                    "pair_id": pair_id,
                    "a_is_white": a_is_white,
                    "fen": fen,
                    "result_from_a": result_from_a,
                    "plies": meta["plies"],
                    "termination": meta["termination"],
                }
            )
            print(f"  game {i+1}/{games}: A_score so far {w}+{d}/2 / {i+1}", flush=True)

        score = (w + 0.5 * d) / games
        elo, err = elo_from_wdl(w, d, l)
        return {
            "name_a": name_a,
            "name_b": name_b,
            "engine_a": str(engine_path),
            "engine_b": str(engine_path_b),
            "cfg_a": str(cfg_a),
            "cfg_b": str(cfg_b),
            "games": games,
            "pairs": games // 2,
            "seed": seed,
            "movetime_ms": movetime,
            "nodes_per_move": nodes,
            "adjudication_cp": adjudication_cp,
            "adjudication_plies": adjudication_plies,
            "W": w,
            "D": d,
            "L": l,
            "score": score,
            "elo_diff_a_minus_b": elo,
            "elo_err_95": err,
            "nodes_per_game_a": total_nodes_a / games,
            "nodes_per_game_b": total_nodes_b / games,
            "time_ms_per_game_a": total_time_a / games,
            "time_ms_per_game_b": total_time_b / games,
            "overruns_a": a.overruns,
            "overruns_b": b.overruns,
            "games_log": games_log,
        }
    finally:
        a.close()
        b.close()


def run_matrix(
    engine: Path,
    outdir: Path,
    openings_path: Path,
    games: int,
    movetime: int,
    max_plies: int,
    seed: int,
    adjudication_cp: int,
    adjudication_plies: int,
    search_matrix: bool = False,
) -> None:
    configs = ROOT / "tools" / "configs"
    openings = load_openings(openings_path)
    outdir.mkdir(parents=True, exist_ok=True)

    if search_matrix:
        baseline = configs / "baseline.uci"
        baseline_text = baseline.read_text()
        pairs = []
        for option in ("UseTT", "UseSEE", "UseLMR", "UseNullMove", "UseFutility", "UseLMP", "UseRazoring", "UseRFP", "UseProbCut"):
            candidate = outdir / f"no_{option.removeprefix('Use').lower()}.uci"
            enabled = f"setoption name {option} value true"
            if enabled not in baseline_text:
                raise RuntimeError(f"baseline does not freeze {option}")
            candidate.write_text(baseline_text.replace(enabled, f"setoption name {option} value false"))
            pairs.append(("baseline", baseline, candidate.stem, candidate))
    else:
        pairs = [
            ("baseline", configs / "baseline.uci", "hce", configs / "hce.uci"),
            ("baseline", configs / "baseline.uci", "policy", configs / "policy.uci"),
            ("baseline", configs / "baseline.uci", "controller", configs / "controller.uci"),
            (
                "baseline",
                configs / "baseline.uci",
                "policy_controller",
                configs / "policy_controller.uci",
            ),
        ]

    results = []

    for name_a, cfg_a, name_b, cfg_b in pairs:
        print(f"\n=== {name_a} vs {name_b} ===")
        r = match(
            engine,
            cfg_a,
            cfg_b,
            name_a,
            name_b,
            games,
            movetime,
            openings,
            max_plies,
            seed,
            adjudication_cp,
            adjudication_plies,
        )
        results.append(r)
        (outdir / f"match_{name_a}_vs_{name_b}.json").write_text(json.dumps(r, indent=2))

    write_report(outdir, results, engine, games, movetime)
    manifest = build_manifest(
        ROOT,
        engine,
        [item for pair in pairs for item in (pair[1], pair[3])],
        openings_path,
        seed,
        {
            "kind": "search_ablation_matrix" if search_matrix else "ablation_matrix",
            "games_per_match": games,
            "movetime_ms": movetime,
            "exploratory_short_tc": movetime < 50,
            "max_plies": max_plies,
            "adjudication_cp": adjudication_cp,
            "adjudication_plies": adjudication_plies,
        },
    )
    write_manifest(outdir / "manifest.json", manifest)


def write_report(outdir: Path, results: list[dict], engine: Path, games: int, movetime: int) -> None:
    lines = [
        f"# Ablation report — {outdir.name}",
        "",
        f"- Engine: `{engine}`",
        f"- Games/match: {games}",
        f"- Color-reversed opening pairs: {games // 2}",
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
            "- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.",
            "- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.",
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
    ap.add_argument("--engine-b", default="", help="optional second binary for engine-vs-engine matches")
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--search-matrix", action="store_true", help="ablate TT/SEE/pruning/search features")
    ap.add_argument("--openings", default=str(ROOT / "tools/openings_balanced.epd"))
    ap.add_argument("--outdir", default="")
    ap.add_argument("--games", type=int, default=100, help="even number; each opening is played with both colors")
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument(
        "--nodes",
        type=int,
        default=0,
        help="if >0, equal-node match (go nodes N) instead of movetime",
    )
    ap.add_argument("--max-plies", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--adjudication-cp", type=int, default=800)
    ap.add_argument("--adjudication-plies", type=int, default=6)
    ap.add_argument("--cfg-a", default="")
    ap.add_argument("--cfg-b", default="")
    ap.add_argument("--name-a", default="A")
    ap.add_argument("--name-b", default="B")
    args = ap.parse_args()

    engine = Path(args.engine)
    if not engine.exists():
        print(f"engine not found: {engine}", file=sys.stderr)
        return 1
    engine_b = Path(args.engine_b) if args.engine_b else engine
    if not engine_b.exists():
        print(f"engine B not found: {engine_b}", file=sys.stderr)
        return 1
    if args.games <= 0 or args.games % 2:
        print("--games must be a positive even number", file=sys.stderr)
        return 1
    if args.movetime < 50:
        print("warning: movetime below 50 ms is exploratory and unsuitable for promotion decisions", file=sys.stderr)

    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")

    openings_path = Path(args.openings)
    if args.matrix or args.search_matrix:
        run_matrix(
            engine,
            outdir,
            openings_path,
            args.games,
            args.movetime,
            args.max_plies,
            args.seed,
            args.adjudication_cp,
            args.adjudication_plies,
            args.search_matrix,
        )
        return 0

    if not args.cfg_a or not args.cfg_b:
        print("need --matrix, --search-matrix or --cfg-a/--cfg-b", file=sys.stderr)
        return 1

    openings = load_openings(openings_path)
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
        args.seed,
        args.adjudication_cp,
        args.adjudication_plies,
        engine_b,
        args.nodes,
    )
    write_report(outdir, [r], engine, args.games, args.movetime)
    manifest = build_manifest(
        ROOT,
        engine,
        [Path(args.cfg_a), Path(args.cfg_b)],
        openings_path,
        args.seed,
        {
            "kind": "ablation_match",
            "games": args.games,
            "movetime_ms": args.movetime,
            "nodes_per_move": args.nodes,
            "exploratory_short_tc": args.movetime < 50,
            "max_plies": args.max_plies,
            "adjudication_cp": args.adjudication_cp,
            "adjudication_plies": args.adjudication_plies,
            "engine_b": str(engine_b.resolve()),
            "engine_b_sha256": sha256_file(engine_b),
        },
    )
    write_manifest(outdir / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
