#!/usr/bin/env python3
"""Distillation scaffold: query a teacher UCI engine for eval/bestmove labels.

Teacher defaults to Stockfish if available; otherwise NSCE at high depth.
Writes JSONL suitable for later NNUE/policy training.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402


def label_position(teacher: UciEngine, fen: str, depth: int) -> dict:
    teacher.new_game()
    teacher.set_position(fen, [])
    teacher._send(f"go depth {depth}")
    lines = teacher._wait_for("bestmove", timeout=120.0)
    score_cp = None
    best = "0000"
    for line in lines:
        if line.startswith("info ") and " score cp " in line:
            parts = line.split()
            if "cp" in parts:
                score_cp = int(parts[parts.index("cp") + 1])
        if line.startswith("bestmove"):
            best = line.split()[1]
    return {"fen": fen, "bestmove": best, "score_cp": score_cp, "depth": depth}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", default="")
    ap.add_argument("--depth", type=int, default=8)
    ap.add_argument("--positions", type=int, default=16)
    ap.add_argument("-o", "--output", default=str(ROOT / "train/data/distill.jsonl"))
    args = ap.parse_args()

    teacher_cmd = args.teacher or shutil.which("stockfish") or str(ROOT / "build" / "nsce")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    openings = load_openings(ROOT / "tools" / "openings.epd")

    eng = UciEngine([teacher_cmd], "teacher")
    if "nsce" in teacher_cmd:
        eng.apply_uci_file(ROOT / "tools/configs/baseline.uci")
    try:
        with out.open("w") as f:
            for i in range(args.positions):
                fen = openings[i % len(openings)]
                lab = label_position(eng, fen, args.depth)
                lab["teacher"] = teacher_cmd
                f.write(json.dumps(lab) + "\n")
                print(f"{i+1}: {lab['bestmove']} cp={lab['score_cp']}")
    finally:
        eng.close()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
