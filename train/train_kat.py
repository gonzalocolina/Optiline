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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "train"))

from eval_scale import NSCE_SEARCH_WDL_SCALE, training_target, white_outcome  # noqa: E402

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
_PIECE_OF = [-1] * 128
for _char, _index in PIECES.items():
    _PIECE_OF[ord(_char)] = _index
KNIGHT_DELTA = (17, 15, 10, 6, -6, -10, -15, -17)
KING_DELTA = (1, -1, 8, -8, 9, 7, -7, -9)
BISHOP_DELTA = (9, 7, -7, -9)
ROOK_DELTA = (1, -1, 8, -8)
# N, S, E, W, NE, NW, SE, SW
_SLIDE_DELTA = (8, -8, 1, -1, 9, 7, -7, -9)
_BISHOP_DIRS = (4, 5, 6, 7)
_ROOK_DIRS = (0, 1, 2, 3)
_RAYS = [[0] * 64 for _ in range(8)]
_KNIGHT_ATT = [0] * 64
_KING_ATT = [0] * 64
_PAWN_ATT = [[0] * 64, [0] * 64]
_BUCKET_MIRROR = [0] * 64
_BUCKET_ID = [0] * 64


def _file(square: int) -> int:
    return square & 7


def _rank(square: int) -> int:
    return square >> 3


def _step_ok(origin: int, dest: int, delta: int) -> bool:
    if dest < 0 or dest > 63:
        return False
    df = abs((dest & 7) - (origin & 7))
    dr = abs((dest >> 3) - (origin >> 3))
    if delta in (1, -1):
        return dr == 0 and df == 1
    if delta in (8, -8):
        return df == 0 and dr == 1
    if delta in (9, 7, -7, -9):
        return df == 1 and dr == 1
    return False


def _init_attack_tables() -> None:
    for sq in range(64):
        oriented = sq
        mirror = 0
        if (oriented & 7) < 4:
            mirror = 7
            oriented ^= 7
        _BUCKET_MIRROR[sq] = mirror
        _BUCKET_ID[sq] = (oriented >> 3) * 4 + ((oriented & 7) - 4)
        for d, delta in enumerate(_SLIDE_DELTA):
            ray = 0
            prev, dest = sq, sq + delta
            while _step_ok(prev, dest, delta):
                ray |= 1 << dest
                prev, dest = dest, dest + delta
            _RAYS[d][sq] = ray
        knight = 0
        for delta in KNIGHT_DELTA:
            dest = sq + delta
            if 0 <= dest < 64 and {abs((dest & 7) - (sq & 7)), abs((dest >> 3) - (sq >> 3))} == {1, 2}:
                knight |= 1 << dest
        _KNIGHT_ATT[sq] = knight
        king = 0
        for delta in KING_DELTA:
            dest = sq + delta
            if _step_ok(sq, dest, delta):
                king |= 1 << dest
        _KING_ATT[sq] = king
        wp = bp = 0
        for dest in (sq + 7, sq + 9):
            if 0 <= dest < 64 and abs((dest & 7) - (sq & 7)) == 1:
                wp |= 1 << dest
        for dest in (sq - 7, sq - 9):
            if 0 <= dest < 64 and abs((dest & 7) - (sq & 7)) == 1:
                bp |= 1 << dest
        _PAWN_ATT[0][sq] = wp
        _PAWN_ATT[1][sq] = bp


_init_attack_tables()

_RANK_ATT = [[0] * 256 for _ in range(8)]
for _file_i in range(8):
    for _occ in range(256):
        _att = 0
        _x = _file_i - 1
        while _x >= 0:
            _att |= 1 << _x
            if _occ & (1 << _x):
                break
            _x -= 1
        _x = _file_i + 1
        while _x <= 7:
            _att |= 1 << _x
            if _occ & (1 << _x):
                break
            _x += 1
        _RANK_ATT[_file_i][_occ] = _att


