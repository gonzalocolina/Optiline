#!/usr/bin/env python3
"""Sparse NumPy trainer for NSCE's two-perspective king-bucket net."""

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

HIDDEN = 128
PS_FEATURES = 12 * 64
KING_BUCKETS = 16
FEATURES = KING_BUCKETS * PS_FEATURES
SCALE = 64
PIECES = {piece: index for index, piece in enumerate("PNBRQKpnbrqk")}


def parse_fen(fen: str) -> tuple[list[tuple[int, int]], list[int], int]:
    fields = fen.split()
    pieces: list[tuple[int, int]] = []
    kings = [-1, -1]
    for fen_rank, row in enumerate(fields[0].split("/")):
        file = 0
        rank = 7 - fen_rank
        for char in row:
            if char.isdigit():
                file += int(char)
                continue
            piece = PIECES[char]
            square = rank * 8 + file
            pieces.append((piece, square))
            if piece == 5:
                kings[0] = square
            elif piece == 11:
                kings[1] = square
            file += 1
    if kings[0] < 0 or kings[1] < 0:
        raise ValueError(f"FEN lacks a king: {fen}")
    return pieces, kings, 0 if fields[1] == "w" else 1


def king_bucket(perspective: int, king: int) -> int:
    oriented = king if perspective == 0 else king ^ 56
    return (oriented // 8 // 2) * 4 + (oriented % 8) // 2


def active_features(fen: str) -> tuple[np.ndarray, np.ndarray, int]:
    pieces, kings, stm = parse_fen(fen)
    result = []
    for perspective in (0, 1):
        bucket = king_bucket(perspective, kings[perspective])
        features = []
        for piece, square in pieces:
            if perspective == 1:
                square ^= 56
                piece = piece + 6 if piece < 6 else piece - 6
            features.append(bucket * PS_FEATURES + piece * 64 + square)
        result.append(np.asarray(features, dtype=np.int32))
    return result[0], result[1], stm


def load_dataset(path: Path, target_clip: float) -> tuple[list[tuple[np.ndarray, np.ndarray, int, float, str]], str]:
    raw = path.read_bytes()
    unique: dict[str, tuple[np.ndarray, np.ndarray, int, float, str]] = {}
    for line in raw.decode().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("score_cp") is None:
            continue
        fen = record["fen"]
        white, black, stm = active_features(fen)
        score = float(np.clip(record["score_cp"], -target_clip, target_clip))
        if record.get("score_pov", "side_to_move") == "white" and stm == 1:
            score = -score
        key = " ".join(fen.split()[:4])
        unique[key] = (white, black, stm, score, fen)
    return list(unique.values()), hashlib.sha256(raw).hexdigest()


def prediction_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction - target
    return {
        "mae_cp": float(np.mean(np.abs(error))),
        "rmse_cp": float(np.sqrt(np.mean(error * error))),
    }


def forward(
    rows: list[tuple[np.ndarray, np.ndarray, int, float, str]],
    w0: np.ndarray,
    b0: np.ndarray,
    w1: np.ndarray,
    b1: float,
) -> tuple[np.ndarray, list[tuple[np.ndarray, np.ndarray]]]:
    predictions = np.empty(len(rows), dtype=np.float32)
    caches = []
    for index, (white, black, stm, _target, _fen) in enumerate(rows):
        accumulators = (b0 + w0[white].sum(axis=0), b0 + w0[black].sum(axis=0))
        own = np.clip(accumulators[stm], 0.0, 127.0)
        opponent = np.clip(accumulators[1 - stm], 0.0, 127.0)
        predictions[index] = own @ w1[:HIDDEN] + opponent @ w1[HIDDEN:] + b1
        caches.append(accumulators)
    return predictions, caches


def train(
    train_rows: list[tuple[np.ndarray, np.ndarray, int, float, str]],
    validation_rows: list[tuple[np.ndarray, np.ndarray, int, float, str]],
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, list[dict[str, float]]]:
    rng = np.random.default_rng(seed)
    w0 = rng.normal(0.0, 0.025, (FEATURES, HIDDEN)).astype(np.float32)
    b0 = np.full(HIDDEN, 0.25, dtype=np.float32)
    w1 = rng.normal(0.0, 0.04, 2 * HIDDEN).astype(np.float32)
    b1 = 0.0
    momentum_w0 = np.zeros_like(w0)
    momentum_b0 = np.zeros_like(b0)
    momentum_w1 = np.zeros_like(w1)
    momentum_b1 = 0.0
    history = []
    best_rmse = float("inf")
    best = (w0.copy(), b0.copy(), w1.copy(), b1)

    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(train_rows))
        for start in range(0, len(order), batch_size):
            batch = [train_rows[i] for i in order[start : start + batch_size]]
            prediction, caches = forward(batch, w0, b0, w1, b1)
            target = np.asarray([row[3] for row in batch], dtype=np.float32)
            error = prediction - target
            grad_prediction = np.where(np.abs(error) <= 200.0, error, 200.0 * np.sign(error))
            grad_prediction /= len(batch)
            grad_w0 = np.zeros_like(w0)
            grad_b0 = np.zeros_like(b0)
            grad_w1 = np.zeros_like(w1)
            grad_b1 = float(np.sum(grad_prediction))

            for row, accumulator, grad in zip(batch, caches, grad_prediction):
                white, black, stm, _target, _fen = row
                own_acc, opponent_acc = accumulator[stm], accumulator[1 - stm]
                own = np.clip(own_acc, 0.0, 127.0)
                opponent = np.clip(opponent_acc, 0.0, 127.0)
                grad_w1[:HIDDEN] += grad * own
                grad_w1[HIDDEN:] += grad * opponent
                grad_own = grad * w1[:HIDDEN] * ((own_acc > 0.0) & (own_acc < 127.0))
                grad_opponent = grad * w1[HIDDEN:] * ((opponent_acc > 0.0) & (opponent_acc < 127.0))
                features = (white, black)
                np.add.at(grad_w0, features[stm], grad_own)
                np.add.at(grad_w0, features[1 - stm], grad_opponent)
                grad_b0 += grad_own + grad_opponent

            momentum_w0 = 0.9 * momentum_w0 + grad_w0
            momentum_b0 = 0.9 * momentum_b0 + grad_b0
            momentum_w1 = 0.9 * momentum_w1 + grad_w1
            momentum_b1 = 0.9 * momentum_b1 + grad_b1
            w0 -= learning_rate * momentum_w0
            b0 -= learning_rate * momentum_b0
            w1 -= learning_rate * momentum_w1
            b1 -= learning_rate * momentum_b1

        validation_prediction, _ = forward(validation_rows, w0, b0, w1, b1)
        validation_target = np.asarray([row[3] for row in validation_rows], dtype=np.float32)
        row = {"epoch": epoch, **prediction_metrics(validation_prediction, validation_target)}
        history.append(row)
        print(json.dumps(row, sort_keys=True))
        if row["rmse_cp"] < best_rmse:
            best_rmse = row["rmse_cp"]
            best = (w0.copy(), b0.copy(), w1.copy(), b1)
    return *best, history


