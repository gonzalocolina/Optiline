#!/usr/bin/env python3
"""Pack FENs + converted NSCE search-cp into bulletformat ChessBoard records.

Does not append onto train/data/gen0.bin. Score field is the NSCE search coin
(scale 400) after SFNNv16 static eval → teacher WDL → NSCE cp. Result is unused
(NSCE_WDL=0). Layout matches engine/src/datagen.cpp to_bullet.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "train"))

from eval_scale import NSCE_SEARCH_WDL_SCALE  # noqa: E402
from import_lichess_evals import normalize_fen  # noqa: E402
from sf_eval import (  # noqa: E402
    DEFAULT_SF19,
    StockfishEvalEngine,
    fit_teacher_wdl_scale,
    sfnnv16_to_nsce_cp,
)

RECORD = struct.Struct("<Q16sh6B")
assert RECORD.size == 32

PIECE_INDEX = {
    "P": 0,
    "N": 1,
    "B": 2,
    "R": 3,
    "Q": 4,
    "K": 5,
    "p": 0,
    "n": 1,
    "b": 2,
    "r": 3,
    "q": 4,
    "k": 5,
}


def byteswap64(value: int) -> int:
    return int.from_bytes(value.to_bytes(8, "little"), "big")


def fen_bitboards(fen: str) -> tuple[list[int], int]:
    """Return [white, black, P, N, B, R, Q, K] bitboards and stm (0 white / 1 black)."""
    parts = fen.split()
    board, stm = parts[0], parts[1]
    bbs = [0] * 8
    rank, file = 7, 0
    for ch in board:
        if ch == "/":
            rank -= 1
            file = 0
            continue
        if ch.isdigit():
            file += int(ch)
            continue
        if ch not in PIECE_INDEX:
            raise ValueError(f"bad FEN piece {ch!r}")
        sq = rank * 8 + file
        bit = 1 << sq
        pt = PIECE_INDEX[ch]
        colour = 0 if ch.isupper() else 1
        bbs[colour] |= bit
        bbs[2 + pt] |= bit
        file += 1
    if bbs[0].bit_count() + bbs[1].bit_count() < 2:
        raise ValueError(f"too few pieces in {fen}")
    return bbs, 0 if stm == "w" else 1


def to_bullet(bbs: list[int], stm: int, score_white: int, result_white: float = 0.5) -> bytes:
    boards = list(bbs)
    score = int(score_white)
    result = float(result_white)
    if stm == 1:
        boards = [byteswap64(b) for b in boards]
        boards[0], boards[1] = boards[1], boards[0]
        score = -score
        result = 1.0 - result
    occ = boards[0] | boards[1]
    pcs = [0] * 16
    remaining = occ
    idx = 0
    while remaining:
        sq = (remaining & -remaining).bit_length() - 1
        bit = 1 << sq
        remaining &= remaining - 1
        colour = 1 if (bit & boards[1]) else 0
        piece = 0
        for p in range(6):
            if bit & boards[2 + p]:
                piece = p
                break
        nibble = (colour << 3) | piece
        pcs[idx // 2] |= nibble << (4 * (idx & 1))
        idx += 1
    white_king = boards[0] & boards[7]
    black_king = boards[1] & boards[7]
    if white_king == 0 or black_king == 0:
        raise ValueError("missing king")
    ksq = (white_king & -white_king).bit_length() - 1
    opp = (black_king & -black_king).bit_length() - 1
    packed = RECORD.pack(
        occ,
        bytes(pcs),
        max(-30000, min(30000, score)),
        int(2.0 * result + 0.5),
        ksq,
        opp ^ 56,
        0,
        0,
        0,
    )
    return packed


def fen_to_record(fen: str, nsce_cp_white: int, result_white: float = 0.5) -> bytes:
    bbs, stm = fen_bitboards(fen)
    return to_bullet(bbs, stm, nsce_cp_white, result_white)


def iter_fens(path: Path, limit: int = 0) -> list[str]:
    fens: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                fen = normalize_fen(str(json.loads(line).get("fen") or ""))
            else:
                fen = normalize_fen(line)
            if fen is None:
                continue
            key = " ".join(fen.split()[:4])
            if key in seen:
                continue
            seen.add(key)
            fens.append(fen)
            if limit and len(fens) >= limit:
                break
    return fens


def _label_one(eng: StockfishEvalEngine, fen: str, teacher_wdl_scale: float) -> tuple[str, int, int] | None:
    try:
        ev = eng.eval_sfnnv16(fen)
    except (RuntimeError, ValueError):
        return None
    nsce = sfnnv16_to_nsce_cp(ev.nnue_white_cp, teacher_wdl_scale)
    return fen, ev.nnue_white_cp, int(round(nsce))


def _label_chunk(
    fens: list[str],
    teacher_wdl_scale: float,
    engine_path: str,
) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    eng = StockfishEvalEngine(engine_path)
    try:
        for i, fen in enumerate(fens, 1):
            labeled = _label_one(eng, fen, teacher_wdl_scale)
            if labeled is None:
                try:
                    eng.close()
                except Exception:
                    pass
                eng = StockfishEvalEngine(engine_path)
                labeled = _label_one(eng, fen, teacher_wdl_scale)
            if labeled is None:
                continue
            out.append(labeled)
            if i % 10000 == 0:
                print(f"labeled {i}/{len(fens)} in worker", flush=True)
    finally:
        eng.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=ROOT / "train/data/lichess_evals_1m.jsonl")
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "train/data/sfnnv16_static.bin")
    ap.add_argument("--engine", type=Path, default=DEFAULT_SF19)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--fit-n", type=int, default=64)
    ap.add_argument("--teacher-wdl-scale", type=float, default=None)
    ap.add_argument("--scale-json", type=Path, default=None)
    args = ap.parse_args()
    if args.output.resolve() == (ROOT / "train/data/gen0.bin").resolve():
        raise SystemExit("refusing to write onto train/data/gen0.bin")

    fens = iter_fens(args.input, args.limit)
    if len(fens) < 8:
        raise SystemExit(f"not enough FENs in {args.input}")

    scale = args.teacher_wdl_scale
    if scale is None:
        fit_fens = fens[: max(8, args.fit_n)]
        print(f"fitting teacher WDL scale on {len(fit_fens)} FENs", flush=True)
        with StockfishEvalEngine(args.engine) as eng:
            scale = fit_teacher_wdl_scale(eng, fit_fens)
        print(f"teacher_wdl_scale={scale} search_wdl_scale={NSCE_SEARCH_WDL_SCALE}", flush=True)
    if abs(scale - NSCE_SEARCH_WDL_SCALE) < 1e-9:
        raise SystemExit("fitted teacher WDL scale equals 400; refusing currency bug")

    scale_path = args.scale_json or args.output.with_suffix(".scale.json")
    scale_path.write_text(
        json.dumps(
            {
                "teacher_wdl_scale": scale,
                "search_wdl_scale": NSCE_SEARCH_WDL_SCALE,
                "engine": str(args.engine),
                "n_fens": len(fens),
                "source": str(args.input),
            },
            indent=2,
        )
        + "\n"
    )

    workers = max(1, args.workers)
    chunks = [fens[i::workers] for i in range(workers)]
    labeled: list[tuple[str, int, int]] = []
    if workers == 1:
        labeled = _label_chunk(fens, scale, str(args.engine))
    else:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_label_chunk, chunk, scale, str(args.engine)) for chunk in chunks if chunk]
            for fut in futs:
                labeled.extend(fut.result())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    n_written = 0
    raw_path = args.output.with_suffix(".raw.bin")
    with args.output.open("wb") as out, raw_path.open("wb") as raw_out:
        for fen, raw_cp, nsce_cp in labeled:
            try:
                out.write(fen_to_record(fen, nsce_cp))
            except ValueError:
                continue
            raw_out.write(struct.pack("<h", max(-30000, min(30000, int(raw_cp)))))
            n_written += 1
            if n_written % 50000 == 0:
                print(f"wrote {n_written}", flush=True)
    print(f"wrote {n_written} records ({n_written * 32} bytes) to {args.output}")
    print(f"wrote {n_written} raw_teacher_cp int16 to {raw_path}")
    return 0 if n_written else 1


if __name__ == "__main__":
    raise SystemExit(main())
