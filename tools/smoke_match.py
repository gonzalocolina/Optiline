#!/usr/bin/env python3
"""Minimal UCI self-play smoke test (no Cute Chess required).

Runs NSCE vs NSCE at different depths for a few games to validate the protocol.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


class UciEngine:
    def __init__(self, cmd: list[str], name: str):
        self.name = name
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._wait_for("uciok")
        self._send("isready")
        self._wait_for("readyok")

    def _send(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _wait_for(self, token: str, timeout: float = 30.0) -> str:
        assert self.proc.stdout is not None
        deadline = time.time() + timeout
        lines: list[str] = []
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            lines.append(line)
            if token in line:
                return line
        raise RuntimeError(f"{self.name}: timeout waiting for {token}\n" + "\n".join(lines[-20:]))

    def new_game(self) -> None:
        self._send("ucinewgame")
        self._send("isready")
        self._wait_for("readyok")

    def bestmove(self, fen_or_start: str, moves: list[str], depth: int) -> str:
        if fen_or_start == "startpos":
            cmd = "position startpos"
        else:
            cmd = f"position fen {fen_or_start}"
        if moves:
            cmd += " moves " + " ".join(moves)
        self._send(cmd)
        self._send("legalmoves")
        legal_line = self._wait_for("legalmoves")
        legal = set(legal_line.split()[1:])
        self._send(f"go depth {depth}")
        line = self._wait_for("bestmove", timeout=120.0)
        parts = line.split()
        if len(parts) < 2:
            raise RuntimeError(f"bad bestmove: {line}")
        best = parts[1]
        if best not in ("0000", "(none)", "none") and best not in legal:
            raise RuntimeError(f"{self.name}: illegal bestmove {best}; legal={sorted(legal)}")
        if legal and best in ("0000", "(none)", "none"):
            raise RuntimeError(f"{self.name}: missing bestmove for non-terminal position")
        return best

    def close(self) -> None:
        try:
            self._send("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


def play_game(white: UciEngine, black: UciEngine, w_depth: int, b_depth: int, max_plies: int) -> str:
    white.new_game()
    black.new_game()
    moves: list[str] = []
    for ply in range(max_plies):
        engine = white if ply % 2 == 0 else black
        depth = w_depth if ply % 2 == 0 else b_depth
        mv = engine.bestmove("startpos", moves, depth)
        if mv in ("0000", "(none)", "none"):
            return "draw"
        moves.append(mv)
    return "draw"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(Path(__file__).resolve().parents[1] / "build" / "nsce"))
    ap.add_argument("--games", type=int, default=2)
    ap.add_argument("--depth-a", type=int, default=3)
    ap.add_argument("--depth-b", type=int, default=2)
    ap.add_argument("--max-plies", type=int, default=40)
    args = ap.parse_args()

    engine_path = Path(args.engine)
    if not engine_path.exists():
        print(f"engine not found: {engine_path}", file=sys.stderr)
        return 1

    a = UciEngine([str(engine_path)], "NSCE-A")
    b = UciEngine([str(engine_path)], "NSCE-B")
    try:
        for i in range(args.games):
            # Alternate colors by swapping depth assignment via engine roles
            if i % 2 == 0:
                result = play_game(a, b, args.depth_a, args.depth_b, args.max_plies)
                print(f"game {i+1}: A(d{args.depth_a}) vs B(d{args.depth_b}) -> {result}")
            else:
                result = play_game(b, a, args.depth_b, args.depth_a, args.max_plies)
                print(f"game {i+1}: B(d{args.depth_b}) vs A(d{args.depth_a}) -> {result}")
        print("smoke_match: OK")
        return 0
    finally:
        a.close()
        b.close()


if __name__ == "__main__":
    raise SystemExit(main())
