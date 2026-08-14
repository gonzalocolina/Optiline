#!/usr/bin/env python3
"""Train and quantize the 768x128x1 NSCE evaluator from teacher labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "train"))

from eval_scale import (  # noqa: E402
    NSCE_SEARCH_WDL_SCALE,
    teacher_family,
    to_white_cp,
    training_target,
    white_outcome,
)

try:
    import numpy as np
except ImportError:
    print("NumPy is required: python3 -m pip install numpy", file=sys.stderr)
    raise

FEATURES = 12 * 64
HIDDEN = 128
SCALE = 64
PIECES = {p: i for i, p in enumerate("PNBRQKpnbrqk")}
PIECE_VALUE = [100, 320, 330, 500, 900, 0]
# Midgame PST from engine/src/nnue.cpp (white's perspective; black uses sq ^ 56).
PST = [
    [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5, 0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5, 5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30, -30, 5, 15, 20, 20, 15, 5, -30, -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30, -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10, -10, 5, 5, 10, 10, 5, 5, -10, -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10, -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10, -5, 0, 5, 5, 5, 5, 0, -5, 0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10, -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10, 20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
]


def encode_fen(fen: str) -> np.ndarray:
    x = np.zeros(FEATURES, dtype=np.float32)
    ranks = fen.split()[0].split("/")
    if len(ranks) != 8:
        raise ValueError(f"invalid FEN: {fen}")
    for fen_rank, row in enumerate(ranks):
        file = 0
        rank = 7 - fen_rank
        for char in row:
            if char.isdigit():
                file += int(char)
            else:
                piece = PIECES[char]
                square = rank * 8 + file
                x[piece * 64 + square] = 1.0
                file += 1
        if file != 8:
            raise ValueError(f"invalid FEN rank: {fen}")
    return x


def load_dataset(
    path: Path,
    target_clip: float,
    target_mode: str = "cp",
    wdl_scale: float = NSCE_SEARCH_WDL_SCALE,
    result_weight: float = 0.0,
    residualize_extras: bool = False,
    return_groups: bool = False,
    teacher_wdl_scale: float | None = None,
    search_wdl_scale: float | None = None,
) -> tuple:
    teacher_scale = float(teacher_wdl_scale if teacher_wdl_scale is not None else wdl_scale)
    search_scale = float(search_wdl_scale if search_wdl_scale is not None else wdl_scale)
    raw = path.read_bytes()
    unique: dict[str, tuple[np.ndarray, float, str, str]] = {}
    warned_currency = False
    for line in raw.decode().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        score = record.get("score_cp")
        fen = record.get("fen", "")
        if score is None or len(fen.split()) < 2:
            continue
        fields = fen.split()
        key = " ".join(fields[:4])
        pov = record.get("score_pov", "side_to_move")
        white_score = to_white_cp(float(score), fen, pov)
        extras_score = to_white_cp(float(record.get("extras_cp") or 0.0), fen, pov)
        family = record.get("teacher_family") or teacher_family(
            record.get("teacher_identity"), str(record.get("teacher") or "")
        )
        if (
            not warned_currency
            and family == "stockfish"
            and target_mode == "wdl"
            and abs(teacher_scale - search_scale) < 1e-9
        ):
            print(
                "warning: Stockfish labels with identical teacher/search WDL scales "
                "are the currency bug; pass --teacher-wdl-scale for that teacher",
                file=sys.stderr,
                flush=True,
            )
            warned_currency = True
        target = training_target(
            white_score,
            target_mode=target_mode,
            teacher_wdl_scale=teacher_scale,
            search_wdl_scale=search_scale,
            extras_cp_white=extras_score,
            residualize_extras=residualize_extras,
            result_white=white_outcome(record),
            result_weight=result_weight,
            target_clip=target_clip,
        )
        group = str(
            record.get("source_game")
            or record.get("game_id")
            or record.get("opening")
            or record.get("source")
            or key
        )
        if group in {"self_play", "random_walk"}:
            group = f"{group}:{key}"
        unique[key] = (encode_fen(fen), float(target), fen, group)
    if len(unique) < 20:
        raise ValueError(f"need at least 20 distinct labeled positions, found {len(unique)}")
    rows = list(unique.values())
    x = np.stack([row[0] for row in rows])
    y = np.asarray([row[1] for row in rows], dtype=np.float32)
    fens = [row[2] for row in rows]
    digest = hashlib.sha256(raw).hexdigest()
    if return_groups:
        return x, y, fens, digest, [row[3] for row in rows]
    return x, y, fens, digest


def hce_internal_weights() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Float weights matching Nnue::load_default_from_hce() after dequantizing int16 / SCALE."""
    w0_q = np.zeros((FEATURES, HIDDEN), dtype=np.int32)
    for pc in range(12):
        pt = pc % 6
        black = pc >= 6
        for sq in range(64):
            pst_sq = sq ^ 56 if black else sq
            val = PIECE_VALUE[pt] + PST[pt][pst_sq]
            if black:
                val = -val
            for h in range(HIDDEN):
                num = val * SCALE
                w = num // HIDDEN if num >= 0 else -((-num) // HIDDEN)
                w += ((h * 17 + sq * 3 + pc) & 7) - 3
                w0_q[pc * 64 + sq, h] = np.clip(w, -32768, 32767)
    w0 = (w0_q.astype(np.float32) / SCALE)
    b0 = np.zeros(HIDDEN, dtype=np.float32)
    w1 = np.full(HIDDEN, float(SCALE) / SCALE, dtype=np.float32)
    b1 = np.zeros(1, dtype=np.float32)
    return w0, b0, w1, b1


