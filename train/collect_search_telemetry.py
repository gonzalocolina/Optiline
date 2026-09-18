#!/usr/bin/env python3
"""Collect classical-LMR telemetry (controller off) for fit_controller.py."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from eval_contract import parse_uci_options  # noqa: E402
from uci_common import UciEngine, load_openings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    parser.add_argument("--openings", default=str(ROOT / "tools" / "openings_balanced.epd"))
    parser.add_argument("--config", default=str(ROOT / "tools/configs/baseline.uci"))
    parser.add_argument("--telemetry", default=str(ROOT / "train" / "data" / "lmr_telemetry.csv"))
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--limit", type=int, default=64)
    args = parser.parse_args()

    telemetry = Path(args.telemetry)
    telemetry.parent.mkdir(parents=True, exist_ok=True)
    if telemetry.exists():
        telemetry.unlink()

    openings = load_openings(Path(args.openings))[: max(1, args.limit)]
    engine = UciEngine([str(args.engine)], "NSCE")
    try:
        options = parse_uci_options(Path(args.config))
        options["UsePolicy"] = "false"
        options["UseSearchController"] = "false"
        options["TelemetryFile"] = str(telemetry)
        engine.apply_options(options)
        for index, fen in enumerate(openings):
            engine.new_game()
            engine.go_depth(fen, [], args.depth)
            print(f"telemetry position {index + 1}/{len(openings)}", flush=True)
    finally:
        engine.close()

    rows = telemetry.read_text().count("\n") if telemetry.exists() else 0
    print(f"wrote {rows} LMR events to {telemetry}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
