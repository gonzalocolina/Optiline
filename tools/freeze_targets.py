#!/usr/bin/env python3
"""Freeze explicit NSCE/Stockfish reference identities for an experiment."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from experiment_common import build_manifest, sha256_file, write_manifest  # noqa: E402


def version(binary: Path) -> str:
    try:
        proc = subprocess.run(
            [str(binary)],
            input="uci\nquit\n",
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "version-unavailable"
    for line in (proc.stdout or "").splitlines():
        if line.startswith("id name "):
            return line[len("id name ") :].strip()
    return "version-unavailable"


def target(binary: Path, label: str) -> dict[str, str]:
    if not binary.exists():
        raise FileNotFoundError(binary)
    return {
        "label": label,
        "path": str(binary.resolve()),
        "sha256": sha256_file(binary),
        "version": version(binary),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path, help="NSCE binary under test")
    parser.add_argument(
        "--stockfish19",
        required=True,
        type=Path,
        help="official Stockfish 19 pin (north-star stable)",
    )
    parser.add_argument(
        "--stockfish18",
        type=Path,
        default=None,
        help="optional historical Stockfish 18 pin (pre-2026-09-21 reports)",
    )
    parser.add_argument(
        "--stockfish-dev",
        type=Path,
        default=None,
        help="optional development snapshot (must be newer than the stable pin)",
    )
    parser.add_argument(
        "--stockfish-historical",
        type=Path,
        default=None,
        help="optional PATH/ladder binary (this lab's historical Stockfish 17)",
    )
    parser.add_argument("--config-a", type=Path, default=ROOT / "tools/configs/baseline.uci")
    parser.add_argument("--config-b", type=Path, default=ROOT / "tools/configs/baseline.uci")
    parser.add_argument("--openings", type=Path, default=ROOT / "tools/openings_balanced.epd")
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    references = [target(args.stockfish19, "stockfish-19-stable")]
    if args.stockfish18:
        references.append(target(args.stockfish18, "stockfish-18-historical"))
    if args.stockfish_dev:
        references.append(target(args.stockfish_dev, "stockfish-current-development"))
    if args.stockfish_historical:
        references.append(target(args.stockfish_historical, "stockfish-17-historical-ladder"))
    manifest = build_manifest(
        ROOT,
        args.engine,
        [args.config_a, args.config_b],
        args.openings,
        args.seed,
        {
            "kind": "frozen-strength-targets",
            "reference_targets": references,
            "controls": {
                "threads": 1,
                "hash_mb": 16,
                "equal_node_and_equal_time_required": True,
            },
        },
    )
    manifest["targets"] = {
        "nsce": target(args.engine, "nsce-under-test"),
        "stockfish": references,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(args.out, manifest)
    print(json.dumps(manifest["targets"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
