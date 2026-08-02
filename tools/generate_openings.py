#!/usr/bin/env python3
"""Generate deterministic, diverse and teacher-balanced opening FENs."""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from uci_common import UciEngine, load_openings

ROOT = Path(__file__).resolve().parents[1]


def normalized_key(fen: str) -> str:
    return " ".join(fen.split()[:4])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampler", default=str(ROOT / "build/nsce"))
    parser.add_argument("--teacher", default=shutil.which("stockfish") or "")
    parser.add_argument("--source", default=str(ROOT / "tools/openings.epd"))
    parser.add_argument("--output", default=str(ROOT / "tools/openings_balanced.epd"))
    parser.add_argument("--positions", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--min-ply", type=int, default=4)
    parser.add_argument("--max-ply", type=int, default=12)
    parser.add_argument("--teacher-depth", type=int, default=8)
    parser.add_argument("--max-abs-cp", type=int, default=150)
    parser.add_argument("--max-attempts", type=int, default=20000)
    args = parser.parse_args()
    if not args.teacher:
        parser.error("--teacher is required when stockfish is not on PATH")
    if args.positions <= 0 or args.min_ply < 0 or args.max_ply < args.min_ply:
        parser.error("invalid position or ply range")

    rng = random.Random(args.seed)
    bases = load_openings(Path(args.source))
    sampler = UciEngine([args.sampler], "opening-sampler")
    teacher = UciEngine([args.teacher], "opening-teacher")
    teacher.apply_options({"Threads": "1", "Hash": "128"})
    accepted: dict[str, str] = {}
    attempts = 0
    try:
        while len(accepted) < args.positions and attempts < args.max_attempts:
            attempts += 1
            base = bases[rng.randrange(len(bases))]
            moves: list[str] = []
            for _ in range(rng.randint(args.min_ply, args.max_ply)):
                legal = sampler.legal_moves(base, moves)
                if not legal:
                    break
                moves.append(rng.choice(legal))
            fen = sampler.current_fen(base, moves)
            if sampler.status(fen, []) != "ongoing":
                continue
            teacher.go_depth(fen, [], args.teacher_depth)
            if abs(teacher.last_score_cp) > args.max_abs_cp:
                continue
            accepted.setdefault(normalized_key(fen), fen)
            if len(accepted) % 32 == 0:
                print(f"accepted {len(accepted)}/{args.positions} after {attempts} attempts")
    finally:
        sampler.close()
        teacher.close()

    if len(accepted) < args.positions:
        raise RuntimeError(f"accepted only {len(accepted)} positions after {attempts} attempts")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(accepted.values()) + "\n")
    print(f"wrote {len(accepted)} balanced openings to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
