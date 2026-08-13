#!/usr/bin/env python3
"""Train NSCE-KAT: HalfKA-hm (32 buckets) + factorized PS + 12-dim threat residual.

Train-time factorization (piece-square weights shared across king buckets) is
folded into the sparse table at export, so the C++ runtime stays a single
NSCEKAT1 affine. Threat counts are dense and recomputed from attacks.
"""

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
KING_BUCKETS = 32
FEATURES = KING_BUCKETS * PS_FEATURES
THREAT_DIM = 12
SCALE = 64
PIECES = {piece: index for index, piece in enumerate("PNBRQKpnbrqk")}
KNIGHT_DELTA = (17, 15, 10, 6, -6, -10, -15, -17)
KING_DELTA = (1, -1, 8, -8, 9, 7, -7, -9)
BISHOP_DELTA = (9, 7, -7, -9)
ROOK_DELTA = (1, -1, 8, -8)


def _file(square: int) -> int:
    return square & 7


def _rank(square: int) -> int:
    return square >> 3


def _step_ok(origin: int, dest: int, delta: int) -> bool:
    if dest < 0 or dest > 63:
        return False
    df = abs(_file(dest) - _file(origin))
    dr = abs(_rank(dest) - _rank(origin))
    if delta in (1, -1):
        return dr == 0 and df == 1
    if delta in (8, -8):
        return df == 0 and dr == 1
    if delta in (9, 7, -7, -9):
        return df == 1 and dr == 1
    return False


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


def kat_king_bucket(perspective: int, king: int) -> tuple[int, int]:
    oriented = king if perspective == 0 else king ^ 56
    mirror = 0
    if _file(oriented) < 4:
        mirror = 7
        oriented ^= 7
    return _rank(oriented) * 4 + (_file(oriented) - 4), mirror


def ray_attacks(origin: int, occupied: int, deltas: tuple[int, ...]) -> int:
    attacks = 0
    for delta in deltas:
        square = origin
        while True:
            dest = square + delta
            if not _step_ok(square, dest, delta):
                break
            attacks |= 1 << dest
            if occupied & (1 << dest):
                break
            square = dest
    return attacks


def color_attacks(pieces: list[tuple[int, int]], color: int, occupied: int) -> int:
    attacks = 0
    for piece, square in pieces:
        if piece // 6 != color:
            continue
        ptype = piece % 6
        if ptype == 0:
            if color == 0:
                for dest in (square + 7, square + 9):
                    if 0 <= dest < 64 and abs(_file(dest) - _file(square)) == 1:
                        attacks |= 1 << dest
            else:
                for dest in (square - 7, square - 9):
                    if 0 <= dest < 64 and abs(_file(dest) - _file(square)) == 1:
                        attacks |= 1 << dest
        elif ptype == 1:
            for delta in KNIGHT_DELTA:
                dest = square + delta
                if 0 <= dest < 64 and {abs(_file(dest) - _file(square)), abs(_rank(dest) - _rank(square))} == {1, 2}:
                    attacks |= 1 << dest
        elif ptype == 2:
            attacks |= ray_attacks(square, occupied, BISHOP_DELTA)
        elif ptype == 3:
            attacks |= ray_attacks(square, occupied, ROOK_DELTA)
        elif ptype == 4:
            attacks |= ray_attacks(square, occupied, BISHOP_DELTA) | ray_attacks(square, occupied, ROOK_DELTA)
        else:
            for delta in KING_DELTA:
                dest = square + delta
                if _step_ok(square, dest, delta):
                    attacks |= 1 << dest
    return attacks


