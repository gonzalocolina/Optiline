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
from experiment_common import attach_frozen_targets, build_manifest, paired_schedule, write_manifest  # noqa: E402
from uci_common import UciEngine, elo_from_wdl, load_openings  # noqa: E402


def depth_ladder(engine: Path, games: int, outdir: Path, seed: int) -> dict:
    """Stronger depth vs weaker depth using same baseline config."""
    return depth_ladder_custom(engine, games, 5, 3, outdir, seed)


def weak_nsce_rung(engine: Path, games: int, movetime: int, outdir: Path, seed: int) -> dict:
    """Baseline movetime vs very weak (tiny movetime) as stand-in for weak engine."""
    # Use configs: baseline 100ms vs "weak" via same binary with UseNNUE false + short time in match
    # Simpler: depth 4 vs depth 1 through go_depth match inline
    return depth_ladder_custom(engine, games, 4, 1, outdir, seed)


def depth_ladder_custom(engine: Path, games: int, d_hi: int, d_lo: int, outdir: Path, seed: int) -> dict:
    openings = load_openings(ROOT / "tools" / "openings_balanced.epd")
    cfg = ROOT / "tools" / "configs" / "baseline.uci"
    hi = UciEngine([str(engine)], f"d{d_hi}")
    lo = UciEngine([str(engine)], f"d{d_lo}")
    try:
        hi.apply_uci_file(cfg)
        lo.apply_uci_file(cfg)
        w = d = l = 0
        for i, (pair_id, fen, a_white) in enumerate(paired_schedule(openings, games, seed)):
            hi.new_game()
            lo.new_game()
            moves: list[str] = []
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
        elo, err = elo_from_wdl(w, d, l)
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


def resolve_stockfish(explicit: str | None = None) -> str | None:
    if explicit and Path(explicit).exists():
        return explicit
    env = os.environ.get("STOCKFISH")
    if env and Path(env).exists():
        return env
    frozen = ROOT / "third_party" / "stockfish" / "stockfish-18"
    if frozen.exists():
        return str(frozen)
    w = shutil.which("stockfish")
    if w:
        return w
    local = ROOT / "third_party" / "stockfish" / "stockfish"
    if local.exists():
        return str(local)
    return None


def stockfish_rung(
    engine: Path,
    games: int,
    movetime: int,
    outdir: Path,
    sf_elo: int,
    seed: int,
    openings_path: Path | None = None,
    max_plies: int = 120,
    nsce_config: Path | None = None,
    stockfish: str | None = None,
) -> dict | None:
    sf = resolve_stockfish(stockfish)
    if not sf:
        return {
            "rung": f"stockfish_elo_{sf_elo}",
            "skipped": True,
            "reason": "stockfish not in PATH; install to enable this rung",
        }
    book = openings_path or (ROOT / "tools" / "openings_balanced.epd")
    cfg = nsce_config or (ROOT / "tools" / "configs" / "baseline.uci")
    openings = load_openings(book)
    nsce = UciEngine([str(engine)], "NSCE")
    stock = UciEngine([sf], "SF")
    try:
        nsce.apply_uci_file(cfg)
        stock.apply_options(
            {
                "UCI_LimitStrength": "true",
                "UCI_Elo": str(sf_elo),
                "Threads": "1",
                "Hash": "16",
            }
        )
        w = d = l = 0
        for i, (_pair_id, fen, a_white) in enumerate(paired_schedule(openings, games, seed)):
            nsce.new_game()
            stock.new_game()
            moves: list[str] = []
            result = "1/2-1/2"
            for ply in range(max_plies):
                eng = (nsce if a_white else stock) if ply % 2 == 0 else (stock if a_white else nsce)
                mv = eng.go_movetime(fen, moves, movetime)
                if mv in ("0000", "(none)", "none"):
                    st = nsce.status(fen, moves)
                    if st == "checkmate":
                        white_won = ply % 2 == 1
                        if a_white:
                            result = "1-0" if white_won else "0-1"
                        else:
                            result = "0-1" if white_won else "1-0"
                    elif st in ("stalemate", "draw"):
                        result = "1/2-1/2"
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
            print(f"  SF rung game {i+1}: NSCE result={result}", flush=True)
        score = (w + 0.5 * d) / max(1, games)
        elo, err = elo_from_wdl(w, d, l)
        return {
            "rung": f"stockfish_elo_{sf_elo}",
            "W": w,
            "D": d,
            "L": l,
            "score": score,
            "elo": elo,
            "elo_err": err,
            "skipped": False,
            "stockfish": sf,
            "openings": str(book),
            "max_plies": max_plies,
            "nsce_config": str(cfg),
            "oracle": "nsce_status",
        }
    finally:
        nsce.close()
        stock.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--outdir", default="")
    ap.add_argument("--games", type=int, default=100, help="positive even number")
    ap.add_argument("--movetime", type=int, default=100)
    ap.add_argument("--sf-elo", type=int, default=1400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument(
        "--openings",
        default=str(ROOT / "tools" / "openings_balanced.epd"),
        help="EPD book for the Stockfish rung",
    )
    ap.add_argument("--max-plies", type=int, default=120)
    ap.add_argument(
        "--nsce-config",
        default=str(ROOT / "tools" / "configs" / "baseline.uci"),
    )
    ap.add_argument(
        "--only-stockfish",
        action="store_true",
        help="skip self-play depth/weak rungs; only play limited-strength Stockfish",
    )
    ap.add_argument(
        "--stockfish",
        default=str(ROOT / "third_party/stockfish/stockfish-18"),
        help="pinned Stockfish binary; do not rely on PATH",
    )
    ap.add_argument(
        "--frozen-targets",
        default=str(ROOT / "experiments/frozen-targets/manifest.json"),
    )
    args = ap.parse_args()

    engine = Path(args.engine)
    if not engine.exists():
        print(f"engine not found: {engine}", file=sys.stderr)
        return 1
    if args.games <= 0 or args.games % 2:
        print("--games must be a positive even number", file=sys.stderr)
        return 1
    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / date.today().strftime("%Y%m%d")
    outdir.mkdir(parents=True, exist_ok=True)

    results = []
    openings_path = Path(args.openings)
    nsce_config = Path(args.nsce_config)
    if not args.only_stockfish:
        print("=== Rung 1: depth ladder ===")
        results.append(depth_ladder(engine, args.games, outdir, args.seed))
        print("=== Rung 2: weak proxy ===")
        results.append(weak_nsce_rung(engine, args.games, args.movetime, outdir, args.seed))
    print("=== Stockfish limited ===")
    results.append(
        stockfish_rung(
            engine,
            args.games,
            args.movetime,
            outdir,
            args.sf_elo,
            args.seed,
            openings_path=openings_path,
            max_plies=args.max_plies,
            nsce_config=nsce_config,
            stockfish=args.stockfish or None,
        )
    )

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
    configs = [ROOT / "tools" / "configs" / "baseline.uci"]
    manifest = attach_frozen_targets(
        build_manifest(
            ROOT,
            engine,
            configs,
            openings_path,
            args.seed,
            {
                "kind": "elo_ladder",
                "games_per_rung": args.games,
                "movetime_ms": args.movetime,
                "max_plies": args.max_plies,
                "stockfish_elo": args.sf_elo,
                "stockfish": resolve_stockfish(args.stockfish or None),
                "openings": str(openings_path),
                "nsce_config": str(nsce_config),
                "oracle": "nsce_status",
                "only_stockfish": args.only_stockfish,
            },
        ),
        Path(args.frozen_targets) if args.frozen_targets else None,
    )
    write_manifest(outdir / "manifest.json", manifest)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
