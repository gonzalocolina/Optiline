#!/usr/bin/env python3
"""Stream Lichess eval JSONL (optionally zstd) into NSCE distillation records.

The Lichess eval dump is labels (centipawns / mates), not Stockfish source.
Centipawns are stored from White's point of view (positive = White better),
matching the HuggingFace fishnet-evals convention. Trainers must set
score_pov=white so Black-to-move positions are flipped to side-to-move.

Default source: https://database.lichess.org/lichess_db_eval.jsonl.zst
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO


def open_text(path: str) -> TextIO:
    if path == "-":
        return sys.stdin
    raw = Path(path)
    if raw.suffix == ".zst" or str(raw).endswith(".jsonl.zst"):
        import subprocess

        proc = subprocess.Popen(
            ["zstd", "-d", "-c", str(raw)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert proc.stdout is not None
        return proc.stdout
    return raw.open("r", encoding="utf-8")


def normalize_fen(fen: str) -> str | None:
    parts = fen.strip().split()
    if len(parts) < 4:
        return None
    if len(parts) == 4:
        parts.extend(["0", "1"])
    elif len(parts) == 5:
        parts.append("1")
    board, stm, castle, ep, half, full = parts[:6]
    if stm not in ("w", "b"):
        return None
    if "K" not in board or "k" not in board:
        return None
    return f"{board} {stm} {castle} {ep} {half} {full}"


def deepest_cp(record: dict[str, Any]) -> tuple[int, int] | None:
    evals = record.get("evals") or []
    best: tuple[int, int] | None = None
    for item in evals:
        depth = int(item.get("depth") or 0)
        pvs = item.get("pvs") or []
        if not pvs:
            continue
        pv = pvs[0]
        if "mate" in pv and pv["mate"] is not None:
            continue
        if "cp" not in pv or pv["cp"] is None:
            continue
        cp = int(pv["cp"])
        if best is None or depth >= best[1]:
            best = (cp, depth)
    return best


def iter_records(lines: Iterable[str], limit: int, max_abs_cp: int) -> Iterable[dict[str, Any]]:
    seen: set[str] = set()
    for line in lines:
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        fen = normalize_fen(str(raw.get("fen") or ""))
        if fen is None:
            continue
        key = " ".join(fen.split()[:4])
        if key in seen:
            continue
        labeled = deepest_cp(raw)
        if labeled is None:
            continue
        cp, depth = labeled
        if abs(cp) > max_abs_cp:
            continue
        seen.add(key)
        yield {
            "fen": fen,
            "score_cp": cp,
            "score_pov": "white",
            "depth": depth,
            "teacher": "lichess_eval_db",
            "bestmove": None,
        }
        if limit and len(seen) >= limit:
            break


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="-", help="JSONL, .jsonl.zst, or - for stdin")
    parser.add_argument("-o", "--output", default="train/data/lichess_evals.jsonl")
    parser.add_argument("--limit", type=int, default=120000)
    parser.add_argument("--max-abs-cp", type=int, default=8000)
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open_text(args.input) as src, out.open("w", encoding="utf-8") as dst:
        for record in iter_records(src, args.limit, args.max_abs_cp):
            dst.write(json.dumps(record, separators=(",", ":")) + "\n")
            written += 1
            if written % 10000 == 0:
                print(f"wrote {written}", file=sys.stderr)
    print(f"wrote {written} positions to {out}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