def load_init_weights(source: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if source in {"internal", "hce", "<internal>"}:
        return hce_internal_weights()
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"init weights not found: {path}")
    if path.suffix == ".npz":
        packed = np.load(path)
        w0 = packed["w0"].astype(np.float32)
        b0 = packed["b0"].astype(np.float32)
        w1 = packed["w1"].astype(np.float32)
        b1 = np.asarray(packed["b1"], dtype=np.float32).reshape(1)
        if w0.shape != (FEATURES, HIDDEN) or b0.shape != (HIDDEN,) or w1.shape != (HIDDEN,):
            raise ValueError(f"unexpected npz shapes: w0={w0.shape} b0={b0.shape} w1={w1.shape}")
        return w0, b0, w1, b1
    raw = path.read_bytes()
    if raw[:8] != b"NSCENNUE":
        raise ValueError(f"init file is not NSCENNUE or npz: {path}")
    features, hidden = struct.unpack_from("<ii", raw, 8)
    if features != FEATURES or hidden != HIDDEN:
        raise ValueError(f"unexpected NSCENNUE header: features={features} hidden={hidden}")
    offset = 16
    w0_q = np.frombuffer(raw, dtype="<i2", count=FEATURES * HIDDEN, offset=offset).reshape(FEATURES, HIDDEN)
    offset += FEATURES * HIDDEN * 2
    b0_q = np.frombuffer(raw, dtype="<i2", count=HIDDEN, offset=offset)
    offset += HIDDEN * 2
    w1_q = np.frombuffer(raw, dtype="<i2", count=HIDDEN, offset=offset)
    offset += HIDDEN * 2
    (b1_q,) = struct.unpack_from("<i", raw, offset)
    return (
        w0_q.astype(np.float32) / SCALE,
        b0_q.astype(np.float32) / SCALE,
        w1_q.astype(np.float32) / SCALE,
        np.asarray([b1_q / float(SCALE * SCALE)], dtype=np.float32),
    )


def split_dataset(fens: list[str], groups: list[str] | None = None) -> tuple[np.ndarray, np.ndarray]:
    keys = groups if groups is not None else fens
    validation = np.asarray(
        [int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "little") % 10 == 0 for key in keys]
    )
    if not validation.any() or validation.all():
        validation = np.arange(len(fens)) % 10 == 0
    return np.flatnonzero(~validation), np.flatnonzero(validation)


