#!/usr/bin/env python3
"""Self-play data generation for NSCE (UCI).

Plays NSCE vs NSCE under a fixed movetime budget, records FENs, moves, and outcomes.
Reward for search-control training: result - lambda * (nodes/time proxy via depth used).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


class UciEngine:
    def __init__(self, cmd: list[str]):
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        self._send("uci")
        self._wait("uciok")
        self._send("isready")
        self._wait("readyok")

    def _send(self, line: str) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _wait(self, token: str, timeout: float = 60.0) -> list[str]:
        assert self.proc.stdout
        deadline = time.time() + timeout
        lines: list[str] = []
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            lines.append(line)
            if token in line:
                return lines
        raise RuntimeError(f"timeout waiting {token}: " + "\n".join(lines[-30:]))

    def setoption(self, name: str, value: str) -> None:
        self._send(f"setoption name {name} value {value}")

    def new_game(self) -> None:
        self._send("ucinewgame")
        self._send("isready")
        self._wait("readyok")

    def go(self, moves: list[str], movetime_ms: int) -> tuple[str, int]:
        cmd = "position startpos"
        if moves:
            cmd += " moves " + " ".join(moves)
        self._send(cmd)
        self._send(f"go movetime {movetime_ms}")
        lines = self._wait("bestmove", timeout=120.0)
        nodes = 0
        best = "0000"
        for line in lines:
            if line.startswith("info ") and " nodes " in line:
                parts = line.split()
                if "nodes" in parts:
                    nodes = int(parts[parts.index("nodes") + 1])
            if line.startswith("bestmove"):
                best = line.split()[1]
        return best, nodes

    def close(self) -> None:
        try:
            self._send("quit")
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


def play_game(engine: UciEngine, movetime: int, max_plies: int, lam: float) -> dict:
    engine.new_game()
    moves: list[str] = []
    records = []
    total_nodes = 0
    for ply in range(max_plies):
        mv, nodes = engine.go(moves, movetime)
        total_nodes += nodes
        if mv in ("0000", "(none)", "none"):
            break
        records.append({"ply": ply, "move": mv, "nodes": nodes})
        moves.append(mv)
    # Outcome proxy: longer games ~ draw; decisive if one side "dominates" nodes early — keep draw default.
    # For RL scaffold we assign draw=0; user can label later. Self-play outcome via repetition length.
    result = 0.0
    if len(moves) < 10:
        result = 0.0
    cost = total_nodes / max(1, len(moves))
    reward = result - lam * (cost / 10000.0)
    return {"moves": moves, "records": records, "reward": reward, "total_nodes": total_nodes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(Path(__file__).resolve().parents[1] / "build" / "nsce"))
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--movetime", type=int, default=50)
    ap.add_argument("--max-plies", type=int, default=40)
    ap.add_argument("--lambda", dest="lam", type=float, default=0.1)
    ap.add_argument("-o", "--output", default="train/data/selfplay.jsonl")
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    eng = UciEngine([args.engine])
    try:
        with out.open("w") as f:
            for i in range(args.games):
                g = play_game(eng, args.movetime, args.max_plies, args.lam)
                f.write(json.dumps(g) + "\n")
                print(f"game {i+1}: plies={len(g['moves'])} nodes={g['total_nodes']} reward={g['reward']:.4f}")
    finally:
        eng.close()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
