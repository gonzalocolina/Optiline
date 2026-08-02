#!/usr/bin/env python3
"""Shared UCI engine helper for NSCE experiments."""

from __future__ import annotations

import math
import subprocess
import time
from pathlib import Path


def elo_from_score(score: float, n: int) -> tuple[float, float]:
    """Approximate Elo diff and 95% CI from score (0..1) over n games."""
    if n <= 0:
        return 0.0, 999.0
    score = min(max(score, 1e-6), 1 - 1e-6)
    elo = 400.0 * math.log10(score / (1.0 - score))
    # binomial SE on score
    se = math.sqrt(score * (1.0 - score) / n)
    # dElo/dscore ≈ 400 / ln(10) / (s(1-s))
    deriv = 400.0 / math.log(10) / (score * (1.0 - score))
    err = 1.96 * se * abs(deriv)
    return elo, err


def load_openings(path: Path) -> list[str]:
    fens: list[str] = []
    if not path.exists():
        return ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]
    for line in path.read_text().splitlines():
        line = line.strip().rstrip(";")
        if not line:
            continue
        # EPD may have ops after fen fields; keep first 4–6 fen tokens
        parts = line.split()
        if len(parts) >= 4:
            fen = " ".join(parts[:4])
            if len(parts) >= 6 and parts[4].isdigit():
                fen = " ".join(parts[:6])
            else:
                fen += " 0 1"
            fens.append(fen)
    return fens or ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]


class UciEngine:
    def __init__(self, cmd: list[str], name: str = "engine"):
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
        self.last_nodes = 0
        self.last_time_ms = 0
        self.overruns = 0

    def _send(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _wait_for(self, token: str, timeout: float = 60.0) -> list[str]:
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
                return lines
        raise RuntimeError(f"{self.name}: timeout waiting for {token}\n" + "\n".join(lines[-30:]))

    def apply_uci_file(self, path: Path) -> None:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                self._send(line)
        self._send("isready")
        self._wait_for("readyok")

    def apply_options(self, options: dict[str, str]) -> None:
        for k, v in options.items():
            self._send(f"setoption name {k} value {v}")
        self._send("isready")
        self._wait_for("readyok")

    def new_game(self) -> None:
        self._send("ucinewgame")
        self._send("isready")
        self._wait_for("readyok")

    def set_position(self, fen: str, moves: list[str]) -> None:
        if fen == "startpos":
            cmd = "position startpos"
        else:
            cmd = f"position fen {fen}"
        if moves:
            cmd += " moves " + " ".join(moves)
        self._send(cmd)

    def go_movetime(self, fen: str, moves: list[str], movetime_ms: int) -> str:
        self.set_position(fen, moves)
        t0 = time.time()
        self._send(f"go movetime {movetime_ms}")
        lines = self._wait_for("bestmove", timeout=max(30.0, movetime_ms / 1000.0 + 30.0))
        elapsed_ms = int((time.time() - t0) * 1000)
        self.last_time_ms = elapsed_ms
        if elapsed_ms > movetime_ms * 2 + 200:
            self.overruns += 1
        self.last_nodes = 0
        best = "0000"
        for line in lines:
            if line.startswith("info ") and " nodes " in line:
                parts = line.split()
                if "nodes" in parts:
                    self.last_nodes = int(parts[parts.index("nodes") + 1])
            if line.startswith("bestmove"):
                best = line.split()[1]
        return best

    def go_depth(self, fen: str, moves: list[str], depth: int) -> str:
        self.set_position(fen, moves)
        self._send(f"go depth {depth}")
        lines = self._wait_for("bestmove", timeout=120.0)
        self.last_nodes = 0
        best = "0000"
        for line in lines:
            if line.startswith("info ") and " nodes " in line:
                parts = line.split()
                if "nodes" in parts:
                    self.last_nodes = int(parts[parts.index("nodes") + 1])
            if line.startswith("bestmove"):
                best = line.split()[1]
        return best

    def status(self, fen: str, moves: list[str]) -> str:
        self.set_position(fen, moves)
        self._send("status")
        # read one line response
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline().strip()
        return line

    def close(self) -> None:
        try:
            self._send("quit")
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()
