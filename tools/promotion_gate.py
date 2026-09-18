#!/usr/bin/env python3
"""Validate the immutable evidence required before promoting a candidate.

MAE never promotes. Clone proves the train→export→C++ pipe. Eval promotion
needs a full-game fastchess SPRT H1 (or the legacy sprt.py JSON), one change,
and the extras contract of that net. Equal-node ablation JSON is telemetry
only unless the SPRT is the old 60-ply runner.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from eval_contract import (  # noqa: E402
    equal_node_clearly_winning,
    equal_node_not_losing,
    extras_contract_errors,
    one_change_errors,
    parse_uci_options,
)
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


def load_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.read_text())


def is_fastchess(payload: dict | None) -> bool:
    if not payload:
        return False
    return payload.get("harness") == "fastchess" or "fastchess_exit_code" in payload


def first_match_result(payload: dict | list | None) -> dict | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        return payload[0] if payload else None
    if "W" in payload and "games" in payload:
        return payload
    return None


def config_pair(sprt: dict | None, manifest: dict | None) -> tuple[Path | None, Path | None]:
    cfg_a = cfg_b = None
    if sprt:
        if sprt.get("cfg_a"):
            cfg_a = Path(str(sprt["cfg_a"]))
        if sprt.get("cfg_b"):
            cfg_b = Path(str(sprt["cfg_b"]))
    if manifest:
        artifacts = manifest.get("artifacts", {})
        configs = list((artifacts.get("configs") or {}).keys())
        if len(configs) >= 2:
            cfg_a = cfg_a or Path(configs[0])
            cfg_b = cfg_b or Path(configs[1])
        command = manifest.get("command") or []
        if "--cfg-a" in command:
            cfg_a = Path(command[command.index("--cfg-a") + 1])
        if "--cfg-b" in command:
            cfg_b = Path(command[command.index("--cfg-b") + 1])
    return cfg_a, cfg_b


def contract_errors(
    cfg_a: Path | None,
    cfg_b: Path | None,
    *,
    allow_search_retune: bool,
) -> list[str]:
    if cfg_a is None or cfg_b is None:
        return ["cannot resolve baseline/candidate UCI configs"]
    baseline = parse_uci_options(cfg_a)
    candidate = parse_uci_options(cfg_b)
    errors = one_change_errors(baseline, candidate, allow_search_retune=allow_search_retune)
    eval_file = candidate.get("EvalFile", baseline.get("EvalFile", "internal"))
    use_extras = candidate.get("UseExtras", baseline.get("UseExtras", "true"))
    errors.extend(extras_contract_errors(eval_file, use_extras))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sprt", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--equal-node", type=Path, help="ablation_match JSON (A=baseline, go nodes)")
    parser.add_argument("--validation", type=Path, help="validate_nnue.py JSON")
    parser.add_argument(
        "--stage",
        choices=("clone", "eval", "search"),
        default="eval",
        help="clone: reproduce arbiter and do not lose nodes; "
        "eval: full-game fastchess SPRT H1; search: retune after eval H1",
    )
    parser.add_argument("--min-games", type=int, default=40)
    parser.add_argument("--min-equal-node-games", type=int, default=200)
    args = parser.parse_args()

    errors: list[str] = []
    sprt = load_json(args.sprt) if args.sprt else None
    manifest = load_json(args.manifest) if args.manifest else None
    equal_node = first_match_result(load_json(args.equal_node)) if args.equal_node else None
    validation = load_json(args.validation) if args.validation else None

    if args.stage in {"eval", "search"} and (args.sprt is None or args.manifest is None):
        errors.append("eval/search promotion requires --sprt and --manifest")
    if args.stage == "clone" and (validation is None or equal_node is None):
        errors.append("clone gate needs --validation (C++ vs static labels) and --equal-node (must not lose)")

    if manifest is not None:
        if manifest.get("schema_version") != 2:
            errors.append("manifest schema_version must be 2")
        measurement = manifest.get("measurement", {})
        if measurement.get("pairing") != "color_reversed_opening_pairs":
            errors.append("manifest does not declare color-reversed pairing")
        if measurement.get("raw_game_telemetry") is not True:
            errors.append("manifest does not declare raw game telemetry")
        artifacts = manifest.get("artifacts", {})
        errors += check_artifact(artifacts.get("engine"), artifacts.get("engine_sha256"), "engine")
        errors += check_artifact(artifacts.get("engine_b"), artifacts.get("engine_b_sha256"), "engine-b")
        for path, digest in artifacts.get("configs", {}).items():
            errors += check_artifact(path, digest, "config")
        errors += check_artifact(artifacts.get("openings"), artifacts.get("openings_sha256"), "openings")
        for path, digest in artifacts.get("referenced_files", {}).items():
            errors += check_artifact(path, digest, "referenced model")
        for reference in manifest.get("targets", {}).get("stockfish", []):
            errors += check_artifact(reference.get("path"), reference.get("sha256"), reference.get("label", "target"))

    cfg_a, cfg_b = config_pair(sprt, manifest)
    if equal_node is not None:
        cfg_a = cfg_a or Path(str(equal_node.get("cfg_a") or ""))
        cfg_b = cfg_b or Path(str(equal_node.get("cfg_b") or ""))
    if cfg_a and cfg_b and cfg_a.exists() and cfg_b.exists():
        errors.extend(contract_errors(cfg_a, cfg_b, allow_search_retune=args.stage == "search"))
    elif args.stage == "clone" and validation is not None:
        opts = validation.get("trained_options") or {}
        errors.extend(
            extras_contract_errors(str(opts.get("EvalFile", "internal")), opts.get("UseExtras", True))
        )
    else:
        errors.append("cannot resolve baseline/candidate UCI configs for the extras/one-change contract")

    if validation is not None:
        clone_mae = float((validation.get("trained") or {}).get("mae_cp") or 1e9)
        ceiling = float((validation.get("clone") or {}).get("max_clone_mae_cp") or 15.0)
        if args.stage == "clone" and not validation.get("clone", {}).get("pass", clone_mae <= ceiling):
            errors.append(f"clone validation MAE {clone_mae:.1f} cp fails the C++ reproduction gate")
        if args.stage != "clone" and clone_mae > 400:
            errors.append(f"engine MAE {clone_mae:.1f} cp looks like a broken net; MAE still rejects wreckage")

    if equal_node is not None:
        if args.stage == "clone":
            errors.extend(equal_node_not_losing(equal_node, min_games=args.min_equal_node_games))
        elif not is_fastchess(sprt):
            errors.extend(equal_node_clearly_winning(equal_node, min_games=args.min_equal_node_games))
    elif args.stage in {"eval", "search"} and not is_fastchess(sprt):
        errors.append("legacy sprt.py promotion still needs equal-node JSON (N>=200); prefer tools/fastchess_match.py")

    if sprt is not None:
        decision = sprt.get("decision")
        if is_fastchess(sprt) and decision is None:
            mapped = sprt.get("sprt_decision")
            decision = {
                "H1": "accept_H1_candidate_stronger",
                "H0": "accept_H0_baseline_not_weaker",
            }.get(str(mapped or ""), "inconclusive")
        if decision != "accept_H1_candidate_stronger":
            errors.append(f"SPRT decision is not promotion-positive: {decision}")
        games = int(sprt.get("W", 0)) + int(sprt.get("D", 0)) + int(sprt.get("L", 0))
        if games < args.min_games or games % 2:
            errors.append(f"SPRT has {games} games; need an even count >= {args.min_games}")
        st_ms = int(sprt.get("st_ms") or sprt.get("movetime_ms") or 0)
        tc = sprt.get("tc")
        if is_fastchess(sprt):
            if int(sprt.get("nodes_per_move") or 0) > 0:
                errors.append("Elo promotion was run with go-nodes; timed full-game gate is missing")
            elif st_ms and st_ms < 50:
                errors.append("promotion requires st >= 50 ms or a real tc (e.g. 8+0.08)")
            elif not st_ms and not tc:
                errors.append("fastchess promotion JSON is missing st_ms and tc")
            pgn = sprt.get("pgn")
            if pgn and not Path(str(pgn)).exists():
                errors.append(f"fastchess PGN is missing: {pgn}")
        else:
            if st_ms < 50:
                errors.append("promotion requires movetime >= 50 ms")
            if any(int(game.get("overruns", 0)) for game in sprt.get("history", [])):
                errors.append("at least one game exceeded its time budget")
            if sprt.get("history") and any("moves" not in game for game in sprt.get("history", [])):
                errors.append("SPRT history is missing raw move telemetry")
            if int(sprt.get("nodes_per_move") or 0) > 0:
                errors.append("equal-time SPRT was run with go-nodes; timed gate is missing")
    elif args.stage in {"eval", "search"}:
        errors.append("full-game fastchess SPRT H1 is required to promote")

    if errors:
        print("promotion_gate: FAIL")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"promotion_gate: PASS (stage={args.stage})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