def parse_fen(fen: str) -> tuple[list[tuple[int, int]], list[int], int]:
    raw = fen.encode("ascii")
    pieces: list[tuple[int, int]] = []
    append = pieces.append
    kings = [-1, -1]
    square = 56
    piece_of = _PIECE_OF
    i = 0
    n = len(raw)
    while i < n:
        code = raw[i]
        i += 1
        if code == 32:
            break
        if code == 47:
            square -= 16
            continue
        if 49 <= code <= 56:
            square += code - 48
            continue
        piece = piece_of[code]
        append((piece, square))
        if piece == 5:
            kings[0] = square
        elif piece == 11:
            kings[1] = square
        square += 1
    if kings[0] < 0 or kings[1] < 0:
        raise ValueError(f"FEN lacks a king: {fen}")
    stm = 0 if i < n and raw[i] == 119 else 1
    return pieces, kings, stm


def kat_king_bucket(perspective: int, king: int) -> tuple[int, int]:
    oriented = king if perspective == 0 else king ^ 56
    return _BUCKET_ID[oriented], _BUCKET_MIRROR[oriented]


def _rank_attacks(square: int, occupied: int) -> int:
    shift = square & ~7
    return _RANK_ATT[square & 7][(occupied >> shift) & 0xFF] << shift


def _slide(square: int, occupied: int, dirs: tuple[int, ...]) -> int:
    rays = _RAYS
    deltas = _SLIDE_DELTA
    if dirs is _ROOK_DIRS:
        attacks = _rank_attacks(square, occupied)
        dirs = (0, 1)
    else:
        attacks = 0
    for d in dirs:
        ray = rays[d][square]
        blockers = occupied & ray
        if blockers:
            blocker = (blockers & -blockers).bit_length() - 1 if deltas[d] > 0 else blockers.bit_length() - 1
            attacks |= ray ^ rays[d][blocker]
        else:
            attacks |= ray
    return attacks


def ray_attacks(origin: int, occupied: int, deltas: tuple[int, ...]) -> int:
    if deltas is BISHOP_DELTA or deltas == BISHOP_DELTA:
        return _slide(origin, occupied, _BISHOP_DIRS)
    if deltas is ROOK_DELTA or deltas == ROOK_DELTA:
        return _slide(origin, occupied, _ROOK_DIRS)
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
    pawn = _PAWN_ATT[color]
    knight = _KNIGHT_ATT
    king = _KING_ATT
    for piece, square in pieces:
        if piece // 6 != color:
            continue
        ptype = piece % 6
        if ptype == 0:
            attacks |= pawn[square]
        elif ptype == 1:
            attacks |= knight[square]
        elif ptype == 2:
            attacks |= _slide(square, occupied, _BISHOP_DIRS)
        elif ptype == 3:
            attacks |= _slide(square, occupied, _ROOK_DIRS)
        elif ptype == 4:
            attacks |= _slide(square, occupied, _BISHOP_DIRS) | _slide(square, occupied, _ROOK_DIRS)
        else:
            attacks |= king[square]
    return attacks


def _threat_counts(pieces: list[tuple[int, int]], stm: int) -> list[int]:
    occupied = 0
    by_type = [0] * 12
    for piece, square in pieces:
        bit = 1 << square
        occupied |= bit
        by_type[piece] |= bit
    att = [0, 0]
    pawn = _PAWN_ATT
    knight = _KNIGHT_ATT
    king = _KING_ATT
    for piece, square in pieces:
        color = piece // 6
        ptype = piece - color * 6
        if ptype == 0:
            att[color] |= pawn[color][square]
        elif ptype == 1:
            att[color] |= knight[square]
        elif ptype == 2:
            att[color] |= _slide(square, occupied, _BISHOP_DIRS)
        elif ptype == 3:
            att[color] |= _slide(square, occupied, _ROOK_DIRS)
        elif ptype == 4:
            att[color] |= _slide(square, occupied, _BISHOP_DIRS) | _slide(square, occupied, _ROOK_DIRS)
        else:
            att[color] |= king[square]
    our, their = att[stm], att[1 - stm]
    ours = stm * 6
    theirs = (1 - stm) * 6
    counts = [0] * THREAT_DIM
    for ptype in range(6):
        counts[ptype] = (by_type[ours + ptype] & their).bit_count()
        counts[6 + ptype] = (by_type[theirs + ptype] & our).bit_count()
    return counts


