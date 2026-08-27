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
sys.path.insert(0, str(ROOT / "train"))

from eval_scale import teacher_family  # noqa: E402
from uci_common import UciEngine, load_openings  # noqa: E402

DEFAULT_LEAF_SITES = ("q_stand_pat", "static", "in_check_static")


def _annotate_teacher(lab: dict, teacher: UciEngine, command: str, kind: str) -> dict:
    lab["score_kind"] = kind
    lab["raw_teacher_cp"] = lab.get("score_cp")
    lab["teacher_family"] = teacher_family(teacher.identity, command)
    lab["score_pov"] = lab.get("score_pov") or "side_to_move"
    return lab


def label_static(teacher: UciEngine, fen: str) -> dict:
    """Label with the deployed static eval (network + extras exactly as C++ runs)."""
    teacher.set_position(fen, [])
    details = teacher.evaluate_details(fen, [])
    deployed = details.get("eval")
    return {
        "fen": fen,
        "bestmove": "0000",
        "score_cp": deployed,
        "score_pov": "side_to_move",
        "depth": 0,
        "nodes": 0,
        "completed_depth": 0,
        "searched_nodes": 0,
        "score_bound": "exact",
        "pv": [],
        "teacher_nnue_cp": details.get("nnue"),
        "extras_cp": details.get("extras"),
        "deployed_eval_cp": deployed,
        "use_extras": details.get("use_extras"),
    }


