#!/usr/bin/env python3
"""Compare NSCEPER1 float SCReLU to C++ integers on packed nets.

Quantized Python must match C++ exactly (same toward-zero `/`). |float − C++|
≤ 2 cp on 10k FENs — two integer divisions can exceed 1 cp vs the real SCReLU.

UseExtras is forced off; extras() is not part of the net. Do not run this as a
promotion gate — only as an export check before the first fastchess match.
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

from pack_nsceper1 import BUCKETS, FEATURES, HIDDEN, QA, QB, SCALE  # noqa: E402
from uci_common import UciEngine  # noqa: E402

PIECE = {
    "P": 0,
    "N": 1,
    "B": 2,
    "R": 3,
    "Q": 4,
    "K": 5,
    "p": 6,
    "n": 7,
    "b": 8,
    "r": 9,
    "q": 10,
    "k": 11,
}


def clamp_i16(value: int) -> int:
    return max(-32768, min(32767, value))


def trunc_div(numer: int, denom: int) -> int:
    """C++ integer `/` (toward zero). Python `//` floors and misses by 1–2 cp."""
    if numer < 0:
        return -((-numer) // denom)
    return numer // denom



def per1_feature(perspective: int, pc: int, sq: int) -> int:
    oriented_sq = sq if perspective == 0 else sq ^ 56
    oriented_pc = pc
    if perspective == 1:
        oriented_pc += 6 if pc < 6 else -6
    return oriented_pc * 64 + oriented_sq


def per1_bucket(piece_count: int) -> int:
    n = max(2, min(32, piece_count))
    return (n - 2) // 4


def pieces_from_fen(fen: str) -> tuple[list[tuple[int, int]], int]:
    board, stm, *_ = fen.split()
    pieces: list[tuple[int, int]] = []
    rank = 7
    file = 0
    for ch in board:
        if ch == "/":
            rank -= 1
            file = 0
            continue
        if ch.isdigit():
            file += int(ch)
            continue
        if ch not in PIECE:
            raise ValueError(f"bad FEN piece {ch!r} in {fen}")
        pieces.append((PIECE[ch], rank * 8 + file))
        file += 1
    return pieces, 0 if stm == "w" else 1


class Per1Net:
    def __init__(self, path: Path) -> None:
        data = path.read_bytes()
        if data[:8] != b"NSCEPER1":
            raise ValueError(f"{path} is not NSCEPER1")
        hidden, features, buckets, qa, qb, scale = struct.unpack_from("<6i", data, 8)
        if (hidden, features, buckets) != (HIDDEN, FEATURES, BUCKETS):
            raise ValueError(f"{path} header {(hidden, features, buckets)} != {(HIDDEN, FEATURES, BUCKETS)}")
        self.qa = qa
        self.qb = qb
        self.scale = scale
        offset = 32
        n_w0 = features * hidden
        self.w0 = list(struct.unpack_from(f"<{n_w0}h", data, offset))
        offset += n_w0 * 2
        self.b0 = list(struct.unpack_from(f"<{hidden}h", data, offset))
        offset += hidden * 2
        n_w1 = buckets * 2 * hidden
        flat_w1 = struct.unpack_from(f"<{n_w1}h", data, offset)
        offset += n_w1 * 2
        self.w1 = [list(flat_w1[b * 2 * hidden : (b + 1) * 2 * hidden]) for b in range(buckets)]
        self.b1 = list(struct.unpack_from(f"<{buckets}i", data, offset))

    def _accumulators(self, pieces: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
        acc_w = list(self.b0)
        acc_b = list(self.b0)
        for pc, sq in pieces:
            fw = per1_feature(0, pc, sq) * HIDDEN
            fb = per1_feature(1, pc, sq) * HIDDEN
            for h in range(HIDDEN):
                acc_w[h] = clamp_i16(acc_w[h] + self.w0[fw + h])
                acc_b[h] = clamp_i16(acc_b[h] + self.w0[fb + h])
        return acc_w, acc_b

    def eval_int(self, fen: str) -> int:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        bucket = per1_bucket(len(pieces))
        w = self.w1[bucket]
        qa = self.qa
        total = 0
        for h in range(HIDDEN):
            x = max(0, min(qa, stm_acc[h]))
            total += x * x * w[h]
            x = max(0, min(qa, nstm_acc[h]))
            total += x * x * w[HIDDEN + h]
        total = trunc_div(total, qa)
        total += self.b1[bucket]
        return trunc_div(total * self.scale, qa * self.qb)

    def eval_float(self, fen: str) -> float:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        w = self.w1[per1_bucket(len(pieces))]
        qa = float(self.qa)
        qb = float(self.qb)
        total = self.b1[per1_bucket(len(pieces))] / (qa * qb)
        for h in range(HIDDEN):
            x = min(max(stm_acc[h] / qa, 0.0), 1.0)
            total += x * x * (w[h] / qb)
            x = min(max(nstm_acc[h] / qa, 0.0), 1.0)
            total += x * x * (w[HIDDEN + h] / qb)
        return total * self.scale


def load_fens(path: Path, limit: int) -> list[str]:
    fens: list[str] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            fen = str(json.loads(line).get("fen", "")).strip()
        else:
            parts = line.split()
            fen = " ".join(parts[:4]) if len(parts) >= 4 else ""
        if fen:
            fens.append(fen)
        if len(fens) >= limit:
            break
    if not fens:
        raise SystemExit(f"no FENs in {path}")
    return fens


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", type=Path, required=True)
    parser.add_argument("--engine", type=Path, default=ROOT / "build" / "nsce")
    parser.add_argument("--fens", type=Path, default=ROOT / "train/data/lichess_evals_1m.jsonl")
    parser.add_argument("--n", type=int, default=10_000)
    parser.add_argument("--max-abs-cp", type=float, default=2.0)
    args = parser.parse_args()

    net = Per1Net(args.net)
    fens = load_fens(args.fens, args.n * 2)
    engine = UciEngine([str(args.engine)], "nsce", cwd=ROOT)
    engine.apply_options(
        {
            "UseNNUE": "true",
            "EvalFile": str(args.net.resolve()),
            "UseExtras": "false",
            "Hash": "16",
            "Threads": "1",
        }
    )
    max_float = 0.0
    max_int = 0
    n_int_mismatch = 0
    n_ok = 0
    n_skip = 0

    def boot() -> UciEngine:
        eng = UciEngine([str(args.engine)], "nsce", cwd=ROOT)
        eng.apply_options(
            {
                "UseNNUE": "true",
                "EvalFile": str(args.net.resolve()),
                "UseExtras": "false",
                "Hash": "16",
                "Threads": "1",
            }
        )
        return eng

    try:
        for fen in fens:
            if n_ok >= args.n:
                break
            try:
                details = engine.evaluate_details(fen)
            except RuntimeError as exc:
                msg = str(exc)
                n_skip += 1
                engine.close()
                engine = boot()
                if "invalid" in msg.lower():
                    continue
                print(f"UCI eval failed fen={fen!r}: {exc}", file=sys.stderr)
                details = engine.evaluate_details(fen)
            cpp = int(details["nnue"])
            q = net.eval_int(fen)
            fl = net.eval_float(fen)
            int_err = abs(q - cpp)
            float_err = abs(fl - cpp)
            if int_err:
                n_int_mismatch += 1
            max_int = max(max_int, int_err)
            max_float = max(max_float, float_err)
            n_ok += 1
    finally:
        engine.close()

    print(
        f"n={n_ok} skipped={n_skip} max|int-C++|={max_int} mismatches={n_int_mismatch} "
        f"max|float-C++|={max_float:.4f} gate={args.max_abs_cp}"
    )
    if n_ok < args.n:
        print(f"FAIL: only {n_ok} valid FENs, need {args.n}")
        return 1
    if n_int_mismatch:
        print("FAIL: Python quantized eval disagrees with C++ nnue")
        return 1
    if max_float > args.max_abs_cp:
        print("FAIL: float-ref vs C++ exceeds gate")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