def threat_vector(pieces: list[tuple[int, int]], stm: int) -> np.ndarray:
    return np.asarray(_threat_counts(pieces, stm), dtype=np.float32)


def _feature_lists(fen: str):
    pieces, kings, stm = parse_fen(fen)
    white_kp: list[int] = []
    black_kp: list[int] = []
    white_ps: list[int] = []
    black_ps: list[int] = []
    wb, wm = kat_king_bucket(0, kings[0])
    bb, bm = kat_king_bucket(1, kings[1])
    wbase = wb * PS_FEATURES
    bbase = bb * PS_FEATURES
    for piece, square in pieces:
        wsq = square ^ wm
        bsq = (square ^ 56) ^ bm
        bpc = piece + 6 if piece < 6 else piece - 6
        wps = piece * 64 + wsq
        bps = bpc * 64 + bsq
        white_ps.append(wps)
        black_ps.append(bps)
        white_kp.append(wbase + wps)
        black_kp.append(bbase + bps)
    return white_kp, black_kp, white_ps, black_ps, _threat_counts(pieces, stm), stm


def active_features(fen: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    white_kp, black_kp, white_ps, black_ps, threats, stm = _feature_lists(fen)
    return (
        np.asarray(white_kp, dtype=np.int32),
        np.asarray(black_kp, dtype=np.int32),
        np.asarray(white_ps, dtype=np.int32),
        np.asarray(black_ps, dtype=np.int32),
        np.asarray(threats, dtype=np.float32),
        stm,
    )


def _row_from_line(line: str, target_clip: float):
    if not line:
        return None
    fen = None
    score = None
    pov = "side_to_move"
    record = None
    try:
        record = json.loads(line)
    except (TypeError, json.JSONDecodeError):
        pass
    try:
        start = line.index('"fen":"') + 7
        end = line.index('"', start)
        fen = line[start:end]
        start = line.index('"score_cp":', end) + 11
        n = len(line)
        while start < n and line[start] == " ":
            start += 1
        if line.startswith("null", start):
            return None
        stop = start
        if stop < n and line[stop] in "+-":
            stop += 1
        while stop < n and line[stop].isdigit():
            stop += 1
        if stop < n and line[stop] == ".":
            stop += 1
            while stop < n and line[stop].isdigit():
                stop += 1
        score = float(line[start:stop])
        marker = line.find('"score_pov":"', stop)
        if marker >= 0:
            pov_start = marker + 13
            pov = line[pov_start : line.index('"', pov_start)]
    except ValueError:
        record = json.loads(line)
        if record.get("score_cp") is None:
            return None
        fen = record["fen"]
        score = float(record["score_cp"])
        pov = record.get("score_pov", "side_to_move")
    white_kp, black_kp, white_ps, black_ps, threats, stm = _feature_lists(fen)
    if score > target_clip:
        score = target_clip
    elif score < -target_clip:
        score = -target_clip
    if pov == "white" and stm == 1:
        score = -score
    score = _target_from_white_score(score, record)
    score = float(np.clip(score, -target_clip, target_clip))
    key = " ".join(fen.split()[:4])
    group = str(
        (record or {}).get("source_game")
        or (record or {}).get("game_id")
        or (record or {}).get("opening")
        or (record or {}).get("source")
        or key
    )
    if group in {"self_play", "random_walk"}:
        group = f"{group}:{key}"
    return key, (white_kp, black_kp, white_ps, black_ps, threats, stm, score, fen, group)


def _parse_chunk(lines: list[str], target_clip: float):
    rows = []
    for line in lines:
        parsed = _row_from_line(line, target_clip)
        if parsed is not None:
            rows.append(parsed)
    return rows


_LOAD_LINES: list[str] = []
_LOAD_CLIP = 2000.0
_LOAD_TARGET_MODE = "wdl"
_LOAD_TEACHER_WDL_SCALE = 400.0
_LOAD_SEARCH_WDL_SCALE = 400.0
_LOAD_RESULT_WEIGHT = 0.0


def _target_from_white_score(score: float, record: dict | None) -> float:
    return training_target(
        score,
        target_mode=_LOAD_TARGET_MODE,
        teacher_wdl_scale=_LOAD_TEACHER_WDL_SCALE,
        search_wdl_scale=_LOAD_SEARCH_WDL_SCALE,
        extras_cp_white=0.0,
        residualize_extras=False,
        result_white=white_outcome(record or {}),
        result_weight=_LOAD_RESULT_WEIGHT,
        target_clip=_LOAD_CLIP,
    )


def _parse_range(start_end: tuple[int, int]):
    start, end = start_end
    return _parse_chunk(_LOAD_LINES[start:end], _LOAD_CLIP)


def load_dataset(
    path: Path,
    target_clip: float,
    workers: int = 0,
    target_mode: str = "wdl",
    wdl_scale: float = 400.0,
    result_weight: float = 0.0,
    teacher_wdl_scale: float | None = None,
    search_wdl_scale: float | None = None,
):
    import os
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor

    global _LOAD_LINES, _LOAD_CLIP, _LOAD_TARGET_MODE, _LOAD_TEACHER_WDL_SCALE
    global _LOAD_SEARCH_WDL_SCALE, _LOAD_RESULT_WEIGHT
    print(f"loading {path}", flush=True)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    _LOAD_LINES = raw.decode("utf-8").splitlines()
    _LOAD_CLIP = target_clip
    _LOAD_TARGET_MODE = target_mode
    _LOAD_TEACHER_WDL_SCALE = float(teacher_wdl_scale if teacher_wdl_scale is not None else wdl_scale)
    _LOAD_SEARCH_WDL_SCALE = float(search_wdl_scale if search_wdl_scale is not None else wdl_scale)
    _LOAD_RESULT_WEIGHT = result_weight
    n_lines = len(_LOAD_LINES)
    ranges = [(i, min(i + 4000, n_lines)) for i in range(0, n_lines, 4000)]

    if workers <= 0:
        workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    unique: dict[str, tuple] = {}
    if workers == 1 or len(ranges) <= 1:
        chunks = [_parse_range(span) for span in ranges]
    else:
        try:
            ctx = mp.get_context("fork")
        except ValueError:
            ctx = mp.get_context()
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            chunks = list(pool.map(_parse_range, ranges, chunksize=1))
    for index, parsed in enumerate(chunks, start=1):
        for key, row in parsed:
            unique[key] = row
        print(f"parsed chunk {index}/{len(ranges)} unique={len(unique)}", flush=True)
    _LOAD_LINES = []
    print(f"loaded {len(unique)} unique / {n_lines} lines", flush=True)
    return list(unique.values()), digest


def prediction_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction - target
    return {
        "mae_cp": float(np.mean(np.abs(error))),
        "rmse_cp": float(np.sqrt(np.mean(error * error))),
        "sign_accuracy": float(np.mean(np.sign(prediction) == np.sign(target))),
    }


def _offsets_from_lengths(lengths: np.ndarray) -> np.ndarray:
    offsets = np.empty(len(lengths), dtype=np.intp)
    offsets[0] = 0
    if len(lengths) > 1:
        np.cumsum(lengths[:-1], out=offsets[1:])
    return offsets


def _packed_sum(weight: np.ndarray, index_lists) -> np.ndarray:
    concat = np.concatenate(index_lists)
    lengths = np.fromiter((len(idx) for idx in index_lists), dtype=np.intp, count=len(index_lists))
    return np.add.reduceat(weight[concat], _offsets_from_lengths(lengths), axis=0)


def _scatter_padded(dest: np.ndarray, padded: np.ndarray, lengths: np.ndarray, rows: np.ndarray) -> None:
    mask = np.arange(padded.shape[1]) < lengths[:, None]
    np.add.at(dest, padded[mask], np.repeat(rows, lengths, axis=0))


def _unpack_rows(rows):
    n = len(rows)
    white_kp = np.empty(n, dtype=object)
    black_kp = np.empty(n, dtype=object)
    white_ps = np.empty(n, dtype=object)
    black_ps = np.empty(n, dtype=object)
    white_kp[:] = [row[0] for row in rows]
    black_kp[:] = [row[1] for row in rows]
    white_ps[:] = [row[2] for row in rows]
    black_ps[:] = [row[3] for row in rows]
    threats = np.stack([row[4] for row in rows])
    stm = np.fromiter((row[5] for row in rows), dtype=np.int8, count=n)
    target = np.fromiter((row[6] for row in rows), dtype=np.float32, count=n)
    return white_kp, black_kp, white_ps, black_ps, threats, stm, target


def _unpack_padded(rows):
    n = len(rows)
    max_p = max(len(row[0]) for row in rows)
    white_kp = np.full((n, max_p), FEATURES, dtype=np.int32)
    black_kp = np.full((n, max_p), FEATURES, dtype=np.int32)
    white_ps = np.full((n, max_p), PS_FEATURES, dtype=np.int32)
    black_ps = np.full((n, max_p), PS_FEATURES, dtype=np.int32)
    lengths = np.empty(n, dtype=np.intp)
    threats = np.empty((n, THREAT_DIM), dtype=np.float32)
    stm = np.empty(n, dtype=np.int8)
    target = np.empty(n, dtype=np.float32)
    for i, row in enumerate(rows):
        length = len(row[0])
        lengths[i] = length
        white_kp[i, :length] = row[0]
        black_kp[i, :length] = row[1]
        white_ps[i, :length] = row[2]
        black_ps[i, :length] = row[3]
        threats[i] = row[4]
        stm[i] = row[5]
        target[i] = row[6]
    return white_kp, black_kp, white_ps, black_ps, lengths, threats, stm, target


def _fake_quantize(values: np.ndarray, scale: float, low: float, high: float) -> np.ndarray:
    return np.clip(np.rint(values * scale), low, high) / scale


def _forward_padded(
    white_kp,
    black_kp,
    white_ps,
    black_ps,
    threats,
    stm,
    w0,
    w_ps,
    b0,
    w1,
    b1,
    w_threat,
    qat: bool = True,
):
    if qat:
        fw0 = _fake_quantize(w0, SCALE, -32768, 32767)
        fw_ps = _fake_quantize(w_ps, SCALE, -32768, 32767)
        fb0 = _fake_quantize(b0, SCALE, -32768, 32767)
        fw1 = _fake_quantize(w1, SCALE, -32768, 32767)
        fb1 = float(_fake_quantize(np.asarray([b1]), SCALE * SCALE, -(2**31), 2**31 - 1)[0])
        fw_threat = _fake_quantize(w_threat, SCALE, -32768, 32767)
    else:
        fw0, fw_ps, fb0, fw1, fb1, fw_threat = w0, w_ps, b0, w1, b1, w_threat
    white = fw0[white_kp].sum(axis=1) + fw_ps[white_ps].sum(axis=1) + fb0
    black = fw0[black_kp].sum(axis=1) + fw_ps[black_ps].sum(axis=1) + fb0
    own_acc = np.where(stm[:, None] == 0, white, black)
    opp_acc = np.where(stm[:, None] == 0, black, white)
    own = np.clip(own_acc, 0.0, 127.0)
    opponent = np.clip(opp_acc, 0.0, 127.0)
    if qat:
        own = _fake_quantize(own, SCALE, 0, 127 * SCALE)
        opponent = _fake_quantize(opponent, SCALE, 0, 127 * SCALE)
    predictions = own @ fw1[:HIDDEN] + opponent @ fw1[HIDDEN:] + fb1 + threats @ fw_threat
    return predictions.astype(np.float32, copy=False), white, black, own, opponent, own_acc, opp_acc


def _forward_parts(white_kp, black_kp, white_ps, black_ps, threats, stm, w0, w_ps, b0, w1, b1, w_threat):
    white = b0 + _packed_sum(w0, white_kp) + _packed_sum(w_ps, white_ps)
    black = b0 + _packed_sum(w0, black_kp) + _packed_sum(w_ps, black_ps)
    own_acc = np.where(stm[:, None] == 0, white, black)
    opp_acc = np.where(stm[:, None] == 0, black, white)
    own = np.clip(own_acc, 0.0, 127.0)
    opponent = np.clip(opp_acc, 0.0, 127.0)
    predictions = own @ w1[:HIDDEN] + opponent @ w1[HIDDEN:] + b1 + threats @ w_threat
    return predictions.astype(np.float32, copy=False), white, black, own, opponent, own_acc, opp_acc


def forward(rows, w0, w_ps, b0, w1, b1, w_threat):
    white_kp, black_kp, white_ps, black_ps, threats, stm, _target = _unpack_rows(rows)
    predictions, white, black, _own, _opp, _oa, _opa = _forward_parts(
        white_kp, black_kp, white_ps, black_ps, threats, stm, w0, w_ps, b0, w1, b1, w_threat
    )
    return predictions, (white, black)


def train(
    train_rows,
    validation_rows,
    epochs,
    batch_size,
    learning_rate,
    seed,
    init_path=None,
    checkpoint_path=None,
    qat=True,
    use_threats=True,
):
    rng = np.random.default_rng(seed)
    w0 = np.zeros((FEATURES + 1, HIDDEN), dtype=np.float32)
    w_ps = np.zeros((PS_FEATURES + 1, HIDDEN), dtype=np.float32)
    if init_path:
        packed = np.load(init_path)
        w0[:FEATURES] = packed["w0"].astype(np.float32)
        w_ps[:PS_FEATURES] = packed["w_ps"].astype(np.float32)
        b0 = packed["b0"].astype(np.float32)
        w1 = packed["w1"].astype(np.float32)
        b1 = float(packed["b1"])
        w_threat = packed["w_threat"].astype(np.float32)
        print(f"init from {init_path}", flush=True)
    else:
        w0[:FEATURES] = rng.normal(0.0, 0.02, (FEATURES, HIDDEN)).astype(np.float32)
        w_ps[:PS_FEATURES] = rng.normal(0.0, 0.03, (PS_FEATURES, HIDDEN)).astype(np.float32)
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
    best = (w0[:FEATURES].copy(), w_ps[:PS_FEATURES].copy(), b0.copy(), w1.copy(), b1, w_threat.copy())
    train_wkp, train_bkp, train_wps, train_bps, train_len, train_threats, train_stm, train_target = _unpack_padded(
        train_rows
    )
    val_wkp, val_bkp, val_wps, val_bps, _val_len, val_threats, val_stm, val_target = _unpack_padded(validation_rows)
    clip_lo = np.float32(-200.0)
    clip_hi = np.float32(200.0)
    lr = np.float32(learning_rate)
    step0 = np.empty_like(mw0)
    step_ps = np.empty_like(mps)

    for epoch in range(1, epochs + 1):
        print(f"epoch {epoch}/{epochs} train={len(train_rows)} val={len(validation_rows)}", flush=True)
        order = rng.permutation(len(train_rows))
        for start in range(0, len(order), batch_size):
            sel = order[start : start + batch_size]
            n_batch = len(sel)
            white_kp, black_kp = train_wkp[sel], train_bkp[sel]
            white_ps, black_ps = train_wps[sel], train_bps[sel]
            lengths, threats, stm, target = train_len[sel], train_threats[sel], train_stm[sel], train_target[sel]
            prediction, _white, _black, own, opponent, own_acc, opp_acc = _forward_padded(
                white_kp,
                black_kp,
                white_ps,
                black_ps,
                threats,
                stm,
                w0,
                w_ps,
                b0,
                w1,
                b1,
                w_threat,
                qat=qat,
            )
            error = prediction - target
            grad = np.clip(error, clip_lo, clip_hi)
            grad /= np.float32(n_batch)
            own_mask = (own_acc > 0.0) & (own_acc < 127.0)
            opp_mask = (opp_acc > 0.0) & (opp_acc < 127.0)
            grad_own = grad[:, None] * w1[:HIDDEN] * own_mask
            grad_opp = grad[:, None] * w1[HIDDEN:] * opp_mask
            stm_col = stm[:, None] == 0
            grad_white = np.where(stm_col, grad_own, grad_opp)
            grad_black = np.where(stm_col, grad_opp, grad_own)
            grad_b0 = grad_own.sum(axis=0) + grad_opp.sum(axis=0)
            grad_w1 = np.concatenate((own.T @ grad, opponent.T @ grad))
            grad_b1 = float(grad.sum())
            grad_th = threats.T @ grad

            np.multiply(mw0, 0.9, out=mw0)
            np.multiply(mps, 0.9, out=mps)
            _scatter_padded(mw0, white_kp, lengths, grad_white)
            _scatter_padded(mw0, black_kp, lengths, grad_black)
            _scatter_padded(mps, white_ps, lengths, grad_white)
            _scatter_padded(mps, black_ps, lengths, grad_black)
            np.multiply(mb0, 0.9, out=mb0)
            np.add(mb0, grad_b0, out=mb0)
            np.multiply(mw1, 0.9, out=mw1)
            np.add(mw1, grad_w1, out=mw1)
            mb1 = 0.9 * mb1 + grad_b1
            if use_threats:
                np.multiply(mth, 0.9, out=mth)
                np.add(mth, grad_th, out=mth)
            np.multiply(mw0, lr, out=step0)
            np.subtract(w0, step0, out=w0)
            np.multiply(mps, lr, out=step_ps)
            np.subtract(w_ps, step_ps, out=w_ps)
            b0 -= lr * mb0
            w1 -= lr * mw1
            b1 -= float(lr) * mb1
            if use_threats:
                w_threat -= lr * mth
            else:
                w_threat.fill(0.0)
            w0[-1] = 0
            w_ps[-1] = 0
            mw0[-1] = 0
            mps[-1] = 0

        validation_prediction, *_ = _forward_padded(
            val_wkp,
            val_bkp,
            val_wps,
            val_bps,
            val_threats,
            val_stm,
            w0,
            w_ps,
            b0,
            w1,
            b1,
            w_threat,
            qat=qat,
        )
        row = {"epoch": epoch, **prediction_metrics(validation_prediction, val_target)}
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if row["rmse_cp"] < best_rmse:
            best_rmse = row["rmse_cp"]
            best = (w0[:FEATURES].copy(), w_ps[:PS_FEATURES].copy(), b0.copy(), w1.copy(), b1, w_threat.copy())
        if checkpoint_path:
            Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
            np.savez(
                checkpoint_path,
                w0=best[0],
                w_ps=best[1],
                b0=best[2],
                w1=best[3],
                b1=np.float32(best[4]),
                w_threat=best[5],
                epoch=np.int32(epoch),
            )
            print(f"wrote checkpoint {checkpoint_path}", flush=True)
    return *best, history


def fold_factorization(w0: np.ndarray, w_ps: np.ndarray) -> np.ndarray:
    return (w0.reshape(KING_BUCKETS, PS_FEATURES, HIDDEN) + w_ps).reshape(FEATURES, HIDDEN)


def export_network(path: Path, w0: np.ndarray, b0: np.ndarray, w1: np.ndarray, b1: float, w_threat: np.ndarray):
    w0_q = np.clip(np.rint(w0 * SCALE), -32768, 32767).astype("<i2")
    b0_q = np.clip(np.rint(b0 * SCALE), -32768, 32767).astype("<i2")
    w1_q = np.clip(np.rint(w1 * SCALE), -32768, 32767).astype("<i2")
    th_q = np.clip(np.rint(w_threat * SCALE), -32768, 32767).astype("<i2")
    b1_q = int(np.clip(np.rint(b1 * SCALE * SCALE), -(2**31), 2**31 - 1))
    max_weight = int(max(np.max(np.abs(w0_q)), np.max(np.abs(b0_q)), np.max(np.abs(w1_q)), np.max(np.abs(th_q))))
    max_piece_counts = (8, 2, 2, 2, 1, 1)
    bucketed = w0_q.reshape(KING_BUCKETS, 12, 64, HIDDEN)
    conservative = np.abs(b0_q).astype(np.int64)
    for piece in range(12):
        per_hidden_max = np.max(np.abs(bucketed[:, piece]).astype(np.int64), axis=(0, 1))
        conservative += max_piece_counts[piece % 6] * per_hidden_max
    if max_weight >= 32767:
        raise ValueError("quantized KAT weights hit the int16 limit")
    if int(np.max(conservative)) >= 32767:
        raise ValueError(f"KAT accumulator bound exceeds int16: {int(np.max(conservative))}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(b"NSCEKAT1")
        output.write(struct.pack("<iii", FEATURES, HIDDEN, THREAT_DIM))
        output.write(w0_q.tobytes(order="C"))
        output.write(b0_q.tobytes(order="C"))
        output.write(w1_q.tobytes(order="C"))
        output.write(th_q.tobytes(order="C"))
        output.write(struct.pack("<i", b1_q))
    return {
        "max_abs_quantized_weight": max_weight,
        "conservative_accumulator_abs_bound": int(np.max(conservative)),
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="train/data/lichess_evals.jsonl")
    parser.add_argument("--output", default="nets/kat_candidate.bin")
    parser.add_argument("--metrics", default="nets/kat_candidate.metrics.json")
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.0004)
    parser.add_argument("--target-clip", type=float, default=2000.0)
    parser.add_argument("--target-mode", choices=("cp", "wdl"), default="wdl")
    parser.add_argument("--wdl-scale", type=float, default=NSCE_SEARCH_WDL_SCALE)
    parser.add_argument("--teacher-wdl-scale", type=float, default=None)
    parser.add_argument("--search-wdl-scale", type=float, default=None)
    parser.add_argument("--result-weight", type=float, default=0.0)
    parser.add_argument("--no-qat", action="store_true", help="disable fake integer forward during training")
    parser.add_argument("--no-threats", action="store_true", help="train the king-relative base without KAT residuals")
    parser.add_argument("--minimum-samples", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument("--init", default="", help="optional float checkpoint (.npz) to continue from")
    parser.add_argument("--checkpoint", default="", help="write best float weights here after each epoch")
    args = parser.parse_args()

    if not 0.0 <= args.result_weight <= 1.0:
        parser.error("--result-weight must be in [0, 1]")
    teacher_wdl_scale = args.teacher_wdl_scale if args.teacher_wdl_scale is not None else args.wdl_scale
    search_wdl_scale = args.search_wdl_scale if args.search_wdl_scale is not None else args.wdl_scale
    rows, dataset_sha256 = load_dataset(
        Path(args.data),
        args.target_clip,
        target_mode=args.target_mode,
        wdl_scale=args.wdl_scale,
        result_weight=args.result_weight,
        teacher_wdl_scale=teacher_wdl_scale,
        search_wdl_scale=search_wdl_scale,
    )
    if len(rows) < args.minimum_samples:
        raise ValueError(f"KAT promotion requires at least {args.minimum_samples} samples; found {len(rows)}")
    print(f"split {len(rows)} samples (sha256={dataset_sha256[:12]}…)", flush=True)
    train_rows, validation_rows = [], []
    for row in rows:
        bucket = int.from_bytes(hashlib.sha256(row[8].encode()).digest()[:4], "little") % 10
        (validation_rows if bucket == 0 else train_rows).append(row)
    w0, w_ps, b0, w1, b1, w_threat, history = train(
        train_rows,
        validation_rows,
        args.epochs,
        args.batch_size,
        args.learning_rate,
        args.seed,
        init_path=args.init or None,
        checkpoint_path=args.checkpoint or None,
        qat=not args.no_qat,
        use_threats=not args.no_threats,
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
            "validation_groups": len({row[8] for row in validation_rows}),
        "seed": args.seed,
        "target_mode": args.target_mode,
        "wdl_scale": args.wdl_scale,
        "teacher_wdl_scale": teacher_wdl_scale,
        "search_wdl_scale": search_wdl_scale,
        "result_weight": args.result_weight,
        "qat": not args.no_qat,
        "threats": not args.no_threats,
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