def label_position(teacher: UciEngine, fen: str, depth: int | None, nodes: int | None) -> dict:
    teacher.new_game()
    teacher.set_position(fen, [])
    if nodes:
        teacher._send(f"go nodes {nodes}")
    else:
        teacher._send(f"go depth {depth}")
    lines = teacher._wait_for("bestmove", timeout=120.0)
    score_cp = None
    best = "0000"
    completed_depth = 0
    searched_nodes = 0
    score_bound = "exact"
    pv: list[str] = []
    for line in lines:
        if line.startswith("info ") and "score" in line:
            parts = line.split()
            if "depth" in parts:
                completed_depth = max(completed_depth, int(parts[parts.index("depth") + 1]))
            if "nodes" in parts:
                searched_nodes = max(searched_nodes, int(parts[parts.index("nodes") + 1]))
            if "bound" in parts:
                score_bound = parts[parts.index("bound") + 1]
            if "cp" in parts:
                score_cp = int(parts[parts.index("cp") + 1])
            elif "mate" in parts:
                mate = int(parts[parts.index("mate") + 1])
                score_cp = (32000 - min(abs(mate) * 2, 255)) * (1 if mate > 0 else -1)
            if "pv" in parts:
                pv = parts[parts.index("pv") + 1 :]
        if line.startswith("bestmove"):
            best = line.split()[1]
    details = {}
    if "NSCE" in teacher.identity.get("id_name", "").upper():
        details = teacher.evaluate_details(fen, [])
    teacher.clear_hash()
    return {
        "fen": fen,
        "bestmove": best,
        "score_cp": score_cp,
        "score_pov": "side_to_move",
        "depth": depth,
        "nodes": nodes,
        "completed_depth": completed_depth,
        "searched_nodes": searched_nodes,
        "score_bound": score_bound,
        "pv": pv,
        "teacher_nnue_cp": details.get("nnue"),
        "extras_cp": details.get("extras"),
        "deployed_eval_cp": details.get("eval"),
        "use_extras": details.get("use_extras"),
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


def sample_self_play_position(
    sampler: UciEngine,
    opening: str,
    rng: random.Random,
    min_ply: int,
    max_ply: int,
    depth: int,
) -> tuple[str, int, str | None]:
    """Sample a position from a shallow teacher trajectory and retain terminal outcomes."""
    target_ply = rng.randint(min_ply, max_ply)
    moves: list[str] = []
    terminal_result: str | None = None
    for ply in range(max_ply + 32):
        if ply == target_ply:
            sampled_fen = sampler.current_fen(opening, moves)
        move = sampler.go_depth(opening, moves, depth)
        if move in {"0000", "(none)", "none"}:
            status = sampler.status(opening, moves)
            terminal_result = "1-0" if status == "checkmate" and (ply & 1) else "0-1" if status == "checkmate" else "1/2-1/2"
            break
        moves.append(move)
        status = sampler.status(opening, moves)
        if status in {"checkmate", "stalemate", "draw"}:
            terminal_result = "1-0" if status == "checkmate" and (ply & 1) == 0 else "0-1" if status == "checkmate" else "1/2-1/2"
            break
    else:
        terminal_result = "1/2-1/2"
    if "sampled_fen" not in locals():
        sampled_fen = sampler.current_fen(opening, moves)
        target_ply = len(moves)
    return sampled_fen, target_ply, terminal_result


def iter_source_records(path: Path) -> Iterator[dict]:
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
                    yield record
                continue
            parts = line.rstrip(";").split()
            if len(parts) < 4:
                continue
            fen = " ".join(parts[:4])
            if len(parts) >= 6 and parts[4].isdigit():
                fen = " ".join(parts[:6])
            else:
                fen += " 0 1"
            yield {"fen": fen}


def keep_source_record(
    record: dict,
    leaf_sites: set[str] | None,
    label_kinds: set[str] | None = None,
) -> bool:
    if label_kinds:
        kind = str(record.get("label_kind") or "search_leaf")
        if kind not in label_kinds:
            return False
    if not leaf_sites:
        return True
    site = record.get("site")
    if not site:
        return True
    return str(site) in leaf_sites


def reservoir_sample(records: Iterator[dict], k: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    sample: list[dict] = []
    started = time.monotonic()
    for index, record in enumerate(records):
        if len(sample) < k:
            sample.append(record)
        else:
            slot = rng.randint(0, index)
            if slot < k:
                sample[slot] = record
        scanned = index + 1
        if scanned % 100000 == 0:
            elapsed = max(time.monotonic() - started, 1e-6)
            print(
                f"reservoir {scanned}  kept {len(sample)}/{k}  "
                f"{scanned / elapsed:.0f} rec/s  elapsed {format_duration(elapsed)}",
                file=sys.stderr,
                flush=True,
            )
    return sample


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
        default="",
        help="teacher binary; defaults to $STOCKFISH or the current local NSCE build",
    )
    ap.add_argument("--teacher-config", default=str(ROOT / "tools/configs/baseline.uci"))
    ap.add_argument(
        "--label",
        choices=("static", "search"),
        default="search",
        help="static = deployed C++ eval (clone the arbiter); search = go depth/nodes",
    )
    ap.add_argument("--depth", type=int, default=8)
    ap.add_argument("--nodes", type=int, default=0, help="If >0, label with go nodes N instead of depth")
    ap.add_argument("--positions", type=int, default=2000)
    ap.add_argument(
        "--fens",
        default="",
        help="JSONL/EPD of existing FENs to label (skips random-walk sampling)",
    )
    ap.add_argument(
        "--sample-uniform",
        action="store_true",
        help="when reading --fens, reservoir-sample --positions uniformly (not the file prefix)",
    )
    ap.add_argument(
        "--leaf-sites",
        default="",
        help="comma-separated LeafTelemetry sites to keep (empty keeps all; "
        f"typical clone set: {','.join(DEFAULT_LEAF_SITES)})",
    )
    ap.add_argument(
        "--label-kinds",
        default="",
        help="comma-separated label_kind values to keep (path, search_leaf); empty keeps all",
    )
    ap.add_argument("--sampler", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--self-play", action="store_true", help="sample positions from shallow teacher trajectories")
    ap.add_argument("--self-play-depth", type=int, default=4)
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
    if args.label == "search" and args.nodes <= 0 and args.depth <= 0:
        ap.error("search labels need --depth or --nodes")
    if args.resume and args.sample_uniform:
        ap.error("--resume cannot be combined with --sample-uniform")
    if args.min_ply < 0 or args.max_ply < args.min_ply:
        ap.error("invalid ply sampling range")
    fens_path = Path(args.fens) if args.fens else None
    if fens_path is not None and not fens_path.exists():
        raise RuntimeError(f"FEN source not found: {fens_path}")
    leaf_sites = {item.strip() for item in args.leaf_sites.split(",") if item.strip()} or None
    label_kinds = {item.strip() for item in args.label_kinds.split(",") if item.strip()} or None

    if args.label == "static":
        teacher_cmd = args.teacher or str(ROOT / "build" / "nsce")
    else:
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

    if fens_path is None and not args.self_play:
        print(
            "warning: random-walk sampling is not the eval protocol; "
            "prefer train/collect_leaves.py or selfplay --positions-out",
            file=sys.stderr,
            flush=True,
        )
    eng = UciEngine([teacher_cmd], "teacher")
    sampler = None if fens_path is not None else UciEngine([args.sampler], "sampler")
    openings = [] if fens_path is not None else load_openings(ROOT / "tools" / "openings_balanced.epd")
    eng.apply_options({"Threads": "1", "Hash": "16"})
    if "nsce" in teacher_cmd.lower():
        eng.apply_uci_file(Path(args.teacher_config))
    if args.label == "static" and teacher_family(eng.identity, teacher_cmd) != "nsce":
        raise RuntimeError("static labels require an NSCE teacher with `eval details`")

    def label_fen(fen: str) -> dict:
        if args.label == "static":
            lab = label_static(eng, fen)
        else:
            lab = label_position(eng, fen, None if args.nodes else args.depth, args.nodes or None)
        _annotate_teacher(lab, eng, teacher_cmd, args.label)
        lab["teacher"] = teacher_cmd
        lab["teacher_identity"] = eng.identity
        lab["seed"] = args.seed
        return lab

    try:
        mode = "a" if start else "w"
        with out.open(mode) as f:
            if fens_path is not None:
                source_iter = (
                    record
                    for record in iter_source_records(fens_path)
                    if keep_source_record(record, leaf_sites, label_kinds)
                )
                if args.sample_uniform:
                    sources = reservoir_sample(source_iter, args.positions, args.seed)
                    print(
                        f"uniform sample {len(sources)} / requested {args.positions}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    sources = []
                    for record in source_iter:
                        if len(sources) >= args.positions:
                            break
                        sources.append(record)
                for kept, source in enumerate(sources):
                    if kept < start:
                        continue
                    fen = str(source["fen"])
                    lab = label_fen(fen)
                    lab["sampled_ply"] = None
                    lab["source_index"] = kept
                    lab["source_game"] = source.get("source_game") or f"fen:{args.seed}:{kept}"
                    lab["sample_uniform"] = bool(args.sample_uniform)
                    for key in (
                        "result",
                        "outcome",
                        "site",
                        "in_check",
                        "pieces",
                        "ply",
                        "halfmove",
                        "phase",
                        "label_kind",
                        "opening_index",
                        "color",
                        "termination",
                    ):
                        if key in source and key not in lab:
                            lab[key] = source[key]
                    write_label(f, lab, args.verbose, kept)
                    labeled += 1
                    done = kept + 1
                    if labeled == 1 or (progress_every and done % progress_every == 0):
                        emit_progress(
                            done, args.positions, started, start, lab["bestmove"], lab["score_cp"]
                        )
            else:
                for i in range(start, args.positions):
                    rng = random.Random(args.seed + i)
                    opening = openings[i % len(openings)]
                    if args.self_play:
                        fen, sampled_ply, result = sample_self_play_position(
                            sampler, opening, rng, args.min_ply, args.max_ply, args.self_play_depth
                        )
                    else:
                        fen, sampled_ply = sample_position(sampler, opening, rng, args.min_ply, args.max_ply)
                        result = None
                    lab = label_fen(fen)
                    lab["sampled_ply"] = sampled_ply
                    lab["source_game"] = f"trajectory:{args.seed}:{i}"
                    lab["opening_index"] = i % len(openings)
                    if result is not None:
                        lab["result"] = result
                        lab["source"] = "self_play"
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
