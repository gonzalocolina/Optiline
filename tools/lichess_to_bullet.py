#!/usr/bin/env python3
"""Stream Lichess eval JSONL into bulletformat ChessBoard records.

The public dump is https://database.lichess.org/lichess_db_eval.jsonl.zst
(CC0, about 22 GB compressed, 416 million positions). Each line is a FEN plus
one or more Stockfish searches. This keeps the deepest non-mate centipawn
score, white-relative, and packs the 32-byte record the HL trainer reads.

The dump has no game result. The stored result is 1/2. Train with NSCE_WDL=0
so the label is sigmoid(cp / 400) and the result byte is unused.

Example
-------
curl -L https://database.lichess.org/lichess_db_eval.jsonl.zst \\
  | zstd -d -c \\
  | python3 tools/lichess_to_bullet.py --limit 2000000 --min-depth 12 \\
      -o train/data/lichess_eval.bin --holdout train/data/lichess_eval_holdout.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "train"))

from import_lichess_evals import deepest_cp, normalize_fen  # noqa: E402
from jsonl_to_bullet import fen_to_record  # noqa: E402


def position_key(fen: str) -> int:
    """8-byte hash of the piece placement, side, castling and en passant."""
    key = " ".join(fen.split()[:4]).encode()
    return int.from_bytes(hashlib.blake2s(key, digest_size=8).digest(), "little")


def iter_packed(
    lines: Iterable[str],
    limit: int,
    min_depth: int,
    max_abs_cp: int,
) -> Iterable[tuple[str, int, int, bytes]]:
    seen: set[int] = set()
    kept = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            raw: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        fen = normalize_fen(str(raw.get("fen") or ""))
        if fen is None:
            continue
        labeled = deepest_cp(raw)
        if labeled is None:
            continue
        cp, depth = labeled
        if depth < min_depth or abs(cp) > max_abs_cp:
            continue
        key = position_key(fen)
        if key in seen:
            continue
        try:
            record = fen_to_record(fen, cp)
        except (ValueError, IndexError):
            # A few dump rows are not 32-piece chess positions.
            continue
        seen.add(key)
        kept += 1
        yield fen, cp, depth, record
        if limit and kept >= limit:
            break


def shuffle_bin(path: Path, seed: int) -> int:
    blob = path.read_bytes()
    if len(blob) % 32 != 0:
        raise ValueError(f"{path} is {len(blob)} bytes, not a multiple of 32")
    records = [blob[i : i + 32] for i in range(0, len(blob), 32)]
    random.Random(seed).shuffle(records)
    path.write_bytes(b"".join(records))
    return len(records)


def convert(
    src: TextIO,
    output: Path,
    holdout_path: Path | None,
    limit: int,
    holdout: int,
    min_depth: int,
    max_abs_cp: int,
) -> tuple[int, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if holdout_path is not None:
        holdout_path.parent.mkdir(parents=True, exist_ok=True)
    train_n = 0
    hold_n = 0
    scanned = 0
    with output.open("wb") as out:
        hold_fh = holdout_path.open("w", encoding="utf-8") if holdout_path is not None else None
        try:
            for fen, cp, depth, record in iter_packed(src, limit + holdout, min_depth, max_abs_cp):
                scanned += 1
                if hold_fh is not None and hold_n < holdout:
                    hold_fh.write(
                        json.dumps(
                            {"fen": fen, "score_cp": cp, "depth": depth, "score_pov": "white"},
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    hold_n += 1
                    continue
                out.write(record)
                train_n += 1
                if train_n % 100000 == 0:
                    print(f"wrote {train_n}", file=sys.stderr, flush=True)
                if limit and train_n >= limit:
                    break
        finally:
            if hold_fh is not None:
                hold_fh.close()
    return train_n, hold_n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="-", help="JSONL path, or - for stdin")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=2_000_000, help="training records to keep")
    ap.add_argument("--holdout", type=int, default=0, help="extra labeled positions kept out of the bin")
    ap.add_argument("--holdout-path", type=Path, default=None)
    ap.add_argument("--min-depth", type=int, default=12)
    ap.add_argument("--max-abs-cp", type=int, default=3000)
    ap.add_argument("--shuffle-seed", type=int, default=20261018)
    ap.add_argument("--no-shuffle", action="store_true")
    args = ap.parse_args()
    if args.output.name == "gen0.bin":
        raise SystemExit("refusing to write onto gen0.bin")
    holdout_path = args.holdout_path
    if args.holdout and holdout_path is None:
        holdout_path = args.output.with_suffix(".holdout.jsonl")

    if args.input == "-":
        src: TextIO = sys.stdin
        close = False
    else:
        src = Path(args.input).open(encoding="utf-8")
        close = True
    try:
        train_n, hold_n = convert(
            src,
            args.output,
            holdout_path,
            args.limit,
            args.holdout,
            args.min_depth,
            args.max_abs_cp,
        )
    finally:
        if close:
            src.close()
    if not args.no_shuffle and train_n:
        shuffle_bin(args.output, args.shuffle_seed)
    print(
        f"wrote {train_n} records ({train_n * 32} bytes) to {args.output}; holdout {hold_n}",
        flush=True,
    )
    return 0 if train_n else 1


if __name__ == "__main__":
    raise SystemExit(main())
