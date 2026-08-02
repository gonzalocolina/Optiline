"""Reproducible scheduling and provenance for engine experiments."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def paired_schedule(openings: list[str], games: int, seed: int) -> list[tuple[int, str, bool]]:
    """Return (pair_id, fen, a_is_white), with every opening used in color-reversed pairs."""
    if games <= 0 or games % 2:
        raise ValueError("--games must be a positive even number")
    if not openings:
        raise ValueError("at least one opening is required")

    rng = random.Random(seed)
    order = list(openings)
    schedule: list[tuple[int, str, bool]] = []
    pair_id = 0
    while len(schedule) < games:
        rng.shuffle(order)
        for fen in order:
            schedule.append((pair_id, fen, True))
            schedule.append((pair_id, fen, False))
            pair_id += 1
            if len(schedule) >= games:
                break
    return schedule


def _run(command: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def build_manifest(
    root: Path,
    engine: Path,
    configs: Iterable[Path],
    openings: Path,
    seed: int,
    extra: dict | None = None,
) -> dict:
    engine = engine.resolve()
    config_paths = [path.resolve() for path in configs]
    cache = engine.parent / "CMakeCache.txt"
    return {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "seed": seed,
        "git": {
            "commit": _run(["git", "rev-parse", "HEAD"], root),
            "dirty": bool(_run(["git", "status", "--porcelain"], root).strip()),
        },
        "platform": {
            "system": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "toolchain": {
            "cxx": _run(["c++", "--version"], root).splitlines()[0],
            "cmake_cache_sha256": sha256_file(cache) if cache.exists() else None,
        },
        "artifacts": {
            "engine": str(engine),
            "engine_sha256": sha256_file(engine),
            "configs": {str(path): sha256_file(path) for path in config_paths},
            "openings": str(openings.resolve()),
            "openings_sha256": sha256_file(openings),
        },
        "parameters": extra or {},
    }


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
