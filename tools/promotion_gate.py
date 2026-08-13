#!/usr/bin/env python3
"""Validate the immutable evidence required before promoting a candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from experiment_common import sha256_file  # noqa: E402


def check_artifact(path_text: str | None, expected: str | None, label: str) -> list[str]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.exists():
        return [f"{label} is missing: {path}"]
    if expected and sha256_file(path) != expected:
        return [f"{label} hash changed: {path}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sprt", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--min-games", type=int, default=40)
    args = parser.parse_args()

    result = json.loads(args.sprt.read_text())
    manifest = json.loads(args.manifest.read_text())
    errors: list[str] = []
    if manifest.get("schema_version") != 2:
        errors.append("manifest schema_version must be 2")
    if result.get("decision") != "accept_H1_candidate_stronger":
        errors.append(f"SPRT decision is not promotion-positive: {result.get('decision')}")
    games = int(result.get("W", 0)) + int(result.get("D", 0)) + int(result.get("L", 0))
    if games < args.min_games or games % 2:
        errors.append(f"SPRT has {games} games; need an even count >= {args.min_games}")
    if int(result.get("movetime_ms", 0)) < 50:
        errors.append("promotion requires movetime >= 50 ms")
    if any(int(game.get("overruns", 0)) for game in result.get("history", [])):
        errors.append("at least one game exceeded its time budget")

    artifacts = manifest.get("artifacts", {})
    errors += check_artifact(artifacts.get("engine"), artifacts.get("engine_sha256"), "engine")
    errors += check_artifact(artifacts.get("engine_b"), artifacts.get("engine_b_sha256"), "engine-b")
    for path, digest in artifacts.get("configs", {}).items():
        errors += check_artifact(path, digest, "config")
    errors += check_artifact(artifacts.get("openings"), artifacts.get("openings_sha256"), "openings")
    for path, digest in artifacts.get("referenced_files", {}).items():
        errors += check_artifact(path, digest, "referenced model")

    if errors:
        print("promotion_gate: FAIL")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"promotion_gate: PASS ({games} games, immutable artifacts verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
