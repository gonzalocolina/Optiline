#!/usr/bin/env python3
"""Compare NSCEPER1 float SCReLU to C++ integers on packed nets.

Quantized Python must match C++ exactly (same toward-zero `/`). |float − C++|
≤ 4 cp on 10k FENs — pairwise /QA plus two SCReLU /QA/QB truncations. Gen0
measured 2.98 cp; a 2 cp gate is too tight on a trained net.

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

from pack_nsceper1 import BUCKETS, FEATURES, HIDDEN, L2, L3, QA, QB, SCALE, SIMPLE_HIDDEN  # noqa: E402
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
        hidden, features, buckets, l2, l3, qa, qb, scale = struct.unpack_from("<8i", data, 8)
        self.qa = qa
        self.qb = qb
        self.scale = scale
        self.hidden = hidden
        self.simple = buckets == 0 and l2 == 0 and l3 == 0
        offset = 8 + 32
        n_w0 = features * hidden
        self.w0 = list(struct.unpack_from(f"<{n_w0}h", data, offset))
        offset += n_w0 * 2
        self.b0 = list(struct.unpack_from(f"<{hidden}h", data, offset))
        offset += hidden * 2
        if self.simple:
            if (hidden, features) != (SIMPLE_HIDDEN, FEATURES):
                raise ValueError(f"{path} simple header {(hidden, features)} != {(SIMPLE_HIDDEN, FEATURES)}")
            self.l1w_flat = list(struct.unpack_from(f"<{2 * hidden}h", data, offset))
            offset += 2 * hidden * 2
            (self.l1b_simple,) = struct.unpack_from("<i", data, offset)
            return
        if (hidden, features, buckets, l2, l3) != (HIDDEN, FEATURES, BUCKETS, L2, L3):
            raise ValueError(
                f"{path} header {(hidden, features, buckets, l2, l3)} != {(HIDDEN, FEATURES, BUCKETS, L2, L3)}"
            )
        n_l1w = buckets * l2 * hidden
        flat = struct.unpack_from(f"<{n_l1w}h", data, offset)
        offset += n_l1w * 2
        self.l1w = [
            [list(flat[(b * l2 + j) * hidden : (b * l2 + j + 1) * hidden]) for j in range(l2)]
            for b in range(buckets)
        ]
        n_l1b = buckets * l2
        flat_b = struct.unpack_from(f"<{n_l1b}i", data, offset)
        offset += n_l1b * 4
        self.l1b = [list(flat_b[b * l2 : (b + 1) * l2]) for b in range(buckets)]
        n_l2w = buckets * l3 * l2
        flat = struct.unpack_from(f"<{n_l2w}h", data, offset)
        offset += n_l2w * 2
        self.l2w = [
            [list(flat[(b * l3 + j) * l2 : (b * l3 + j + 1) * l2]) for j in range(l3)]
            for b in range(buckets)
        ]
        n_l2b = buckets * l3
        flat_b = struct.unpack_from(f"<{n_l2b}i", data, offset)
        offset += n_l2b * 4
        self.l2b = [list(flat_b[b * l3 : (b + 1) * l3]) for b in range(buckets)]
        n_l3w = buckets * l3
        flat = struct.unpack_from(f"<{n_l3w}h", data, offset)
        offset += n_l3w * 2
        self.l3w = [list(flat[b * l3 : (b + 1) * l3]) for b in range(buckets)]
        self.l3b = list(struct.unpack_from(f"<{buckets}i", data, offset))

    def _accumulators(self, pieces: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
        acc_w = list(self.b0)
        acc_b = list(self.b0)
        hidden = self.hidden
        for pc, sq in pieces:
            fw = per1_feature(0, pc, sq) * hidden
            fb = per1_feature(1, pc, sq) * hidden
            for h in range(hidden):
                acc_w[h] = clamp_i16(acc_w[h] + self.w0[fw + h])
                acc_b[h] = clamp_i16(acc_b[h] + self.w0[fb + h])
        return acc_w, acc_b

    def _simple_int(self, stm_acc: list[int], nstm_acc: list[int]) -> int:
        qa, qb = self.qa, self.qb
        act: list[int] = []
        for acc in (stm_acc, nstm_acc):
            for x in acc:
                c = max(0, min(qa, x))
                act.append(c * c)
        total = 0
        for i, a in enumerate(act):
            total += a * self.l1w_flat[i]
        total = trunc_div(total, qa) + self.l1b_simple
        return trunc_div(total * self.scale, qa * qb)

    def _mlp_int(self, stm_acc: list[int], nstm_acc: list[int], piece_count: int) -> int:
        qa, qb = self.qa, self.qb
        half = HIDDEN // 2
        pair = [0] * HIDDEN

        def fill(acc: list[int], off: int) -> None:
            for i in range(half):
                x0 = max(0, min(qa, acc[i]))
                x1 = max(0, min(qa, acc[half + i]))
                pair[off + i] = trunc_div(x0 * x1, qa)

        fill(stm_acc, 0)
        fill(nstm_acc, half)
        bucket = per1_bucket(piece_count)
        h2 = [0] * L2
        for j in range(L2):
            s = 0
            for i in range(HIDDEN):
                s += pair[i] * self.l1w[bucket][j][i]
            s = trunc_div(s, qa) + self.l1b[bucket][j]
            x = max(0, min(qa, trunc_div(s, qb)))
            h2[j] = x * x
        h3 = [0] * L3
        for j in range(L3):
            s = 0
            for i in range(L2):
                s += h2[i] * self.l2w[bucket][j][i]
            s = trunc_div(s, qa) + self.l2b[bucket][j]
            x = max(0, min(qa, trunc_div(s, qb)))
            h3[j] = x * x
        total = 0
        for i in range(L3):
            total += h3[i] * self.l3w[bucket][i]
        total = trunc_div(total, qa) + self.l3b[bucket]
        return trunc_div(total * self.scale, qa * qb)

    def eval_int(self, fen: str) -> int:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        if self.simple:
            return self._simple_int(stm_acc, nstm_acc)
        return self._mlp_int(stm_acc, nstm_acc, len(pieces))

    def eval_float(self, fen: str) -> float:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        qa = float(self.qa)
        qb = float(self.qb)
        if self.simple:
            act: list[float] = []
            for acc in (stm_acc, nstm_acc):
                for x in acc:
                    c = max(0.0, min(qa, float(x)))
                    act.append(c * c)
            total = sum(a * w for a, w in zip(act, self.l1w_flat))
            total = total / qa + self.l1b_simple
            return total * self.scale / (qa * qb)
        half = HIDDEN // 2
        pair = [0.0] * HIDDEN

        def fill(acc: list[int], off: int) -> None:
            for i in range(half):
                x0 = max(0.0, min(qa, float(acc[i])))
                x1 = max(0.0, min(qa, float(acc[half + i])))
                pair[off + i] = x0 * x1 / qa

        fill(stm_acc, 0)
        fill(nstm_acc, half)
        bucket = per1_bucket(len(pieces))
        h2 = [0.0] * L2
        for j in range(L2):
            s = sum(pair[i] * self.l1w[bucket][j][i] for i in range(HIDDEN))
            s = s / qa + self.l1b[bucket][j]
            x = max(0.0, min(qa, s / qb))
            h2[j] = x * x
        h3 = [0.0] * L3
        for j in range(L3):
            s = sum(h2[i] * self.l2w[bucket][j][i] for i in range(L2))
            s = s / qa + self.l2b[bucket][j]
            x = max(0.0, min(qa, s / qb))
            h3[j] = x * x
        total = sum(h3[i] * self.l3w[bucket][i] for i in range(L3))
        total = total / qa + self.l3b[bucket]
        return total * self.scale / (qa * qb)


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
    parser.add_argument("--max-abs-cp", type=float, default=4.0)
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
