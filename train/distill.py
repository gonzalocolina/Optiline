#!/usr/bin/env python3
"""Build a reproducible, position-diverse NNUE distillation dataset."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402


def label_position(teacher: UciEngine, fen: str, depth: int | None, nodes: int | None) -> dict:
    teacher.set_position(fen, [])
    if nodes:
        teacher._send(f"go nodes {nodes}")
    else:
        teacher._send(f"go depth {depth}")
    lines = teacher._wait_for("bestmove", timeout=120.0)
    score_cp = None
    best = "0000"
    for line in lines:
        if line.startswith("info ") and "score" in line:
            parts = line.split()
            if "cp" in parts:
                score_cp = int(parts[parts.index("cp") + 1])
            elif "mate" in parts:
                mate = int(parts[parts.index("mate") + 1])
                score_cp = (32000 - min(abs(mate) * 2, 255)) * (1 if mate > 0 else -1)
        if line.startswith("bestmove"):
            best = line.split()[1]
    return {
        "fen": fen,
        "bestmove": best,
        "score_cp": score_cp,
        "score_pov": "side_to_move",
        "depth": depth,
        "nodes": nodes,
    }


def sample_position(
    sampler: UciEngine,
    opening: str,
    rng: random.Random,
    min_ply: int,
    max_ply: int,
) -> tuple[str, int]:
    moves: list[str] = []
    target_ply = rng.randint(min_ply, max_ply)
    for _ in range(target_ply):
        legal = sampler.legal_moves(opening, moves)
        if not legal:
            break
        moves.append(rng.choice(legal))
    return sampler.current_fen(opening, moves), len(moves)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--teacher",
        default=str(ROOT / "build" / "nsce"),
        help="teacher binary; default is the current local NSCE build",
    )
    ap.add_argument("--teacher-config", default=str(ROOT / "tools/configs/baseline.uci"))
    ap.add_argument("--depth", type=int, default=8)
    ap.add_argument("--nodes", type=int, default=0, help="If >0, label with go nodes N instead of depth")
    ap.add_argument("--positions", type=int, default=2000)
    ap.add_argument("--sampler", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--seed", type=int, default=20260802)
    ap.add_argument("--min-ply", type=int, default=8)
    ap.add_argument("--max-ply", type=int, default=60)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("-o", "--output", default=str(ROOT / "train/data/distill.jsonl"))
    args = ap.parse_args()
    if args.positions <= 0:
        ap.error("--positions must be positive")
    if args.nodes <= 0 and args.depth <= 0:
        ap.error("need --depth or --nodes")
    if args.min_ply < 0 or args.max_ply < args.min_ply:
        ap.error("invalid ply sampling range")

    teacher_cmd = args.teacher or os.environ.get("STOCKFISH") or str(ROOT / "build" / "nsce")
    if not Path(teacher_cmd).exists() and shutil.which(teacher_cmd) is None:
        raise RuntimeError(f"teacher not found: {teacher_cmd}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    openings = load_openings(ROOT / "tools" / "openings_balanced.epd")
    start = 0
    if args.resume and out.exists():
        start = sum(1 for line in out.open() if line.strip())
        print(f"resuming from {start} existing samples")

    eng = UciEngine([teacher_cmd], "teacher")
    sampler = UciEngine([args.sampler], "sampler")
    eng.apply_options({"Threads": "1", "Hash": "16"})
    if "nsce" in teacher_cmd:
        eng.apply_uci_file(Path(args.teacher_config))
    try:
        mode = "a" if start else "w"
        with out.open(mode) as f:
            for i in range(start, args.positions):
                rng = random.Random(args.seed + i)
                opening = openings[i % len(openings)]
                fen, sampled_ply = sample_position(
                    sampler, opening, rng, args.min_ply, args.max_ply
                )
                lab = label_position(eng, fen, None if args.nodes else args.depth, args.nodes or None)
                lab["teacher"] = teacher_cmd
                lab["sampled_ply"] = sampled_ply
                lab["seed"] = args.seed
                f.write(json.dumps(lab) + "\n")
                f.flush()
                print(f"{i+1}: {lab['bestmove']} cp={lab['score_cp']}")
    finally:
        eng.close()
        sampler.close()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
