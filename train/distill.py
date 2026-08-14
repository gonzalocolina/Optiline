#!/usr/bin/env python3
"""Build a reproducible, position-diverse NNUE distillation dataset."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from collections.abc import Iterator
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
    teacher.clear_hash()
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


def iter_fens(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fen = str(record.get("fen") or "").strip()
                if fen:
                    yield fen
                continue
            parts = line.rstrip(";").split()
            if len(parts) < 4:
                continue
            fen = " ".join(parts[:4])
            if len(parts) >= 6 and parts[4].isdigit():
                fen = " ".join(parts[:6])
            else:
                fen += " 0 1"
            yield fen


def format_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds or seconds == float("inf"):
        return "?"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def emit_progress(
    done: int,
    total: int,
    started: float,
    already: int,
    move: str,
    score_cp: int | None,
) -> None:
    elapsed = max(time.monotonic() - started, 1e-6)
    newly = max(done - already, 0)
    rate = newly / elapsed
    remaining = max(total - done, 0)
    eta = remaining / rate if rate > 0 else float("inf")
    pct = 100.0 * done / total if total else 0.0
    print(
        f"distill {done}/{total} ({pct:.1f}%)  {rate:.1f} pos/s  "
        f"elapsed {format_duration(elapsed)}  eta {format_duration(eta)}  "
        f"last {move} cp={score_cp}",
        file=sys.stderr,
        flush=True,
    )


def write_label(handle, lab: dict, verbose: bool, index: int) -> None:
    handle.write(json.dumps(lab) + "\n")
    handle.flush()
    if verbose:
        print(f"{index + 1}: {lab['bestmove']} cp={lab['score_cp']}", flush=True)


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
    ap.add_argument(
        "--fens",
        default="",
        help="JSONL/EPD of existing FENs to label (skips random-walk sampling)",
    )
    ap.add_argument("--sampler", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--seed", type=int, default=20260802)
    ap.add_argument("--min-ply", type=int, default=8)
    ap.add_argument("--max-ply", type=int, default=60)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="print a stderr progress line every N labeled positions (0 disables)",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="print every labeled move to stdout",
    )
    ap.add_argument("-o", "--output", default=str(ROOT / "train/data/distill.jsonl"))
    args = ap.parse_args()
    if args.positions <= 0:
        ap.error("--positions must be positive")
    if args.nodes <= 0 and args.depth <= 0:
        ap.error("need --depth or --nodes")
    if args.min_ply < 0 or args.max_ply < args.min_ply:
        ap.error("invalid ply sampling range")
    fens_path = Path(args.fens) if args.fens else None
    if fens_path is not None and not fens_path.exists():
        raise RuntimeError(f"FEN source not found: {fens_path}")

    teacher_cmd = args.teacher or os.environ.get("STOCKFISH") or str(ROOT / "build" / "nsce")
    if not Path(teacher_cmd).exists() and shutil.which(teacher_cmd) is None:
        raise RuntimeError(f"teacher not found: {teacher_cmd}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    start = 0
    if args.resume and out.exists():
        start = sum(1 for line in out.open() if line.strip())
        print(f"resuming from {start} existing samples", file=sys.stderr, flush=True)
    if start >= args.positions:
        print(f"{out} already has {start} samples (>= {args.positions})", file=sys.stderr, flush=True)
        return 0
    progress_every = args.progress_every
    started = time.monotonic()
    labeled = 0

    eng = UciEngine([teacher_cmd], "teacher")
    sampler = None if fens_path is not None else UciEngine([args.sampler], "sampler")
    openings = [] if fens_path is not None else load_openings(ROOT / "tools" / "openings_balanced.epd")
    eng.apply_options({"Threads": "1", "Hash": "16"})
    if "nsce" in teacher_cmd:
        eng.apply_uci_file(Path(args.teacher_config))
    try:
        mode = "a" if start else "w"
        with out.open(mode) as f:
            if fens_path is not None:
                for index, fen in enumerate(iter_fens(fens_path)):
                    if index < start:
                        continue
                    if index >= args.positions:
                        break
                    lab = label_position(eng, fen, None if args.nodes else args.depth, args.nodes or None)
                    lab["teacher"] = teacher_cmd
                    lab["sampled_ply"] = None
                    lab["seed"] = args.seed
                    lab["source_index"] = index
                    write_label(f, lab, args.verbose, index)
                    labeled += 1
                    done = index + 1
                    if labeled == 1 or (progress_every and done % progress_every == 0):
                        emit_progress(
                            done, args.positions, started, start, lab["bestmove"], lab["score_cp"]
                        )
            else:
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
                    write_label(f, lab, args.verbose, i)
                    labeled += 1
                    done = i + 1
                    if labeled == 1 or (progress_every and done % progress_every == 0):
                        emit_progress(
                            done, args.positions, started, start, lab["bestmove"], lab["score_cp"]
                        )
    finally:
        eng.close()
        if sampler is not None:
            sampler.close()
    emit_progress(min(start + labeled, args.positions), args.positions, started, start, "-", None)
    print(f"wrote {out}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