def export_network(path: Path, w0: np.ndarray, b0: np.ndarray, w1: np.ndarray, b1: float) -> dict[str, int | float]:
    w0_q = np.clip(np.rint(w0 * SCALE), -32768, 32767).astype("<i2")
    b0_q = np.clip(np.rint(b0 * SCALE), -32768, 32767).astype("<i2")
    w1_q = np.clip(np.rint(w1 * SCALE), -32768, 32767).astype("<i2")
    b1_q = int(np.clip(np.rint(b1 * SCALE * SCALE), -(2**31), 2**31 - 1))
    max_weight = int(max(np.max(np.abs(w0_q)), np.max(np.abs(b0_q)), np.max(np.abs(w1_q))))
    if max_weight >= 32767:
        raise ValueError("quantized HalfKP weights hit the int16 limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(b"NSCEHFKP")
        output.write(struct.pack("<ii", FEATURES, HIDDEN))
        output.write(w0_q.tobytes(order="C"))
        output.write(b0_q.tobytes(order="C"))
        output.write(w1_q.tobytes(order="C"))
        output.write(struct.pack("<i", b1_q))
    return {"max_abs_quantized_weight": max_weight, "size_bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="train/data/nnue_stockfish_d8.jsonl")
    parser.add_argument("--output", default="nets/halfkp_candidate.bin")
    parser.add_argument("--metrics", default="nets/halfkp_candidate.metrics.json")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.0005)
    parser.add_argument("--target-clip", type=float, default=2000.0)
    parser.add_argument("--minimum-samples", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=20260802)
    args = parser.parse_args()

    rows, dataset_sha256 = load_dataset(Path(args.data), args.target_clip)
    if len(rows) < args.minimum_samples:
        raise ValueError(f"HalfKP promotion requires at least {args.minimum_samples} samples; found {len(rows)}")
    train_rows, validation_rows = [], []
    for row in rows:
        bucket = int.from_bytes(hashlib.sha256(row[4].encode()).digest()[:4], "little") % 10
        (validation_rows if bucket == 0 else train_rows).append(row)
    w0, b0, w1, b1, history = train(
        train_rows, validation_rows, args.epochs, args.batch_size, args.learning_rate, args.seed
    )
    quantization = export_network(Path(args.output), w0, b0, w1, b1)
    validation_prediction, _ = forward(validation_rows, w0, b0, w1, b1)
    report = {
        "architecture": "halfkp-16-buckets-12288x128x2",
        "dataset_sha256": dataset_sha256,
        "network_sha256": hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
        "samples": len(rows),
        "train_samples": len(train_rows),
        "validation_samples": len(validation_rows),
        "seed": args.seed,
        "history": history,
        "float_validation": prediction_metrics(
            validation_prediction, np.asarray([row[3] for row in validation_rows], dtype=np.float32)
        ),
        "quantization": quantization,
    }
    metrics = Path(args.metrics)
    metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output} and {args.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
