#!/usr/bin/env python3
"""Self-play with real game outcomes (checkmate / stalemate / draw / adjudication).

Reward: result_from_white - lambda * (mean_nodes / scale), under fixed movetime.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402


def play_game(engine: UciEngine, fen: str, movetime: int, max_plies: int, lam: float) -> dict:
    engine.new_game()
    moves: list[str] = []
    records = []
    total_nodes = 0
    result = "1/2-1/2"
    for ply in range(max_plies):
        mv = engine.go_movetime(fen, moves, movetime)
        total_nodes += engine.last_nodes
        if mv in ("0000", "(none)", "none"):
            break
        records.append({"ply": ply, "move": mv, "fen": engine.current_fen(fen, moves), "nodes": engine.last_nodes})
        moves.append(mv)
        st = engine.status(fen, moves)
        if st == "checkmate":
            result = "1-0" if ply % 2 == 0 else "0-1"
            break
        if st in ("stalemate", "draw"):
            result = "1/2-1/2"
            break
    score_white = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[result]
    mean_nodes = total_nodes / max(1, len(moves))
    reward = score_white - lam * (mean_nodes / 10000.0)
    return {
        "fen": fen,
        "moves": moves,
        "records": records,
        "result": result,
        "score_white": score_white,
        "reward": reward,
        "total_nodes": total_nodes,
        "mean_nodes": mean_nodes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--movetime", type=int, default=50)
    ap.add_argument("--max-plies", type=int, default=60)
    ap.add_argument("--lambda", dest="lam", type=float, default=0.1)
    ap.add_argument("--config", default=str(ROOT / "tools/configs/baseline.uci"))
    ap.add_argument("-o", "--output", default=str(ROOT / "train/data/selfplay.jsonl"))
    ap.add_argument(
        "--positions-out",
        default="",
        help="optional JSONL of (fen, result) for eval training; not random walks",
    )
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    openings = load_openings(ROOT / "tools" / "openings_balanced.epd")
    eng = UciEngine([args.engine], "NSCE")
    eng.apply_uci_file(Path(args.config))
    positions_path = Path(args.positions_out) if args.positions_out else None
    if positions_path is not None:
        positions_path.parent.mkdir(parents=True, exist_ok=True)
        positions_handle = positions_path.open("w", encoding="utf-8")
    else:
        positions_handle = None
    try:
        with out.open("w") as f:
            for i in range(args.games):
                fen = openings[i % len(openings)]
                g = play_game(eng, fen, args.movetime, args.max_plies, args.lam)
                f.write(json.dumps(g) + "\n")
                print(f"game {i+1}: result={g['result']} plies={len(g['moves'])} reward={g['reward']:.4f}")
                if positions_handle is not None:
                    positions_handle.write(
                        json.dumps(
                            {
                                "fen": fen,
                                "result": g["result"],
                                "source_game": f"selfplay:{i}",
                                "ply": 0,
                                "phase": "opening",
                            }
                        )
                        + "\n"
                    )
                    for rec in g["records"]:
                        rec_fen = rec.get("fen")
                        if not rec_fen:
                            continue
                        positions_handle.write(
                            json.dumps(
                                {
                                    "fen": rec_fen,
                                    "result": g["result"],
                                    "source_game": f"selfplay:{i}",
                                    "ply": rec.get("ply"),
                                }
                            )
                            + "\n"
                        )
    finally:
        eng.close()
        if positions_handle is not None:
            positions_handle.close()
    print(f"wrote {out}")
    if positions_path is not None:
        print(f"wrote {positions_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
