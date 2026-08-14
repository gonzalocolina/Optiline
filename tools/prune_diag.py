#!/usr/bin/env python3
"""Fixed-depth tree-shape diagnostic: nodes, nps, and NSCE_STATS prune counters.

Compares two UCI configs on the six nsce_bench FENs at go depth N. Requires a
binary built with -DNSCE_STATS=ON so `info string stats` includes null/razor/RFP
/futility/LMP. Tree size is the gate; prune rates are diagnostic.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_common import build_manifest, write_manifest  # noqa: E402
from uci_common import UciEngine  # noqa: E402

BENCH_FENS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
    "r4rk1/1pp1qppp/p1np1n2/8/2B1P3/2N2Q1p/PPP2PPP/R1B2RK1 w - - 0 10",
]

BENCH_NAMES = [
    "startpos",
    "kiwipete",
    "endgame",
    "pos4",
    "pos5",
    "pos6",
]


def parse_ratio(value: str | None) -> tuple[int, int]:
    if not value or "/" not in value:
        return 0, 0
    left, right = value.split("/", 1)
    return int(left), int(right)


def ratio_pct(cutoffs: int, attempts: int) -> float:
    return 100.0 * cutoffs / attempts if attempts else 0.0


def search_position(engine: UciEngine, fen: str, depth: int) -> dict:
    engine.new_game()
    engine.clear_hash()
    engine.go_depth(fen, [], depth)
    null_cut, null_att = parse_ratio(engine.last_stats.get("null"))
    razor_cut, razor_att = parse_ratio(engine.last_stats.get("razor"))
    rfp_cut, rfp_att = parse_ratio(engine.last_stats.get("rfp"))
    return {
        "fen": fen,
        "nodes": engine.last_nodes,
        "nps": engine.last_nps,
        "time_ms": engine.last_time_ms,
        "depth": engine.last_depth,
        "stats": engine.last_stats,
        "null_cutoffs": null_cut,
        "null_attempts": null_att,
        "razor_cutoffs": razor_cut,
        "razor_attempts": razor_att,
        "rfp_cutoffs": rfp_cut,
        "rfp_attempts": rfp_att,
        "futility_prunes": int(engine.last_stats.get("futility", "0")),
        "lmp_prunes": int(engine.last_stats.get("lmp", "0")),
    }


def run_side(engine: UciEngine, name: str, depth: int) -> dict:
    positions = []
    for fen, label in zip(BENCH_FENS, BENCH_NAMES):
        row = search_position(engine, fen, depth)
        row["name"] = label
        positions.append(row)
    nodes = sum(row["nodes"] for row in positions)
    time_ms = sum(row["time_ms"] for row in positions)
    nps = int(nodes * 1000 / time_ms) if time_ms else nodes
    return {
        "name": name,
        "nodes": nodes,
        "time_ms": time_ms,
        "nps": nps,
        "null_cutoffs": sum(row["null_cutoffs"] for row in positions),
        "null_attempts": sum(row["null_attempts"] for row in positions),
        "razor_cutoffs": sum(row["razor_cutoffs"] for row in positions),
        "razor_attempts": sum(row["razor_attempts"] for row in positions),
        "rfp_cutoffs": sum(row["rfp_cutoffs"] for row in positions),
        "rfp_attempts": sum(row["rfp_attempts"] for row in positions),
        "futility_prunes": sum(row["futility_prunes"] for row in positions),
        "lmp_prunes": sum(row["lmp_prunes"] for row in positions),
        "positions": positions,
    }


def write_report(outdir: Path, baseline: dict, candidate: dict, depth: int) -> None:
    node_ratio = candidate["nodes"] / baseline["nodes"] if baseline["nodes"] else float("inf")
    nps_ratio = candidate["nps"] / baseline["nps"] if baseline["nps"] else float("inf")
    bushy = node_ratio > 1.2
    lines = [
        f"# Prune / tree-shape diagnostic (depth {depth})",
        "",
        f"Suite: 6 `nsce_bench` FENs. Binary must be built with `NSCE_STATS=ON`.",
        "",
        f"- Baseline `{baseline['name']}`: {baseline['nodes']} nodes, {baseline['time_ms']} ms, {baseline['nps']} nps",
        f"- Candidate `{candidate['name']}`: {candidate['nodes']} nodes, {candidate['time_ms']} ms, {candidate['nps']} nps",
        f"- Node ratio (candidate / baseline): **{node_ratio:.2f}×**",
        f"- nps ratio: {nps_ratio:.2f}×",
        "",
        "H1 of pruning: candidate nodes ≤ ~1.2× baseline (not the KAT startpos ~3×) and any nps drop smaller than the node reduction.",
        f"**Tree gate: {'FAIL (bushier)' if bushy else 'PASS (narrower or similar)'}.**",
        "",
        "| Side | nodes | nps | null cut/att | razor | rfp | futility | lmp |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for side in (baseline, candidate):
        lines.append(
            f"| {side['name']} | {side['nodes']} | {side['nps']} | "
            f"{side['null_cutoffs']}/{side['null_attempts']} "
            f"({ratio_pct(side['null_cutoffs'], side['null_attempts']):.0f}%) | "
            f"{side['razor_cutoffs']}/{side['razor_attempts']} "
            f"({ratio_pct(side['razor_cutoffs'], side['razor_attempts']):.0f}%) | "
            f"{side['rfp_cutoffs']}/{side['rfp_attempts']} "
            f"({ratio_pct(side['rfp_cutoffs'], side['rfp_attempts']):.0f}%) | "
            f"{side['futility_prunes']} | {side['lmp_prunes']} |"
        )
    lines.extend(["", "## Per position", "", "| Position | baseline nodes | candidate nodes | ratio |"])
    lines.append("| --- | ---: | ---: | ---: |")
    for bpos, cpos in zip(baseline["positions"], candidate["positions"]):
        ratio = cpos["nodes"] / bpos["nodes"] if bpos["nodes"] else float("inf")
        lines.append(f"| {bpos['name']} | {bpos['nodes']} | {cpos['nodes']} | {ratio:.2f}× |")
    (outdir / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=str(ROOT / "build-stats" / "nsce"))
    parser.add_argument("--cfg-a", default=str(ROOT / "tools/configs/baseline.uci"))
    parser.add_argument("--cfg-b", required=True)
    parser.add_argument("--name-a", default="baseline")
    parser.add_argument("--name-b", default="candidate")
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--outdir", default="")
    args = parser.parse_args()

    engine_path = Path(args.engine)
    if not engine_path.exists():
        print(f"engine not found: {engine_path} (build with -DNSCE_STATS=ON)", file=sys.stderr)
        return 1
    cfg_a = Path(args.cfg_a)
    cfg_b = Path(args.cfg_b)
    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / f"{date.today().strftime('%Y%m%d')}_prune"
    outdir.mkdir(parents=True, exist_ok=True)

    a = UciEngine([str(engine_path)], args.name_a)
    b = UciEngine([str(engine_path)], args.name_b)
    try:
        a.apply_uci_file(cfg_a)
        b.apply_uci_file(cfg_b)
        baseline = run_side(a, args.name_a, args.depth)
        candidate = run_side(b, args.name_b, args.depth)
    finally:
        a.close()
        b.close()

    payload = {
        "depth": args.depth,
        "baseline": baseline,
        "candidate": candidate,
        "node_ratio": candidate["nodes"] / baseline["nodes"] if baseline["nodes"] else None,
        "bushy": bool(baseline["nodes"] and candidate["nodes"] / baseline["nodes"] > 1.2),
    }
    (outdir / "prune_diag.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_report(outdir, baseline, candidate, args.depth)
    write_manifest(
        outdir / "manifest.json",
        build_manifest(
            ROOT,
            engine_path,
            [cfg_a, cfg_b],
            ROOT / "tools" / "openings_balanced.epd",
            args.seed,
            {
                "kind": "prune_diag",
                "depth": args.depth,
                "positions": len(BENCH_FENS),
            },
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
