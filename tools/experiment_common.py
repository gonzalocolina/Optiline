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


def _resolve_artifact(root: Path, value: str) -> Path | None:
    value = value.strip()
    if not value or value.lower() in {"internal", "hce", "<internal>", "<empty>"}:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _config_options(root: Path, configs: list[Path]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for config in configs:
        if not config.exists():
            continue
        for line in config.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) < 5 or parts[0].lower() != "setoption" or parts[1].lower() != "name":
                continue
            try:
                value_index = parts.index("value")
            except ValueError:
                continue
            name = " ".join(parts[2:value_index])
            resolved[name] = " ".join(parts[value_index + 1 :])
    return resolved


def _cpu_governor() -> str | None:
    governors = sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_governor"))
    values = []
    for path in governors:
        try:
            values.append(path.read_text().strip())
        except OSError:
            pass
    return ",".join(sorted(set(values))) if values else None


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
    options = _config_options(root, config_paths)
    referenced: dict[str, str] = {}
    for option in ("EvalFile", "PolicyFile", "ControllerFile"):
        artifact = _resolve_artifact(root, options.get(option, ""))
        if artifact is not None and artifact.exists():
            referenced[str(artifact)] = sha256_file(artifact)
    engine_b = None
    if extra and extra.get("engine_b"):
        engine_b = Path(str(extra["engine_b"])).resolve()
        if engine_b.exists():
            referenced[str(engine_b)] = sha256_file(engine_b)
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        try:
            affinity = sorted(os.sched_getaffinity(0))
        except OSError:
            pass
    return {
        "schema_version": 2,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "seed": seed,
        "git": {
            "commit": _run(["git", "rev-parse", "HEAD"], root),
            "branch": _run(["git", "branch", "--show-current"], root),
            "status_porcelain": _run(["git", "status", "--porcelain"], root),
            "dirty": bool(_run(["git", "status", "--porcelain"], root).strip()),
        },
        "platform": {
            "system": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "affinity": affinity,
            "cpu_governor": _cpu_governor(),
        },
        "toolchain": {
            "cxx": _run(["c++", "--version"], root).splitlines()[0],
            "cmake_cache_sha256": sha256_file(cache) if cache.exists() else None,
        },
        "artifacts": {
            "engine": str(engine),
            "engine_sha256": sha256_file(engine),
            "engine_b": str(engine_b) if engine_b is not None else None,
            "engine_b_sha256": sha256_file(engine_b) if engine_b is not None and engine_b.exists() else None,
            "configs": {str(path): sha256_file(path) for path in config_paths},
            "openings": str(openings.resolve()),
            "openings_sha256": sha256_file(openings),
            "referenced_files": referenced,
        },
        "resolved_options": options,
        "measurement": {
            "state_isolation": (extra or {}).get("state_isolation", "normal_game_warm"),
            "pairing": "color_reversed_opening_pairs",
            "raw_game_telemetry": True,
        },
        "environment": {
            key: value
            for key, value in os.environ.items()
            if key.startswith(("NSCE_", "OMP_", "GOMP_", "MKL_"))
        },
        "parameters": extra or {},
    }


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def attach_frozen_targets(manifest: dict, frozen_path: Path | None) -> dict:
    """Copy pinned NSCE/Stockfish identities into an experiment manifest."""
    if frozen_path is None or not frozen_path.exists():
        return manifest
    frozen = json.loads(frozen_path.read_text())
    targets = frozen.get("targets")
    if targets:
        manifest["targets"] = targets
        manifest["parameters"] = dict(manifest.get("parameters") or {})
        manifest["parameters"]["frozen_targets"] = str(frozen_path.resolve())
    return manifest
