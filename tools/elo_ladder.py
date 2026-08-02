#!/usr/bin/env python3
"""Elo ladder rungs for NSCE (self-play depth → weak → Stockfish if available)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ablation_match import match  # noqa: E402
from uci_common import UciEngine, elo_from_score, load_openings  # noqa: E402


def depth_ladder(engine: Path, games: int, outdir: Path) -> dict:
    """Stronger depth vs weaker depth using same baseline config."""
    return depth_ladder_custom(engine, games, 5, 3, outdir)


def weak_nsce_rung(engine: Path, games: int, movetime: int, outdir: Path) -> dict:
    """Baseline movetime vs very weak (tiny movetime) as stand-in for weak engine."""
    # Use configs: baseline 100ms vs "weak" via same binary with UseNNUE false + short time in match
    # Simpler: depth 4 vs depth 1 through go_depth match inline
    return depth_ladder_custom(engine, games, 4, 1, outdir)


def depth_ladder_custom(engine: Path, games: int, d_hi: int, d_lo: int, outdir: Path) -> dict:
    openings = load_openings(ROOT / "tools" / "openings.epd")
    cfg = ROOT / "tools" / "configs" / "baseline.uci"
    hi = UciEngine([str(engine)], f"d{d_hi}")
    lo = UciEngine([str(engine)], f"d{d_lo}")
    try:
        hi.apply_uci_file(cfg)
        lo.apply_uci_file(cfg)
        w = d = l = 0
        for i in range(games):
            fen = openings[i % len(openings)]
            hi.new_game()
            lo.new_game()
            moves: list[str] = []
            a_white = i % 2 == 0
            result = "1/2-1/2"
            for ply in range(40):
                if a_white:
                    eng, depth = (hi, d_hi) if ply % 2 == 0 else (lo, d_lo)
                else:
                    eng, depth = (lo, d_lo) if ply % 2 == 0 else (hi, d_hi)
                mv = eng.go_depth(fen, moves, depth)
                if mv in ("0000", "(none)", "none"):
                    break
                moves.append(mv)
                st = hi.status(fen, moves)
                if st == "checkmate":
                    white_won = ply % 2 == 0
                    if a_white:
                        result = "1-0" if white_won else "0-1"
                    else:
                        result = "0-1" if white_won else "1-0"
                    break
                if st in ("stalemate", "draw"):
                    result = "1/2-1/2"
                    break
            if result == "1-0":
                w += 1
            elif result == "0-1":
                l += 1
            else:
                d += 1
            print(f"  weak-rung game {i+1}: strong result={result}")
        score = (w + 0.5 * d) / max(1, games)
        elo, err = elo_from_score(score, games)
        return {
            "rung": f"depth_ladder_d{d_hi}_vs_d{d_lo}",
            "W": w,
            "D": d,
            "L": l,
            "score": score,
            "elo": elo,
            "elo_err": err,
        }
    finally:
        hi.close()
        lo.close()


def resolve_stockfish() -> str | None:
    env = os.environ.get("STOCKFISH")
    if env and Path(env).exists():
        return env
    w = shutil.which("stockfish")
    if w:
        return w
    local = ROOT / "third_party" / "stockfish" / "stockfish"
    if local.exists():
        return str(local)
    return None


def stockfish_rung(engine: Path, games: int, movetime: int, outdir: Path, sf_elo: int) -> dict | None:
    sf = resolve_stockfish()
    if not sf:
        return {
            "rung": f"stockfish_elo_{sf_elo}",
            "skipped": True,
            "reason": "stockfish not in PATH; install to enable this rung",
        }
    # Use cutechess if available, else simple UCI loop
    openings = load_openings(ROOT / "tools" / "openings.epd")
    nsce = UciEngine([str(engine)], "NSCE")
    stock = UciEngine([sf], "SF")
    try:
        nsce.apply_uci_file(ROOT / "tools" / "configs" / "baseline.uci")
        stock.apply_options(
            {
                "UCI_LimitStrength": "true",
                "UCI_Elo": str(sf_elo),
                "Threads": "1",
                "Hash": "16",
            }
        )
        w = d = l = 0
        for i in range(games):
            fen = openings[i % len(openings)]
            nsce.new_game()
            stock.new_game()
            moves: list[str] = []
            a_white = i % 2 == 0
            result = "1/2-1/2"
            for ply in range(60):
                eng = (nsce if a_white else stock) if ply % 2 == 0 else (stock if a_white else nsce)
                mv = eng.go_movetime(fen, moves, movetime)
                if mv in ("0000", "(none)", "none"):
                    break
                moves.append(mv)
                st = nsce.status(fen, moves)
                if st == "checkmate":
                    white_won = ply % 2 == 0
                    if a_white:
                        result = "1-0" if white_won else "0-1"
                    else:
                        result = "0-1" if white_won else "1-0"
                    break
                if st in ("stalemate", "draw"):
                    result = "1/2-1/2"
                    break
            if result == "1-0":
                w += 1
            elif result == "0-1":
                l += 1
            else:
                d += 1
            print(f"  SF rung game {i+1}: NSCE result={result}")
        score = (w + 0.5 * d) / max(1, games)
        elo, err = elo_from_score(score, games)
        return {
            "rung": f"stockfish_elo_{sf_elo}",
            "W": w,
            "D": d,
            "L": l,
            "score": score,
            "elo": elo,
            "elo_err": err,
            "skipped": False,
        }
    finally:
        nsce.close()
        stock.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--outdir", default="")
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument("--sf-elo", type=int, default=1400)
    args = ap.parse_args()

    engine = Path(args.engine)
    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")
    outdir.mkdir(parents=True, exist_ok=True)

    results = []
    print("=== Rung 1: depth ladder ===")
    results.append(depth_ladder(engine, args.games, outdir))
    print("=== Rung 2: weak proxy ===")
    results.append(weak_nsce_rung(engine, args.games, args.movetime, outdir))
    print("=== Rung 3: Stockfish limited ===")
    results.append(stockfish_rung(engine, args.games, args.movetime, outdir, args.sf_elo))

    (outdir / "elo_ladder.json").write_text(json.dumps(results, indent=2))
    lines = [
        f"# Elo ladder — {outdir.name}",
        "",
        "| Rung | W-D-L | Score | Elo ±95% | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        if r.get("skipped"):
            lines.append(f"| {r['rung']} | — | — | — | {r.get('reason', 'skipped')} |")
        else:
            lines.append(
                f"| {r['rung']} | {r['W']}-{r['D']}-{r['L']} | {r['score']:.3f} | "
                f"{r['elo']:+.0f} ± {r['elo_err']:.0f} | |"
            )
    lines += [
        "",
        "## Weekly KPI checklist",
        "",
        "- [ ] ΔElo on current rung recorded",
        "- [ ] nodes/move from ablation report",
        "- [ ] time overrun = 0",
        "- [ ] timeouts/illegals = 0",
        "",
    ]
    kpi_path = outdir / "kpi_weekly.md"
    # append if report exists
    existing = (outdir / "report.md").read_text() if (outdir / "report.md").exists() else ""
    kpi_path.write_text("\n".join(lines) + "\n")
    # merge into report
    with (outdir / "report.md").open("a") as f:
        f.write("\n" + "\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