def threat_vector(pieces: list[tuple[int, int]], stm: int) -> np.ndarray:
    occupied = 0
    by_type = [[0] * 6 for _ in range(2)]
    for piece, square in pieces:
        occupied |= 1 << square
        by_type[piece // 6][piece % 6] |= 1 << square
    our = color_attacks(pieces, stm, occupied)
    their = color_attacks(pieces, 1 - stm, occupied)
    threats = np.zeros(THREAT_DIM, dtype=np.float32)
    for ptype in range(6):
        threats[ptype] = (by_type[stm][ptype] & their).bit_count()
        threats[6 + ptype] = (by_type[1 - stm][ptype] & our).bit_count()
    return threats


def active_features(fen: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    pieces, kings, stm = parse_fen(fen)
    kp: list[np.ndarray] = []
    ps: list[np.ndarray] = []
    for perspective in (0, 1):
        bucket, mirror = kat_king_bucket(perspective, kings[perspective])
        kp_idx: list[int] = []
        ps_idx: list[int] = []
        for piece, square in pieces:
            oriented_sq = square if perspective == 0 else square ^ 56
            oriented_sq ^= mirror
            oriented_pc = piece + 6 if perspective == 1 and piece < 6 else piece - 6 if perspective == 1 else piece
            ps_i = oriented_pc * 64 + oriented_sq
            kp_idx.append(bucket * PS_FEATURES + ps_i)
            ps_idx.append(ps_i)
        kp.append(np.asarray(kp_idx, dtype=np.int32))
        ps.append(np.asarray(ps_idx, dtype=np.int32))
    return kp[0], kp[1], ps[0], ps[1], threat_vector(pieces, stm), stm


def _row_from_line(line: str, target_clip: float):
    if not line.strip():
        return None
    record = json.loads(line)
    if record.get("score_cp") is None:
        return None
    fen = record["fen"]
    white_kp, black_kp, white_ps, black_ps, threats, stm = active_features(fen)
    score = float(np.clip(record["score_cp"], -target_clip, target_clip))
    if record.get("score_pov", "side_to_move") == "white" and stm == 1:
        score = -score
    key = " ".join(fen.split()[:4])
    return key, (white_kp, black_kp, white_ps, black_ps, threats, stm, score, fen)


def _parse_chunk(lines: list[str], target_clip: float):
    rows = []
    for line in lines:
        parsed = _row_from_line(line, target_clip)
        if parsed is not None:
            rows.append(parsed)
    return rows


def load_dataset(path: Path, target_clip: float, workers: int = 0):
    import os
    from concurrent.futures import ProcessPoolExecutor

    hasher = hashlib.sha256()
    chunks: list[list[str]] = []
    current: list[str] = []
    n_lines = 0
    print(f"loading {path}", flush=True)
    with path.open("rb") as handle:
        for raw in handle:
            hasher.update(raw)
            current.append(raw.decode("utf-8"))
            n_lines += 1
            if len(current) >= 4000:
                chunks.append(current)
                current = []
        if current:
            chunks.append(current)

    if workers <= 0:
        workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    unique: dict[str, tuple] = {}
    if workers == 1 or len(chunks) <= 1:
        for index, chunk in enumerate(chunks, start=1):
            for key, row in _parse_chunk(chunk, target_clip):
                unique[key] = row
            print(f"parsed chunk {index}/{len(chunks)} unique={len(unique)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_parse_chunk, chunk, target_clip) for chunk in chunks]
            for index, future in enumerate(futures, start=1):
                for key, row in future.result():
                    unique[key] = row
                print(f"parsed chunk {index}/{len(chunks)} unique={len(unique)}", flush=True)
    print(f"loaded {len(unique)} unique / {n_lines} lines", flush=True)
    return list(unique.values()), hasher.hexdigest()


def prediction_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction - target
    return {
        "mae_cp": float(np.mean(np.abs(error))),
        "rmse_cp": float(np.sqrt(np.mean(error * error))),
    }


def forward(rows, w0, w_ps, b0, w1, b1, w_threat):
    predictions = np.empty(len(rows), dtype=np.float32)
    caches = []
    for index, (white_kp, black_kp, white_ps, black_ps, threats, stm, _target, _fen) in enumerate(rows):
        white = b0 + w0[white_kp].sum(axis=0) + w_ps[white_ps].sum(axis=0)
        black = b0 + w0[black_kp].sum(axis=0) + w_ps[black_ps].sum(axis=0)
        accumulators = (white, black)
        own = np.clip(accumulators[stm], 0.0, 127.0)
        opponent = np.clip(accumulators[1 - stm], 0.0, 127.0)
        predictions[index] = own @ w1[:HIDDEN] + opponent @ w1[HIDDEN:] + b1 + threats @ w_threat
        caches.append(accumulators)
    return predictions, caches


def train(train_rows, validation_rows, epochs, batch_size, learning_rate, seed):
    rng = np.random.default_rng(seed)
    w0 = rng.normal(0.0, 0.02, (FEATURES, HIDDEN)).astype(np.float32)
    w_ps = rng.normal(0.0, 0.03, (PS_FEATURES, HIDDEN)).astype(np.float32)
    b0 = np.full(HIDDEN, 0.25, dtype=np.float32)
    w1 = rng.normal(0.0, 0.04, 2 * HIDDEN).astype(np.float32)
    b1 = 0.0
    w_threat = rng.normal(0.0, 0.15, THREAT_DIM).astype(np.float32)
    mw0 = np.zeros_like(w0)
    mps = np.zeros_like(w_ps)
    mb0 = np.zeros_like(b0)
    mw1 = np.zeros_like(w1)
    mb1 = 0.0
    mth = np.zeros_like(w_threat)
    history = []
    best_rmse = float("inf")
    best = (w0.copy(), w_ps.copy(), b0.copy(), w1.copy(), b1, w_threat.copy())

    for epoch in range(1, epochs + 1):
        print(f"epoch {epoch}/{epochs} train={len(train_rows)} val={len(validation_rows)}", flush=True)
        order = rng.permutation(len(train_rows))
        for start in range(0, len(order), batch_size):
            batch = [train_rows[i] for i in order[start : start + batch_size]]
            prediction, caches = forward(batch, w0, w_ps, b0, w1, b1, w_threat)
            target = np.asarray([row[6] for row in batch], dtype=np.float32)
            error = prediction - target
            grad_prediction = np.where(np.abs(error) <= 200.0, error, 200.0 * np.sign(error))
            grad_prediction /= len(batch)
            grad_w0 = np.zeros_like(w0)
            grad_ps = np.zeros_like(w_ps)
            grad_b0 = np.zeros_like(b0)
            grad_w1 = np.zeros_like(w1)
            grad_b1 = float(np.sum(grad_prediction))
            grad_th = np.zeros_like(w_threat)

            for row, accumulator, grad in zip(batch, caches, grad_prediction):
                white_kp, black_kp, white_ps, black_ps, threats, stm, _t, _f = row
                own_acc, opponent_acc = accumulator[stm], accumulator[1 - stm]
                own = np.clip(own_acc, 0.0, 127.0)
                opponent = np.clip(opponent_acc, 0.0, 127.0)
                grad_w1[:HIDDEN] += grad * own
                grad_w1[HIDDEN:] += grad * opponent
                grad_th += grad * threats
                grad_own = grad * w1[:HIDDEN] * ((own_acc > 0.0) & (own_acc < 127.0))
                grad_opp = grad * w1[HIDDEN:] * ((opponent_acc > 0.0) & (opponent_acc < 127.0))
                kp = (white_kp, black_kp)
                ps = (white_ps, black_ps)
                np.add.at(grad_w0, kp[stm], grad_own)
                np.add.at(grad_w0, kp[1 - stm], grad_opp)
                np.add.at(grad_ps, ps[stm], grad_own)
                np.add.at(grad_ps, ps[1 - stm], grad_opp)
                grad_b0 += grad_own + grad_opp

            mw0 = 0.9 * mw0 + grad_w0
            mps = 0.9 * mps + grad_ps
            mb0 = 0.9 * mb0 + grad_b0
            mw1 = 0.9 * mw1 + grad_w1
            mb1 = 0.9 * mb1 + grad_b1
            mth = 0.9 * mth + grad_th
            w0 -= learning_rate * mw0
            w_ps -= learning_rate * mps
            b0 -= learning_rate * mb0
            w1 -= learning_rate * mw1
            b1 -= learning_rate * mb1
            w_threat -= learning_rate * mth

        validation_prediction, _ = forward(validation_rows, w0, w_ps, b0, w1, b1, w_threat)
        validation_target = np.asarray([row[6] for row in validation_rows], dtype=np.float32)
        row = {"epoch": epoch, **prediction_metrics(validation_prediction, validation_target)}
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if row["rmse_cp"] < best_rmse:
            best_rmse = row["rmse_cp"]
            best = (w0.copy(), w_ps.copy(), b0.copy(), w1.copy(), b1, w_threat.copy())
    return *best, history


def fold_factorization(w0: np.ndarray, w_ps: np.ndarray) -> np.ndarray:
    folded = w0.copy()
    for bucket in range(KING_BUCKETS):
        start = bucket * PS_FEATURES
        folded[start : start + PS_FEATURES] += w_ps
    return folded


def export_network(path: Path, w0: np.ndarray, b0: np.ndarray, w1: np.ndarray, b1: float, w_threat: np.ndarray):
    w0_q = np.clip(np.rint(w0 * SCALE), -32768, 32767).astype("<i2")
    b0_q = np.clip(np.rint(b0 * SCALE), -32768, 32767).astype("<i2")
    w1_q = np.clip(np.rint(w1 * SCALE), -32768, 32767).astype("<i2")
    th_q = np.clip(np.rint(w_threat * SCALE), -32768, 32767).astype("<i2")
    b1_q = int(np.clip(np.rint(b1 * SCALE * SCALE), -(2**31), 2**31 - 1))
    max_weight = int(max(np.max(np.abs(w0_q)), np.max(np.abs(b0_q)), np.max(np.abs(w1_q)), np.max(np.abs(th_q))))
    if max_weight >= 32767:
        raise ValueError("quantized KAT weights hit the int16 limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(b"NSCEKAT1")
        output.write(struct.pack("<iii", FEATURES, HIDDEN, THREAT_DIM))
        output.write(w0_q.tobytes(order="C"))
        output.write(b0_q.tobytes(order="C"))
        output.write(w1_q.tobytes(order="C"))
        output.write(th_q.tobytes(order="C"))
        output.write(struct.pack("<i", b1_q))
    return {"max_abs_quantized_weight": max_weight, "size_bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="train/data/lichess_evals.jsonl")
    parser.add_argument("--output", default="nets/kat_candidate.bin")
    parser.add_argument("--metrics", default="nets/kat_candidate.metrics.json")
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.0004)
    parser.add_argument("--target-clip", type=float, default=2000.0)
    parser.add_argument("--minimum-samples", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=20260813)
    args = parser.parse_args()

    rows, dataset_sha256 = load_dataset(Path(args.data), args.target_clip)
    if len(rows) < args.minimum_samples:
        raise ValueError(f"KAT promotion requires at least {args.minimum_samples} samples; found {len(rows)}")
    print(f"split {len(rows)} samples (sha256={dataset_sha256[:12]}…)", flush=True)
    train_rows, validation_rows = [], []
    for row in rows:
        bucket = int.from_bytes(hashlib.sha256(row[7].encode()).digest()[:4], "little") % 10
        (validation_rows if bucket == 0 else train_rows).append(row)
    w0, w_ps, b0, w1, b1, w_threat, history = train(
        train_rows, validation_rows, args.epochs, args.batch_size, args.learning_rate, args.seed
    )
    folded = fold_factorization(w0, w_ps)
    quantization = export_network(Path(args.output), folded, b0, w1, b1, w_threat)
    validation_prediction, _ = forward(validation_rows, w0, w_ps, b0, w1, b1, w_threat)
    report = {
        "architecture": "kat-halfka-hm-32-factorized-plus-12-threat",
        "dataset_sha256": dataset_sha256,
        "network_sha256": hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
        "samples": len(rows),
        "train_samples": len(train_rows),
        "validation_samples": len(validation_rows),
        "seed": args.seed,
        "history": history,
        "float_validation": prediction_metrics(
            validation_prediction, np.asarray([row[6] for row in validation_rows], dtype=np.float32)
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
