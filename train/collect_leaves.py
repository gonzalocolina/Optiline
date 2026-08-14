#!/usr/bin/env python3
"""Dump the positions the tree actually evaluates (QS stand-pat, static, checks).

Root FEN dumps are the wrong exam. This records LeafTelemetryFile rows from the
frozen baseline so later static labels look like search leaves.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402

DEFAULT_SITES = ("q_stand_pat", "static", "in_check_static")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    parser.add_argument("--config", default=str(ROOT / "tools/configs/baseline.uci"))
    parser.add_argument("--openings", default=str(ROOT / "tools/openings_balanced.epd"))
    parser.add_argument("--output", default=str(ROOT / "train/data/leaves.jsonl"))
    parser.add_argument("--nodes", type=int, default=25000)
    parser.add_argument("--depth", type=int, default=0, help="if >0, go depth instead of nodes")
    parser.add_argument("--limit", type=int, default=64)
    parser.add_argument(
        "--sites",
        default=",".join(DEFAULT_SITES),
        help="comma-separated LeafTelemetry sites to keep",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    telemetry = output.with_suffix(".raw.jsonl")
    if telemetry.exists():
        telemetry.unlink()

    sites = {item.strip() for item in args.sites.split(",") if item.strip()}
    openings = load_openings(Path(args.openings))[: max(1, args.limit)]
    engine = UciEngine([str(args.engine)], "NSCE")
    try:
        engine.apply_uci_file(Path(args.config))
        engine.apply_options({"LeafTelemetryFile": str(telemetry), "Threads": "1", "Hash": "16"})
        for index, fen in enumerate(openings):
            engine.new_game()
            if args.depth > 0:
                engine.go_depth(fen, [], args.depth)
            else:
                engine.go_nodes(fen, [], args.nodes)
            print(f"leaves position {index + 1}/{len(openings)}", flush=True)
    finally:
        engine.close()

    seen: set[str] = set()
    kept = 0
    with output.open("w", encoding="utf-8") as handle:
        if telemetry.exists():
            for line in telemetry.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                site = str(record.get("site") or "")
                if sites and site not in sites:
                    continue
                fen = str(record.get("fen") or "")
                key = " ".join(fen.split()[:4])
                if not key or key in seen:
                    continue
                seen.add(key)
                record["source"] = "leaf"
                handle.write(json.dumps(record) + "\n")
                kept += 1
    print(f"wrote {kept} unique leaf FENs to {output}")
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
