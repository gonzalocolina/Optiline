"""NSCE search-scale currency: teacher cp → WDL(teacher) → NSCE search cp.

A Stockfish centipawn is not an NSCE centipawn. Training targets live in the
scale the tree prunes on. Raw teacher cp is metadata, never a search threshold.
"""

from __future__ import annotations

import math
from typing import Any

# Logistic scale of the frozen NSCE tree (cp such that P(win) = sigmoid(cp / scale)).
NSCE_SEARCH_WDL_SCALE = 400.0
TARGET_CLIP_DEFAULT = 2000.0


def cp_to_wdl(score_cp: float, scale: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(score_cp) / max(float(scale), 1e-6)))


def wdl_to_search_cp(probability: float, scale: float) -> float:
    p = min(max(float(probability), 1e-5), 1.0 - 1e-5)
    return max(float(scale), 1e-6) * math.log(p / (1.0 - p))


def white_outcome(record: dict[str, Any]) -> float | None:
    result = record.get("result", record.get("outcome"))
    if isinstance(result, str):
        if result in {"1-0", "win", "white"}:
            return 1.0
        if result in {"0-1", "loss", "black"}:
            return 0.0
        if result in {"1/2-1/2", "draw", "0.5"}:
            return 0.5
    if isinstance(result, (int, float)):
        value = float(result)
        if 0.0 <= value <= 1.0:
            return value
    return None


def to_white_cp(score_cp: float, fen: str, score_pov: str = "side_to_move") -> float:
    if score_pov == "side_to_move" and fen.split()[1] == "b":
        return -float(score_cp)
    return float(score_cp)


def training_target(
    teacher_cp_white: float,
    *,
    target_mode: str,
    teacher_wdl_scale: float,
    search_wdl_scale: float,
    extras_cp_white: float = 0.0,
    residualize_extras: bool = False,
    result_white: float | None = None,
    result_weight: float = 0.0,
    target_clip: float = TARGET_CLIP_DEFAULT,
) -> float:
    """Map a teacher note onto the NSCE search coin, then optionally peel extras.

    Order is mandatory: teacher cp → teacher WDL → (blend result) → NSCE search cp
    → subtract extras if the runtime will add them back. Residualizing before the
    currency conversion mixes Stockfish (or other) units with NSCE extras.
    """
    if target_mode == "cp":
        target = float(teacher_cp_white)
    elif target_mode == "wdl":
        probability = cp_to_wdl(teacher_cp_white, teacher_wdl_scale)
        if result_white is not None:
            weight = min(max(float(result_weight), 0.0), 1.0)
            probability = (1.0 - weight) * probability + weight * float(result_white)
        target = wdl_to_search_cp(probability, search_wdl_scale)
    else:
        raise ValueError(f"unknown target mode: {target_mode}")
    if residualize_extras:
        target -= float(extras_cp_white)
    return float(min(max(target, -target_clip), target_clip))


def teacher_family(identity: dict[str, Any] | None, command: str = "") -> str:
    name = ""
    if identity:
        name = str(identity.get("id_name") or identity.get("name") or "")
    blob = f"{name} {command}".upper()
    if "NSCE" in blob:
        return "nsce"
    if "STOCKFISH" in blob:
        return "stockfish"
    return "unknown"
