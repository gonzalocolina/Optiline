#!/usr/bin/env python3
"""Train and quantize the 768x128x1 NSCE evaluator from teacher labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("NumPy is required: python3 -m pip install numpy", file=sys.stderr)
    raise

FEATURES = 12 * 64
HIDDEN = 128
SCALE = 64
PIECES = {p: i for i, p in enumerate("PNBRQKpnbrqk")}


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


def load_dataset(path: Path, target_clip: float) -> tuple[np.ndarray, np.ndarray, list[str], str]:
    raw = path.read_bytes()
    unique: dict[str, tuple[np.ndarray, float, str]] = {}
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
        white_score = float(score)
        if record.get("score_pov", "side_to_move") == "side_to_move" and fields[1] == "b":
            white_score = -white_score
        unique[key] = (encode_fen(fen), float(np.clip(white_score, -target_clip, target_clip)), fen)
    if len(unique) < 20:
        raise ValueError(f"need at least 20 distinct labeled positions, found {len(unique)}")
    rows = list(unique.values())
    x = np.stack([row[0] for row in rows])
    y = np.asarray([row[1] for row in rows], dtype=np.float32)
    fens = [row[2] for row in rows]
    return x, y, fens, hashlib.sha256(raw).hexdigest()


def split_dataset(fens: list[str]) -> tuple[np.ndarray, np.ndarray]:
    validation = np.asarray(
        [int.from_bytes(hashlib.sha256(fen.encode()).digest()[:4], "little") % 10 == 0 for fen in fens]
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
    }


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    rng = np.random.default_rng(seed)
    w0 = rng.normal(0.0, 0.05, (FEATURES, HIDDEN)).astype(np.float32)
    b0 = np.full(HIDDEN, 0.25, dtype=np.float32)
    w1 = rng.normal(0.0, 0.05, HIDDEN).astype(np.float32)
    b1 = np.zeros(1, dtype=np.float32)
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
            z = xb @ w0 + b0
            activation = np.clip(z, 0.0, 127.0)
            prediction = activation @ w1 + b1[0]
            error = prediction - yb
            delta = 200.0
            grad_prediction = np.where(np.abs(error) <= delta, error, delta * np.sign(error))
            grad_prediction /= max(1, len(idx))

            grad_w1 = activation.T @ grad_prediction + 1e-4 * w1
            grad_b1 = np.asarray([np.sum(grad_prediction)], dtype=np.float32)
            grad_activation = grad_prediction[:, None] * w1[None, :]
            grad_z = grad_activation * ((z > 0.0) & (z < 127.0))
            grad_w0 = xb.T @ grad_z + 1e-4 * w0
            grad_b0 = np.sum(grad_z, axis=0)

            step += 1
            for parameter, gradient, m, v in zip(
                parameters, [grad_w0, grad_b0, grad_w1, grad_b1], first, second
            ):
                adam_step(parameter, gradient, m, v, step, learning_rate)

        val_pred = np.clip(x[validation_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0]
        validation_metrics = metrics(val_pred, y[validation_indices])
        if validation_metrics["rmse_cp"] < best_validation_rmse:
            best_validation_rmse = validation_metrics["rmse_cp"]
            best_parameters = [p.copy() for p in parameters]
            best_epoch = epoch

        if epoch == 1 or epoch == epochs or epoch % max(1, epochs // 10) == 0:
            train_pred = np.clip(x[train_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0]
            row = {"epoch": epoch, **{f"train_{k}": v for k, v in metrics(train_pred, y[train_indices]).items()}}
            row.update({f"validation_{k}": v for k, v in validation_metrics.items()})
            history.append(row)
            print(json.dumps(row, sort_keys=True))

    for parameter, best in zip(parameters, best_parameters):
        parameter[...] = best
    return w0, b0, w1, b1, {"history": history, "best_epoch": best_epoch}


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
    diagnostics = {
        "accumulator_abs_max": float(np.max(np.abs(accumulator))),
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
        diagnostics["accumulator_abs_max"] >= 32767
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
    args = parser.parse_args()

    x, y, fens, dataset_sha256 = load_dataset(Path(args.data), args.target_clip)
    train_indices, validation_indices = split_dataset(fens)
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
    )
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
            "augmented_train_samples": len(augmented_x),
            "validation_samples": len(validation_indices),
            "seed": args.seed,
            "epochs": args.epochs,
            "float_validation": metrics(
                np.clip(x[validation_indices] @ w0 + b0, 0.0, 127.0) @ w1 + b1[0],
                y[validation_indices],
            ),
            "quantized_validation": metrics(
                quantized_prediction[validation_indices], y[validation_indices]
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
