#!/usr/bin/env python3
"""Stockfish 19 SFNNv16 static eval + WDL helpers.

NSCE `eval` is `eval <cp>`. SF19 prints a multi-line NNUE report. This module
parses that report and, when needed, `go depth 1` WDL. Labels only: do not load
`.nnue` weights into NSCE.
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "train"))

from eval_scale import (  # noqa: E402
    NSCE_SEARCH_WDL_SCALE,
    fit_logistic_scale,
    training_target,
    wdl_permille_to_winrate,
)
from uci_common import UciEngine  # noqa: E402

NNUE_WHITE_RE = re.compile(r"^NNUE evaluation\s+([+-]?\d+\.\d+)\s+\(white side\)")
NNUE_STM_RE = re.compile(r"^NNUE evaluation\s+([+-]?\d+)\s+\(side to move, internal units\)")
FINAL_WHITE_RE = re.compile(r"^Final evaluation\s+([+-]?\d+\.\d+)\s+\(white side\)")
FINAL_NONE_RE = re.compile(r"^Final evaluation:\s*none", re.IGNORECASE)
WDL_RE = re.compile(r"\bwdl\s+(\d+)\s+(\d+)\s+(\d+)\b")
SCORE_CP_RE = re.compile(r"\bscore\s+cp\s+(-?\d+)\b")

DEFAULT_SF19 = ROOT / "third_party" / "stockfish" / "stockfish-19"


@dataclass(frozen=True)
class SfEval:
    nnue_white_cp: int
    final_white_cp: int | None
    nnue_stm_internal: int | None
    in_check: bool


def parse_sf_eval_report(lines: list[str]) -> SfEval:
    """Parse SF19 `eval` stdout. Prefer NNUE (white side) pawn units → cp."""
    nnue_white = None
    final_white = None
    stm_internal = None
    in_check = False
    for line in lines:
        line = line.strip()
        m = NNUE_WHITE_RE.match(line)
        if m:
            nnue_white = int(round(float(m.group(1)) * 100.0))
            continue
        m = NNUE_STM_RE.match(line)
        if m:
            stm_internal = int(m.group(1))
            continue
        m = FINAL_WHITE_RE.match(line)
        if m:
            final_white = int(round(float(m.group(1)) * 100.0))
            continue
        if FINAL_NONE_RE.match(line):
            in_check = True
    if nnue_white is None:
        raise ValueError("no NNUE evaluation (white side) in Stockfish eval report:\n" + "\n".join(lines[-20:]))
    return SfEval(
        nnue_white_cp=nnue_white,
        final_white_cp=final_white,
        nnue_stm_internal=stm_internal,
        in_check=in_check,
    )


def parse_wdl_info(lines: list[str]) -> tuple[int, int, int] | None:
    for line in reversed(lines):
        m = WDL_RE.search(line)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def parse_search_cp(lines: list[str]) -> int | None:
    for line in reversed(lines):
        m = SCORE_CP_RE.search(line)
        if m:
            return int(m.group(1))
    return None


def sfnnv16_to_nsce_cp(
    teacher_cp_white: float,
    teacher_wdl_scale: float,
    search_wdl_scale: float = NSCE_SEARCH_WDL_SCALE,
) -> float:
    if abs(float(teacher_wdl_scale) - float(search_wdl_scale)) < 1e-9:
        raise ValueError(
            "Stockfish teacher WDL scale must not equal NSCE search scale 400 "
            "(currency bug). Fit the teacher scale or pass a distinct value."
        )
    return training_target(
        float(teacher_cp_white),
        target_mode="wdl",
        teacher_wdl_scale=float(teacher_wdl_scale),
        search_wdl_scale=float(search_wdl_scale),
    )


class StockfishEvalEngine:
    """UCI wrapper that drains SF19's multi-line `eval` report."""

    def __init__(self, cmd: Path | str = DEFAULT_SF19, name: str = "sf19"):
        path = Path(cmd)
        if not path.is_file():
            raise FileNotFoundError(f"Stockfish binary missing: {path}")
        self.engine = UciEngine([str(path)], name)
        self.engine.apply_options({"Hash": "16", "Threads": "1", "UCI_ShowWDL": "true"})

    def close(self) -> None:
        self.engine.close()

    def __enter__(self) -> "StockfishEvalEngine":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _drain_eval(self, timeout: float = 10.0) -> list[str]:
        assert self.engine.proc.stdout is not None
        deadline = time.time() + timeout
        lines: list[str] = []
        while time.time() < deadline:
            line = self.engine.proc.stdout.readline()
            if not line:
                break
            line = line.rstrip("\n")
            lines.append(line)
            stripped = line.strip()
            if stripped.startswith("Final evaluation") or FINAL_NONE_RE.match(stripped):
                return lines
        raise RuntimeError("timeout waiting for Stockfish Final evaluation\n" + "\n".join(lines[-30:]))

    def eval_sfnnv16(self, fen: str) -> SfEval:
        self.engine.set_position(fen, [])
        self.engine._send("eval")
        return parse_sf_eval_report(self._drain_eval())

    def depth1_wdl(self, fen: str) -> tuple[int, int, int] | None:
        self.engine.set_position(fen, [])
        self.engine._send("go depth 1")
        lines = self.engine._wait_for("bestmove", timeout=30.0)
        return parse_wdl_info(lines)


def fit_teacher_wdl_scale(engine: StockfishEvalEngine, fens: list[str]) -> float:
    """Fit logistic scale mapping SFNNv16 white cp to SF depth-1 WDL winrate."""
    cps: list[float] = []
    rates: list[float] = []
    for fen in fens:
        parts = fen.split()
        if len(parts) < 2:
            continue
        stm = parts[1]
        try:
            ev = engine.eval_sfnnv16(fen)
            wdl = engine.depth1_wdl(fen)
        except (RuntimeError, ValueError):
            continue
        if wdl is None:
            continue
        stm_rate = wdl_permille_to_winrate(*wdl)
        white_rate = stm_rate if stm == "w" else 1.0 - stm_rate
        cps.append(float(ev.nnue_white_cp))
        rates.append(white_rate)
    return fit_logistic_scale(cps, rates)
