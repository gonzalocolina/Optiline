#!/usr/bin/env python3
"""Validate a bulletformat datagen file and a whole-game train/test split.

The confirmatory trainer needs three facts before any GPU time is spent:
the file is aligned 32-byte ChessBoard records, game ids are stamped, and the
test games do not appear in the training file. Structural validation does not
require Bullet or a GPU.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from train_identity import RECORD, game_id, game_relation, iter_game_ids  # noqa: E402

SCORE_LIMIT = 30000


def _record_errors(record: bytes, index: int) -> list[str]:
    occ = struct.unpack_from("<Q", record, 0)[0]
    score, result, ksq, opp_ksq = struct.unpack_from("<hBBB", record, 24)
    errors = []
    if result not in (0, 1, 2):
        errors.append(f"record {index} result {result} is outside 0..2")
    if abs(score) > SCORE_LIMIT:
        errors.append(f"record {index} score {score} is outside ±{SCORE_LIMIT}")
    if ksq > 63 or opp_ksq > 63:
        errors.append(f"record {index} king squares {ksq},{opp_ksq} are outside 0..63")
    if occ.bit_count() < 2:
        errors.append(f"record {index} occupancy has {occ.bit_count()} squares")
    opp_sq = opp_ksq ^ 56
    if (occ >> ksq) & 1 == 0 or (occ >> opp_sq) & 1 == 0:
        errors.append(f"record {index} king squares are not occupied")
    return errors


def summarize(path: Path, sample_errors: int = 8) -> dict:
    data = path.read_bytes()
    if len(data) % RECORD != 0:
        raise ValueError(f"{path} is {len(data)} bytes, not a multiple of {RECORD}")
    count = len(data) // RECORD
    if count == 0:
        raise ValueError(f"{path} has no records")
    ids: dict[int, int] = {}
    errors: list[str] = []
    for index in range(count):
        record = data[index * RECORD : (index + 1) * RECORD]
        ids[game_id(record)] = ids.get(game_id(record), 0) + 1
        if len(errors) < sample_errors:
            errors.extend(_record_errors(record, index))
    return {
        "path": str(path),
        "bytes": len(data),
        "positions": count,
        "games": len(ids),
        "game_ids_min": min(ids),
        "game_ids_max": max(ids),
        "only_game_zero": ids.keys() == {0},
        "positions_per_game_min": min(ids.values()),
        "positions_per_game_max": max(ids.values()),
        "errors": errors,
    }


def split_errors(source: Path, train: Path, test: Path) -> list[str]:
    errors: list[str] = []
    relation = game_relation(train, test)
    if relation != "disjoint":
        errors.append(f"train/test game relation is {relation}, expected disjoint")
    source_ids = set(iter_game_ids(source))
    train_ids = set(iter_game_ids(train))
    test_ids = set(iter_game_ids(test))
    if source_ids <= {0}:
        errors.append("source has no per-game ids; it cannot prove an independent test split")
    if not test_ids:
        errors.append("test split has no games")
    if not train_ids:
        errors.append("train split has no games")
    missing = source_ids - (train_ids | test_ids)
    extra = (train_ids | test_ids) - source_ids
    if missing:
        errors.append(f"{len(missing)} source games are in neither split")
    if extra:
        errors.append(f"{len(extra)} split games are absent from the source")
    source_positions = sum(1 for _ in iter_game_ids(source))
    train_positions = sum(1 for _ in iter_game_ids(train))
    test_positions = sum(1 for _ in iter_game_ids(test))
    if train_positions + test_positions != source_positions:
        errors.append(
            f"split positions {train_positions}+{test_positions} != source {source_positions}"
        )
    return errors


def production_cost(positions: int, games: int, elapsed_sec: float, threads: int, target_positions: int, target_games: int) -> dict:
    if elapsed_sec <= 0 or positions <= 0 or games <= 0:
        raise ValueError("cost needs a positive elapsed time, position count, and game count")
    pos_per_sec = positions / elapsed_sec
    games_per_sec = games / elapsed_sec
    return {
        "threads": threads,
        "elapsed_sec": elapsed_sec,
        "positions_per_sec": pos_per_sec,
        "games_per_sec": games_per_sec,
        "positions_per_game": positions / games,
        "sec_per_million_positions": 1_000_000 / pos_per_sec,
        "hours_for_target_positions": target_positions / pos_per_sec / 3600,
        "target_positions": target_positions,
        "hours_for_target_games": target_games / games_per_sec / 3600,
        "target_games": target_games,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    summary = sub.add_parser("summary")
    summary.add_argument("path", type=Path)
    check = sub.add_parser("check")
    check.add_argument("--source", type=Path, required=True)
    check.add_argument("--train", type=Path, required=True)
    check.add_argument("--test", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "summary":
        print(json.dumps(summarize(args.path), indent=2))
        return 0
    errors = []
    for label, path in ("source", args.source), ("train", args.train), ("test", args.test):
        try:
            summary = summarize(path)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        errors.extend(f"{label}: {item}" for item in summary["errors"])
        if summary["only_game_zero"]:
            errors.append(f"{label}: only game id 0 is present")
    errors.extend(split_errors(args.source, args.train, args.test))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
