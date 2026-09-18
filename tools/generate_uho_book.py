#!/usr/bin/env python3
"""Build a UHO-style 8-move (16-ply) EPD book with NSCE, no PATH stockfish.

UHO = unbalanced human-like openings: unique positions after 8 moves with a
modest static-eval imbalance so long SPRTs do not recycle 128 balanced lines.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from uci_common import UciEngine, load_openings

ROOT = Path(__file__).resolve().parents[1]


def normalized_key(fen: str) -> str:
    return " ".join(fen.split()[:4])


def epd_line(fen: str) -> str:
    # Four EPD fields only. Do not glue ';' onto the EP square: fastchess
    # splits on spaces, so "f6;" / "-;" fail Square::is_valid_string_sq.
    parts = fen.split()
    return " ".join(parts[:4])


def walk_plies(sampler: UciEngine, base: str, plies: int, rng: random.Random) -> str | None:
    moves: list[str] = []
    for _ in range(plies):
        legal = sampler.legal_moves(base, moves)
        if not legal:
            return None
        moves.append(rng.choice(legal))
    if sampler.status(base, moves) != "ongoing":
        return None
    return sampler.current_fen(base, moves)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampler", default=str(ROOT / "build/nsce"))
    parser.add_argument("--config", default=str(ROOT / "tools/configs/baseline.uci"))
    parser.add_argument("--source", default=str(ROOT / "tools/openings.epd"))
    parser.add_argument("--output", default=str(ROOT / "tools/openings_uho.epd"))
    parser.add_argument("--positions", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260915)
    parser.add_argument("--plies", type=int, default=16, help="8 moves = 16 plies")
    parser.add_argument("--min-abs-cp", type=int, default=60)
    parser.add_argument("--max-abs-cp", type=int, default=250)
    parser.add_argument("--max-attempts", type=int, default=200000)
    args = parser.parse_args()
    if args.positions <= 0 or args.plies < 2:
        parser.error("invalid positions or plies")
    if args.min_abs_cp < 0 or args.max_abs_cp < args.min_abs_cp:
        parser.error("invalid cp window")

    rng = random.Random(args.seed)
    bases = load_openings(Path(args.source))
    sampler = UciEngine([args.sampler], "uho-sampler", cwd=ROOT)
    sampler.apply_uci_file(Path(args.config))
    sampler.apply_options({"Threads": "1", "Hash": "16"})
    accepted: dict[str, str] = {}
    attempts = 0
    skipped_balance = 0
    try:
        while len(accepted) < args.positions and attempts < args.max_attempts:
            attempts += 1
            extra = rng.randint(0, 4)
            plies = args.plies + extra - extra % 2  # stay on White-to-move-ish after 8 moves
            plies = max(args.plies, min(20, plies))
            fen = walk_plies(sampler, bases[rng.randrange(len(bases))], plies, rng)
            if fen is None:
                continue
            key = normalized_key(fen)
            if key in accepted:
                continue
            score = abs(sampler.evaluate(fen, []))
            if score < args.min_abs_cp or score > args.max_abs_cp:
                skipped_balance += 1
                continue
            accepted[key] = epd_line(fen)
            if len(accepted) % 256 == 0:
                print(
                    f"accepted {len(accepted)}/{args.positions} after {attempts} attempts "
                    f"(skipped {skipped_balance} outside {args.min_abs_cp}..{args.max_abs_cp} cp)",
                    flush=True,
                )
    finally:
        sampler.close()

    if len(accepted) < args.positions:
        raise RuntimeError(
            f"accepted only {len(accepted)} positions after {attempts} attempts "
            f"(skipped {skipped_balance} by eval window)"
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(accepted.values()) + "\n")
    print(f"wrote {len(accepted)} UHO-style openings to {output} ({attempts} attempts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
