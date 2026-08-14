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


def elo_from_wdl(wins: int, draws: int, losses: int) -> tuple[float, float]:
    """Elo and conservative 95% interval from trinomial W/D/L outcomes."""
    n = wins + draws + losses
    if n <= 0:
        return 0.0, 999.0
    raw_score = (wins + 0.5 * draws) / n
    score = min(max(raw_score, 1e-6), 1 - 1e-6)
    elo = 400.0 * math.log10(score / (1.0 - score))

    # Jeffreys smoothing avoids a zero-width interval for all-draw or all-win samples.
    effective_n = n + 1.5
    p_win = (wins + 0.5) / effective_n
    p_draw = (draws + 0.5) / effective_n
    mean = p_win + 0.5 * p_draw
    variance = max(0.0, p_win + 0.25 * p_draw - mean * mean)
    score_error = 1.96 * math.sqrt(variance / effective_n)
    low = min(max(mean - score_error, 1e-6), 1 - 1e-6)
    high = min(max(mean + score_error, 1e-6), 1 - 1e-6)
    elo_low = 400.0 * math.log10(low / (1.0 - low))
    elo_high = 400.0 * math.log10(high / (1.0 - high))
    return elo, max(elo - elo_low, elo_high - elo)


def _parse_info_stats(line: str) -> dict[str, str]:
    """Parse `info string stats k v k a/b ...` into a string-valued dict."""
    parts = line.split()
    try:
        start = parts.index("stats") + 1
    except ValueError:
        return {}
    parsed: dict[str, str] = {}
    key: str | None = None
    for token in parts[start:]:
        if key is None:
            key = token
            continue
        parsed[key] = token
        key = None
    return parsed


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
        uci_lines = self._wait_for("uciok")
        self.identity = {
            "id_name": next((line[8:] for line in uci_lines if line.startswith("id name ")), ""),
            "id_author": next((line[10:] for line in uci_lines if line.startswith("id author ")), ""),
        }
        self._send("isready")
        self._wait_for("readyok")
        self.last_nodes = 0
        self.last_nps = 0
        self.last_depth = 0
        self.last_time_ms = 0
        self.last_score_cp = 0
        self.last_stats: dict[str, str] = {}
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

    def clear_hash(self) -> None:
        self._send("setoption name Clear Hash")
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
        t0 = time.monotonic()
        self._send(f"go movetime {movetime_ms}")
        lines = self._wait_for("bestmove", timeout=max(30.0, movetime_ms / 1000.0 + 30.0))
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        self.last_time_ms = elapsed_ms
        if elapsed_ms > movetime_ms + max(20, movetime_ms // 10):
            self.overruns += 1
        return self._parse_search(lines)

    def go_depth(self, fen: str, moves: list[str], depth: int) -> str:
        self.set_position(fen, moves)
        t0 = time.monotonic()
        self._send(f"go depth {depth}")
        lines = self._wait_for("bestmove", timeout=120.0)
        self.last_time_ms = int((time.monotonic() - t0) * 1000)
        return self._parse_search(lines)

    def go_nodes(self, fen: str, moves: list[str], nodes: int) -> str:
        self.set_position(fen, moves)
        t0 = time.monotonic()
        self._send(f"go nodes {nodes}")
        lines = self._wait_for("bestmove", timeout=max(30.0, nodes / 50_000.0 + 30.0))
        self.last_time_ms = int((time.monotonic() - t0) * 1000)
        return self._parse_search(lines)

    def _parse_search(self, lines: list[str]) -> str:
        self.last_nodes = 0
        self.last_nps = 0
        self.last_depth = 0
        self.last_score_cp = 0
        self.last_stats = {}
        best = "0000"
        for line in lines:
            if line.startswith("info string stats "):
                self.last_stats = _parse_info_stats(line)
                continue
            if line.startswith("info "):
                parts = line.split()
                if "nodes" in parts:
                    self.last_nodes = int(parts[parts.index("nodes") + 1])
                if "nps" in parts:
                    self.last_nps = int(parts[parts.index("nps") + 1])
                if "depth" in parts:
                    self.last_depth = int(parts[parts.index("depth") + 1])
                if "score" in parts:
                    score_index = parts.index("score")
                    if score_index + 2 < len(parts):
                        kind = parts[score_index + 1]
                        value = int(parts[score_index + 2])
                        if kind == "cp":
                            self.last_score_cp = value
                        elif kind == "mate":
                            self.last_score_cp = (32000 - min(abs(value), 255)) * (1 if value > 0 else -1)
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

    def legal_moves(self, fen: str, moves: list[str]) -> list[str]:
        self.set_position(fen, moves)
        self._send("legalmoves")
        assert self.proc.stdout is not None
        parts = self.proc.stdout.readline().strip().split()
        if not parts or parts[0] != "legalmoves":
            raise RuntimeError(f"{self.name}: expected legalmoves response")
        return parts[1:]

    def current_fen(self, fen: str, moves: list[str]) -> str:
        self.set_position(fen, moves)
        self._send("d")
        assert self.proc.stdout is not None
        return self.proc.stdout.readline().strip()

    def evaluate(self, fen: str, moves: list[str] | None = None) -> int:
        self.set_position(fen, moves or [])
        self._send("eval")
        assert self.proc.stdout is not None
        parts = self.proc.stdout.readline().strip().split()
        if len(parts) != 2 or parts[0] != "eval":
            raise RuntimeError(f"{self.name}: expected eval response")
        return int(parts[1])

    def evaluate_details(self, fen: str, moves: list[str] | None = None) -> dict[str, int]:
        self.set_position(fen, moves or [])
        self._send("eval details")
        assert self.proc.stdout is not None
        parts = self.proc.stdout.readline().strip().split()
        if not parts or parts[0] != "eval" or len(parts) % 2 != 1:
            raise RuntimeError(f"{self.name}: expected eval details response")
        return {
            parts[index]: int(parts[index + 1])
            for index in range(1, len(parts) - 1, 2)
            if parts[index + 1].lstrip("-").isdigit()
        }

    def close(self) -> None:
        try:
            self._send("quit")
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()