def augment_training(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    board = x.reshape((-1, 12, 8, 8))
    mirrored = board[:, :, :, ::-1]
    color_flipped = board[:, [*range(6, 12), *range(0, 6)], ::-1, :]
    color_flipped_mirrored = color_flipped[:, :, :, ::-1]
    augmented_x = np.concatenate([board, mirrored, color_flipped, color_flipped_mirrored])
    augmented_y = np.concatenate([y, y, -y, -y])
    return augmented_x.reshape((-1, FEATURES)), augmented_y


def metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction - target
    return {
        "mae_cp": float(np.mean(np.abs(error))),
        "rmse_cp": float(np.sqrt(np.mean(error * error))),
        "sign_accuracy": float(np.mean(np.sign(prediction) == np.sign(target))),
    }


def phase_metrics(prediction: np.ndarray, target: np.ndarray, fens: list[str]) -> dict[str, dict[str, float]]:
    buckets: dict[str, list[int]] = {"endgame": [], "middlegame": [], "opening": []}
    for index, fen in enumerate(fens):
        pieces = sum(1 for char in fen.split()[0] if char.isalpha())
        bucket = "endgame" if pieces <= 10 else "middlegame" if pieces <= 20 else "opening"
        buckets[bucket].append(index)
    return {
        name: metrics(prediction[indexes], target[indexes])
        for name, indexes in buckets.items()
        if indexes
    }


def fake_quantize(values: np.ndarray, scale: float, low: float, high: float) -> np.ndarray:
    """Forward-only fake quantization used with a straight-through gradient."""
    return np.clip(np.rint(values * scale), low, high) / scale


def adam_step(
    parameter: np.ndarray,
    gradient: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    step: int,
    learning_rate: float,
) -> None:
    first *= 0.9
    first += 0.1 * gradient
    second *= 0.999
    second += 0.001 * gradient * gradient
    first_hat = first / (1.0 - 0.9**step)
    second_hat = second / (1.0 - 0.999**step)
    parameter -= learning_rate * first_hat / (np.sqrt(second_hat) + 1e-8)


def train(
    x: np.ndarray,
    y: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    init: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None,
    qat: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    rng = np.random.default_rng(seed)
    if init is None:
        w0 = rng.normal(0.0, 0.05, (FEATURES, HIDDEN)).astype(np.float32)
        b0 = np.full(HIDDEN, 0.25, dtype=np.float32)
        w1 = rng.normal(0.0, 0.05, HIDDEN).astype(np.float32)
        b1 = np.zeros(1, dtype=np.float32)
    else:
        w0, b0, w1, b1 = (p.copy() for p in init)
    parameters = [w0, b0, w1, b1]
    first = [np.zeros_like(p) for p in parameters]
    second = [np.zeros_like(p) for p in parameters]
    step = 0
    history: list[dict[str, float]] = []
    best_validation_rmse = float("inf")
    best_parameters = [p.copy() for p in parameters]
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        shuffled = rng.permutation(train_indices)
        for start in range(0, len(shuffled), batch_size):
            idx = shuffled[start : start + batch_size]
            xb, yb = x[idx], y[idx]
            if qat:
                fw0 = fake_quantize(w0, SCALE, -32768, 32767)
                fb0 = fake_quantize(b0, SCALE, -32768, 32767)
                fw1 = fake_quantize(w1, SCALE, -32768, 32767)
                fb1 = fake_quantize(b1, SCALE * SCALE, -(2**31), 2**31 - 1)
            else:
                fw0, fb0, fw1, fb1 = w0, b0, w1, b1
            z = xb @ fw0 + fb0
            activation = np.clip(z, 0.0, 127.0)
            q_activation = fake_quantize(activation, SCALE, 0, 127 * SCALE) if qat else activation
            prediction = q_activation @ fw1 + fb1[0]
            error = prediction - yb
            delta = 200.0
            grad_prediction = np.where(np.abs(error) <= delta, error, delta * np.sign(error))
            grad_prediction /= max(1, len(idx))

            grad_w1 = q_activation.T @ grad_prediction + 1e-4 * w1
            grad_b1 = np.asarray([np.sum(grad_prediction)], dtype=np.float32)
            grad_activation = grad_prediction[:, None] * fw1[None, :]
            grad_z = grad_activation * ((z > 0.0) & (z < 127.0))
            grad_w0 = xb.T @ grad_z + 1e-4 * w0
            grad_b0 = np.sum(grad_z, axis=0)

            step += 1
            for parameter, gradient, m, v in zip(
                parameters, [grad_w0, grad_b0, grad_w1, grad_b1], first, second
            ):
                adam_step(parameter, gradient, m, v, step, learning_rate)

        if qat:
            val_w0 = fake_quantize(w0, SCALE, -32768, 32767)
            val_b0 = fake_quantize(b0, SCALE, -32768, 32767)
            val_w1 = fake_quantize(w1, SCALE, -32768, 32767)
            val_b1 = fake_quantize(b1, SCALE * SCALE, -(2**31), 2**31 - 1)
            val_z = x[validation_indices] @ val_w0 + val_b0
            val_activation = fake_quantize(np.clip(val_z, 0.0, 127.0), SCALE, 0, 127 * SCALE)
            val_pred = val_activation @ val_w1 + val_b1[0]
        else:
            val_pred = np.clip(x[validation_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0]
        validation_metrics = metrics(val_pred, y[validation_indices])
        if validation_metrics["rmse_cp"] < best_validation_rmse:
            best_validation_rmse = validation_metrics["rmse_cp"]
            best_parameters = [p.copy() for p in parameters]
            best_epoch = epoch

        if epoch == 1 or epoch == epochs or epoch % max(1, epochs // 10) == 0:
            if qat:
                train_z = x[train_indices] @ val_w0 + val_b0
                train_activation = fake_quantize(np.clip(train_z, 0.0, 127.0), SCALE, 0, 127 * SCALE)
                train_pred = train_activation @ val_w1 + val_b1[0]
            else:
                train_pred = np.clip(x[train_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0]
            row = {"epoch": epoch, **{f"train_{k}": v for k, v in metrics(train_pred, y[train_indices]).items()}}
            row.update({f"validation_{k}": v for k, v in validation_metrics.items()})
            history.append(row)
            print(json.dumps(row, sort_keys=True))

    for parameter, best in zip(parameters, best_parameters):
        parameter[...] = best
    return w0, b0, w1, b1, {"history": history, "best_epoch": best_epoch}


def _sparse_variant(indices: np.ndarray, variant: int) -> np.ndarray:
    pieces = indices // 64
    squares = indices % 64
    if variant >= 2:
        pieces = np.where(pieces < 6, pieces + 6, pieces - 6)
        squares = squares ^ 56
    if variant & 1:
        squares = squares ^ 7
    return pieces * 64 + squares


def _sparse_forward(
    rows: list[np.ndarray],
    w0: np.ndarray,
    b0: np.ndarray,
    w1: np.ndarray,
    b1: np.ndarray,
    qat: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if qat:
        fw0 = fake_quantize(w0, SCALE, -32768, 32767)
        fb0 = fake_quantize(b0, SCALE, -32768, 32767)
        fw1 = fake_quantize(w1, SCALE, -32768, 32767)
        fb1 = fake_quantize(b1, SCALE * SCALE, -(2**31), 2**31 - 1)
    else:
        fw0, fb0, fw1, fb1 = w0, b0, w1, b1
    accumulator = np.stack([fw0[row].sum(axis=0) + fb0 for row in rows])
    activation = np.clip(accumulator, 0.0, 127.0)
    if qat:
        activation = fake_quantize(activation, SCALE, 0, 127 * SCALE)
    prediction = activation @ fw1 + fb1[0]
    return prediction, accumulator, activation, fw1


def train_sparse(
    x: np.ndarray,
    y: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    init: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None,
    qat: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    """Train packed active-feature rows without materializing four dense augmentations."""
    rng = np.random.default_rng(seed)
    rows = [np.flatnonzero(row).astype(np.int32) for row in x]
    if init is None:
        w0 = rng.normal(0.0, 0.05, (FEATURES, HIDDEN)).astype(np.float32)
        b0 = np.full(HIDDEN, 0.25, dtype=np.float32)
        w1 = rng.normal(0.0, 0.05, HIDDEN).astype(np.float32)
        b1 = np.zeros(1, dtype=np.float32)
    else:
        w0, b0, w1, b1 = (p.copy() for p in init)
    parameters = [w0, b0, w1, b1]
    first = [np.zeros_like(p) for p in parameters]
    second = [np.zeros_like(p) for p in parameters]
    step = 0
    history: list[dict[str, float]] = []
    best_validation_rmse = float("inf")
    best_parameters = [p.copy() for p in parameters]
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        order = rng.permutation(train_indices)
        for start in range(0, len(order), batch_size):
            base = order[start : start + batch_size]
            batch_rows = [_sparse_variant(rows[index], variant) for variant in range(4) for index in base]
            batch_y = np.concatenate([y[base], y[base], -y[base], -y[base]])
            prediction, accumulator, activation, forward_w1 = _sparse_forward(
                batch_rows, w0, b0, w1, b1, qat
            )
            error = prediction - batch_y
            grad_prediction = np.where(np.abs(error) <= 200.0, error, 200.0 * np.sign(error))
            grad_prediction /= max(1, len(batch_rows))
            grad_w1 = activation.T @ grad_prediction + 1e-4 * w1
            grad_b1 = np.asarray([np.sum(grad_prediction)], dtype=np.float32)
            grad_acc = grad_prediction[:, None] * forward_w1[None, :]
            grad_acc *= (accumulator > 0.0) & (accumulator < 127.0)
            grad_w0 = np.zeros_like(w0)
            flat = np.concatenate(batch_rows)
            lengths = np.fromiter((len(row) for row in batch_rows), dtype=np.intp, count=len(batch_rows))
            np.add.at(grad_w0, flat, np.repeat(grad_acc, lengths, axis=0))
            grad_b0 = grad_acc.sum(axis=0)

            step += 1
            for parameter, gradient, m, v in zip(
                parameters, [grad_w0, grad_b0, grad_w1, grad_b1], first, second
            ):
                adam_step(parameter, gradient, m, v, step, learning_rate)

        val_rows = [rows[index] for index in validation_indices]
        val_pred, _val_acc, _val_activation, _ = _sparse_forward(val_rows, w0, b0, w1, b1, qat)
        validation_metrics = metrics(val_pred, y[validation_indices])
        if validation_metrics["rmse_cp"] < best_validation_rmse:
            best_validation_rmse = validation_metrics["rmse_cp"]
            best_parameters = [p.copy() for p in parameters]
            best_epoch = epoch
        if epoch == 1 or epoch == epochs or epoch % max(1, epochs // 10) == 0:
            history.append({"epoch": epoch, **{f"validation_{key}": value for key, value in validation_metrics.items()}})
            print(json.dumps(history[-1], sort_keys=True))

    for parameter, best in zip(parameters, best_parameters):
        parameter[...] = best
    return w0, b0, w1, b1, {
        "history": history,
        "best_epoch": best_epoch,
        "sparse_batches": True,
        "augmentation_materialization": False,
    }


def quantize_and_export(
    path: Path,
    x: np.ndarray,
    w0: np.ndarray,
    b0: np.ndarray,
    w1: np.ndarray,
    b1: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    w0_q = np.clip(np.rint(w0 * SCALE), -32768, 32767).astype("<i2")
    b0_q = np.clip(np.rint(b0 * SCALE), -32768, 32767).astype("<i2")
    w1_q = np.clip(np.rint(w1 * SCALE), -32768, 32767).astype("<i2")
    b1_q = int(np.clip(np.rint(b1[0] * SCALE * SCALE), -(2**31), 2**31 - 1))

    accumulator = x.astype(np.int32) @ w0_q.astype(np.int32) + b0_q.astype(np.int32)
    activation = np.clip(accumulator, 0, 127 * SCALE)
    products = activation.astype(np.int64) * w1_q.astype(np.int64)
    affine = products.sum(axis=1) + b1_q
    prediction = affine / float(SCALE * SCALE)
    affine_abs_bound = np.abs(products).sum(axis=1) + abs(b1_q)
    max_piece_counts = (8, 2, 2, 2, 1, 1)
    conservative_acc_bound = np.abs(b0_q).astype(np.int64)
    for piece in range(12):
        per_hidden_max = np.max(
            np.abs(w0_q[piece * 64 : (piece + 1) * 64]).astype(np.int64), axis=0
        )
        conservative_acc_bound += max_piece_counts[piece % 6] * per_hidden_max
    diagnostics = {
        "accumulator_abs_max": float(np.max(np.abs(accumulator))),
        "conservative_accumulator_abs_bound": int(np.max(conservative_acc_bound)),
        "activation_saturation_fraction": float(np.mean(accumulator >= 127 * SCALE)),
        "affine_abs_bound_max": int(np.max(affine_abs_bound)),
        "affine_sum_abs_max": int(np.max(np.abs(affine))),
        "weight_clip_count": int(
            np.sum(np.abs(np.rint(w0 * SCALE)) > 32767)
            + np.sum(np.abs(np.rint(b0 * SCALE)) > 32767)
            + np.sum(np.abs(np.rint(w1 * SCALE)) > 32767)
        ),
    }
    if (
        diagnostics["conservative_accumulator_abs_bound"] >= 32767
        or diagnostics["affine_abs_bound_max"] >= 2**31
        or diagnostics["weight_clip_count"]
    ):
        raise ValueError(f"unsafe int16 quantization: {diagnostics}")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(b"NSCENNUE")
        output.write(struct.pack("<ii", FEATURES, HIDDEN))
        output.write(w0_q.tobytes(order="C"))
        output.write(b0_q.tobytes(order="C"))
        output.write(w1_q.tobytes(order="C"))
        output.write(struct.pack("<i", b1_q))
    return prediction, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="train/data/distill.jsonl")
    parser.add_argument("--output", default="nets/nnue_trained.bin")
    parser.add_argument("--checkpoint", default="train/checkpoints/nnue_trained.npz")
    parser.add_argument("--metrics", default="nets/nnue_trained.metrics.json")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--target-clip", type=float, default=2000.0)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--target-mode", choices=("cp", "wdl"), default="wdl")
    parser.add_argument(
        "--wdl-scale",
        type=float,
        default=NSCE_SEARCH_WDL_SCALE,
        help="legacy alias: sets both teacher and NSCE search scales when those flags are omitted",
    )
    parser.add_argument(
        "--teacher-wdl-scale",
        type=float,
        default=None,
        help="logistic scale of the teacher that produced score_cp (Stockfish ≠ NSCE)",
    )
    parser.add_argument(
        "--search-wdl-scale",
        type=float,
        default=None,
        help="NSCE search-coin scale used by pruning; default is the frozen-tree scale",
    )
    parser.add_argument("--result-weight", type=float, default=0.0)
    parser.add_argument(
        "--residualize-extras",
        action="store_true",
        help="learn target − extras because C++ will add extras() on this 768 net",
    )
    parser.add_argument("--no-qat", action="store_true", help="disable fake integer forward during training")
    parser.add_argument("--dense-legacy", action="store_true", help="use the pre-pipeline dense augmentation path")
    parser.add_argument(
        "--init",
        default="",
        help="optional start weights: 'internal' (HCE default), .npz checkpoint, or NSCENNUE .bin",
    )
    args = parser.parse_args()

    if not 0.0 <= args.result_weight <= 1.0:
        parser.error("--result-weight must be in [0, 1]")
    teacher_wdl_scale = args.teacher_wdl_scale if args.teacher_wdl_scale is not None else args.wdl_scale
    search_wdl_scale = args.search_wdl_scale if args.search_wdl_scale is not None else args.wdl_scale
    x, y, fens, dataset_sha256, groups = load_dataset(
        Path(args.data),
        args.target_clip,
        args.target_mode,
        args.wdl_scale,
        args.result_weight,
        args.residualize_extras,
        return_groups=True,
        teacher_wdl_scale=teacher_wdl_scale,
        search_wdl_scale=search_wdl_scale,
    )
    train_indices, validation_indices = split_dataset(fens, groups)
    init_weights = load_init_weights(args.init) if args.init else None
    if args.init:
        print(f"init from {args.init}", flush=True)
    if args.dense_legacy:
        augmented_x, augmented_y = augment_training(x[train_indices], y[train_indices])
        combined_x = np.concatenate([augmented_x, x[validation_indices]])
        combined_y = np.concatenate([augmented_y, y[validation_indices]])
        combined_train_indices = np.arange(len(augmented_x))
        combined_validation_indices = np.arange(len(augmented_x), len(combined_x))
        w0, b0, w1, b1, report = train(
            combined_x,
            combined_y,
            combined_train_indices,
            combined_validation_indices,
            args.epochs,
            args.batch_size,
            args.learning_rate,
            args.seed,
            init=init_weights,
            qat=not args.no_qat,
        )
        logical_augmented_samples = len(augmented_x)
    else:
        w0, b0, w1, b1, report = train_sparse(
            x,
            y,
            train_indices,
            validation_indices,
            args.epochs,
            args.batch_size,
            args.learning_rate,
            args.seed,
            init=init_weights,
            qat=not args.no_qat,
        )
        logical_augmented_samples = len(train_indices) * 4
    quantized_prediction, diagnostics = quantize_and_export(Path(args.output), x, w0, b0, w1, b1)

    checkpoint = Path(args.checkpoint)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(checkpoint, w0=w0, b0=b0, w1=w1, b1=b1)
    report.update(
        {
            "architecture": [FEATURES, HIDDEN, 1],
            "dataset": str(args.data),
            "dataset_sha256": dataset_sha256,
            "samples": len(x),
            "train_samples": len(train_indices),
            "augmented_train_samples": logical_augmented_samples,
            "sparse_batches": not args.dense_legacy,
            "augmentation_materialization": args.dense_legacy,
            "validation_samples": len(validation_indices),
            "validation_groups": len({groups[index] for index in validation_indices}),
            "groups": len(set(groups)),
            "seed": args.seed,
            "epochs": args.epochs,
            "init": args.init or None,
            "target_mode": args.target_mode,
            "wdl_scale": args.wdl_scale,
            "teacher_wdl_scale": teacher_wdl_scale,
            "search_wdl_scale": search_wdl_scale,
            "result_weight": args.result_weight,
            "residualize_extras": args.residualize_extras,
            "qat": not args.no_qat,
            "float_validation": metrics(
                np.clip(x[validation_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0],
                y[validation_indices],
            ),
            "float_validation_phase": phase_metrics(
                np.clip(x[validation_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0],
                y[validation_indices],
                [fens[index] for index in validation_indices],
            ),
            "quantized_validation": metrics(
                quantized_prediction[validation_indices], y[validation_indices]
            ),
            "quantized_validation_phase": phase_metrics(
                quantized_prediction[validation_indices],
                y[validation_indices],
                [fens[index] for index in validation_indices],
            ),
            "quantization": diagnostics,
            "network_sha256": hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
        }
    )
    metrics_path = Path(args.metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output}, {args.checkpoint}, and {args.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
