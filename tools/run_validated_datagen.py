#!/usr/bin/env python3
"""Generate a bulletformat corpus, time it, and hold out whole games.

This does not train. It produces the dataset the confirmatory MLP run will
consume, plus the measured cost of the node budget on this machine.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from experiment_common import sha256_file, write_manifest  # noqa: E402
from train_identity import split_games  # noqa: E402
from validate_bullet_dataset import production_cost, split_errors, summarize  # noqa: E402

TARGET_POSITIONS = 100_000_000
TARGET_GAMES = 1_200_000


def _run_datagen(binary: Path, out: Path, games: int, nodes: int, threads: int, seed: int, eval_file: Path, hash_mb: int) -> tuple[float, str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        str(binary),
        "--out",
        str(out),
        "--games",
        str(games),
        "--nodes",
        str(nodes),
        "--threads",
        str(threads),
        "--eval-file",
        str(eval_file),
        "--seed",
        str(seed),
        "--hash",
        str(hash_mb),
    ]
    log_path = out.with_suffix(".log")
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as err:
        proc = subprocess.run(cmd, cwd=ROOT, stderr=err)
    elapsed = time.perf_counter() - started
    log = log_path.read_text(encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise SystemExit(log or f"datagen exited {proc.returncode}")
    return elapsed, log


def _done_counts(log: str) -> tuple[int, int]:
    for line in reversed(log.splitlines()):
        if not line.startswith("datagen done:"):
            continue
        parts = line.replace(",", " ").replace("(", " ").replace(")", " ").split()
        return int(parts[parts.index("games") - 1]), int(parts[parts.index("positions") - 1])
    raise ValueError("datagen log has no completion line")


def _rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def produce(args: argparse.Namespace) -> dict:
    binary = Path(args.datagen)
    eval_file = Path(args.eval_file)
    out_dir = Path(args.out_dir)
    source = out_dir / f"gen_seed{args.seed}.bin"
    train = out_dir / f"gen_seed{args.seed}.train.bin"
    test = out_dir / f"gen_seed{args.seed}.test.bin"
    elapsed, log = _run_datagen(
        binary, source, args.games, args.nodes, args.threads, args.seed, eval_file, args.hash_mb
    )
    scale_elapsed = None
    scale_log = ""
    if args.scale_games > 0:
        scale_path = out_dir / f"scale_seed{args.seed}_threads{args.scale_threads}.bin"
        scale_elapsed, scale_log = _run_datagen(
            binary,
            scale_path,
            args.scale_games,
            args.nodes,
            args.scale_threads,
            args.seed,
            eval_file,
            args.hash_mb,
        )
        scale_path.unlink()
    summary = summarize(source)
    if summary["errors"] or summary["only_game_zero"]:
        raise SystemExit(f"source failed validation: {summary}")
    split = split_games(source, train, test, args.fraction, args.seed)
    errors = split_errors(source, train, test)
    errors.extend(f"train: {item}" for item in summarize(train)["errors"])
    errors.extend(f"test: {item}" for item in summarize(test)["errors"])
    if errors:
        raise SystemExit("\n".join(errors))
    finished_games = summary["games"]
    cost = production_cost(
        summary["positions"], finished_games, elapsed, args.threads, TARGET_POSITIONS, TARGET_GAMES
    )
    scale_summary = None
    if scale_elapsed is not None:
        scale_games, scale_positions = _done_counts(scale_log)
        scale_summary = production_cost(
            scale_positions, scale_games, scale_elapsed, args.scale_threads, TARGET_POSITIONS, TARGET_GAMES
        )
    dossier = {
        "schema_version": 2,
        "kind": "validated_datagen",
        "generator": {
            "binary": _rel(binary),
            "binary_sha256": sha256_file(binary),
            "eval_file": _rel(eval_file),
            "eval_file_sha256": sha256_file(eval_file),
            "nodes": args.nodes,
            "threads": args.threads,
            "hash_mb": args.hash_mb,
            "seed": args.seed,
            "games_requested": args.games,
            "use_extras": True,
            "build": "Release -DNSCE_LTO=OFF -DNSCE_NATIVE=ON -DNSCE_AVX2=ON",
        },
        "source": {
            "path": _rel(source),
            "sha256": sha256_file(source),
            **{key: summary[key] for key in ("bytes", "positions", "games", "positions_per_game_min", "positions_per_game_max")},
        },
        "train": {
            "path": _rel(train),
            "sha256": sha256_file(train),
            "positions": summarize(train)["positions"],
            "games": summarize(train)["games"],
        },
        "test": {
            "path": _rel(test),
            "sha256": sha256_file(test),
            "positions": summarize(test)["positions"],
            "games": summarize(test)["games"],
            "fraction_requested": args.fraction,
            "split_seed": args.seed,
            "game_relation": "disjoint",
        },
        "split_counts": split,
        "cost": cost,
        "scale_cost": scale_summary,
        "datagen_log": log.strip().splitlines()[-1] if log.strip() else "",
    }
    train_positions = dossier["train"]["positions"]
    dossier["train_gate"] = {
        "min_positions": args.min_train_positions,
        "positions": train_positions,
        "ok": args.min_train_positions <= 0 or train_positions >= args.min_train_positions,
    }
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest_path, dossier)
    report = render_report(dossier)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report)
    if args.min_train_positions and train_positions < args.min_train_positions:
        raise SystemExit(
            f"training partition has {train_positions} positions; need >= {args.min_train_positions}"
        )
    return dossier


def render_report(dossier: dict) -> str:
    cost = dossier["cost"]
    gen = dossier["generator"]
    src = dossier["source"]
    train = dossier["train"]
    test = dossier["test"]
    lines = [
        "# Validated datagen corpus",
        "",
        "Self-play bulletformat from the Release datagen binary. No GPU and no Bullet training.",
        "Each game clears search state and is seeded by the game index, and records are written in that order, so the same command reproduces the file.",
        "The test file is a holdout of whole game ids, not a sample of positions from the training games.",
        "",
        "## Measured run",
        "",
        f"- Games requested: {gen['games_requested']}. Games written: {src['games']}.",
        f"- Positions: {src['positions']}. Bytes: {src['bytes']}.",
        f"- Nodes per move: {gen['nodes']}. Threads: {gen['threads']}. Hash: {gen['hash_mb']} MB. Seed: {gen['seed']}.",
        f"- Teacher: `{gen['eval_file']}` sha256 `{gen['eval_file_sha256']}`. UseExtras left at the datagen default (on).",
        f"- Wall time: {cost['elapsed_sec']:.3f} s. Throughput: {cost['positions_per_sec']:.2f} positions/s, {cost['games_per_sec']:.3f} games/s.",
        f"- Positions per game: {cost['positions_per_game']:.2f} (min {src['positions_per_game_min']}, max {src['positions_per_game_max']}).",
        f"- Build: {gen['build']}.",
        "",
        "## Cost of the confirmatory corpus",
        "",
        "These hours use the measured rate on this machine. They are not a 14-thread estimate.",
        "",
        f"- {cost['target_positions']:,} positions: {cost['hours_for_target_positions']:.2f} h ({cost['sec_per_million_positions']:.1f} s per million positions).",
        f"- {cost['target_games']:,} games, the README datagen command: {cost['hours_for_target_games']:.2f} h.",
        "",
    ]
    if dossier.get("scale_cost"):
        scale = dossier["scale_cost"]
        lines.extend(
            [
                "## Thread scaling check",
                "",
                f"- {scale['threads']} thread(s): {scale['positions_per_sec']:.2f} positions/s over {scale['elapsed_sec']:.3f} s.",
                f"- Same {scale['target_positions']:,} positions at that rate: {scale['hours_for_target_positions']:.2f} h.",
                "",
            ]
        )
    lines.extend(
        [
            "## Independent split",
            "",
            f"- Train: {train['games']} games, {train['positions']} positions. sha256 `{train['sha256']}`.",
            f"- Test: {test['games']} games, {test['positions']} positions. sha256 `{test['sha256']}`.",
            f"- Source sha256 `{src['sha256']}`.",
            "- Game relation: disjoint. Every source game is in exactly one side.",
            "",
        "Training should point `NSCE_DATASET` at the train file and `NSCE_TEST_SET` at the test file, with `NSCE_REQUIRE_TEST=1`.",
        "",
    ]
    gate = dossier.get("train_gate") or {}
    if gate.get("min_positions"):
        if gate.get("ok"):
            lines.append(
                f"The training partition has {gate['positions']} positions, above the {gate['min_positions']} gate."
            )
        else:
            lines.append(
                f"The training partition has {gate['positions']} positions, below the {gate['min_positions']} gate."
            )
    else:
        lines.append(
            "This corpus is below the 100,000,000-position training gate. It is the format and cost check, not a substitute for that corpus."
        )
    lines.append("")
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datagen", type=Path, default=ROOT / "build-datagen" / "nsce_datagen")
    parser.add_argument("--eval-file", type=Path, default=ROOT / "nets" / "nnue_search_leaves40k_rw0.bin")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "train" / "data" / "validated")
    parser.add_argument("--manifest", type=Path, default=ROOT / "experiments" / "20261020_datagen_validated" / "manifest.json")
    parser.add_argument("--report", type=Path, default=ROOT / "experiments" / "20261020_datagen_validated" / "report.md")
    parser.add_argument("--games", type=int, default=1200)
    parser.add_argument("--nodes", type=int, default=5000)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--hash-mb", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--fraction", type=float, default=0.05)
    parser.add_argument("--scale-games", type=int, default=80)
    parser.add_argument("--min-train-positions", type=int, default=0)
    parser.add_argument("--scale-threads", type=int, default=1)
    args = parser.parse_args()
    produce(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
