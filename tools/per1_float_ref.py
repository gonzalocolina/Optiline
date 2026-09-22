#!/usr/bin/env python3
"""Compare NSCEPER1 float SCReLU to C++ integers on packed nets.

Quantized Python must match C++ exactly (same toward-zero `/`). |float − C++|
≤ 8 cp on 10k FENs. The MLP gate of 4 cp was set after gen0 measured 2.98.
HL adds another SCReLU square: nsce-20 already reached 3.94 cp on 2000 FENs,
so 4 cp would fail a correct export and skip the Elo screen.

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

from pack_nsceper1 import (  # noqa: E402
    BUCKETS,
    FEATURES,
    HIDDEN,
    HL,
    L2,
    L3,
    L2_ACT,
    L3_ACT,
    QA,
    QB,
    SCALE,
    SIMPLE_HIDDEN,
)
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
        self.hl = buckets == 0 and l2 == HL and l3 == 1
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
        if self.hl:
            if (hidden, features) != (SIMPLE_HIDDEN, FEATURES):
                raise ValueError(f"{path} hl header {(hidden, features)} != {(SIMPLE_HIDDEN, FEATURES)}")
            n_l1 = HL * 2 * hidden
            self.hl_w1 = list(struct.unpack_from(f"<{n_l1}h", data, offset))
            offset += n_l1 * 2
            self.hl_b1 = list(struct.unpack_from(f"<{HL}i", data, offset))
            offset += HL * 4
            self.hl_w2 = list(struct.unpack_from(f"<{HL}h", data, offset))
            offset += HL * 2
            (self.hl_b2,) = struct.unpack_from("<i", data, offset)
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
        n_l2w = buckets * l3 * (2 * l2)
        flat = struct.unpack_from(f"<{n_l2w}h", data, offset)
        offset += n_l2w * 2
        l2_in = 2 * l2
        self.l2w = [
            [list(flat[(b * l3 + j) * l2_in : (b * l3 + j + 1) * l2_in]) for j in range(l3)]
            for b in range(buckets)
        ]
        n_l2b = buckets * l3
        flat_b = struct.unpack_from(f"<{n_l2b}i", data, offset)
        offset += n_l2b * 4
        self.l2b = [list(flat_b[b * l3 : (b + 1) * l3]) for b in range(buckets)]
        n_l3w = buckets * (2 * l3)
        flat = struct.unpack_from(f"<{n_l3w}h", data, offset)
        offset += n_l3w * 2
        l3_in = 2 * l3
        self.l3w = [list(flat[b * l3_in : (b + 1) * l3_in]) for b in range(buckets)]
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

    def l2_preacts(self, fen: str) -> list[int]:
        """L2 affine before CReLU, integer scale qa*qb. z in [0,1] ↔ (0, qa*qb)."""
        if self.simple:
            raise ValueError("simple graph has no L2")
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        qa = self.qa
        half = HIDDEN // 2
        pair = [0] * HIDDEN
        for off, acc in ((0, stm_acc), (half, nstm_acc)):
            for i in range(half):
                x0 = max(0, min(qa, acc[i]))
                x1 = max(0, min(qa, acc[half + i]))
                pair[off + i] = trunc_div(x0 * x1, qa)
        bucket = per1_bucket(len(pieces))
        pre = [0] * L2
        for j in range(L2):
            s = 0
            for i in range(HIDDEN):
                s += pair[i] * self.l1w[bucket][j][i]
            pre[j] = trunc_div(s, qa) + self.l1b[bucket][j]
        return pre

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

    def _hl_act(self, stm_acc: list[int], nstm_acc: list[int]) -> list[int]:
        qa = self.qa
        act: list[int] = []
        for acc in (stm_acc, nstm_acc):
            for x in acc:
                c = max(0, min(qa, x))
                act.append(c * c)
        return act

    def _hl_int(self, stm_acc: list[int], nstm_acc: list[int]) -> int:
        qa, qb = self.qa, self.qb
        act = self._hl_act(stm_acc, nstm_acc)
        h = [0] * HL
        width = 2 * self.hidden
        for j in range(HL):
            s = 0
            base = j * width
            for i in range(width):
                s += act[i] * self.hl_w1[base + i]
            pre = trunc_div(s, qa) + self.hl_b1[j]
            x = max(0, min(qa, trunc_div(pre, qb)))
            h[j] = x * x
        total = 0
        for j in range(HL):
            total += h[j] * self.hl_w2[j]
        total = trunc_div(total, qa) + self.hl_b2
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
        h2pre = [0] * L2
        for j in range(L2):
            s = 0
            for i in range(HIDDEN):
                s += pair[i] * self.l1w[bucket][j][i]
            h2pre[j] = trunc_div(s, qa) + self.l1b[bucket][j]
        h2 = [0] * L2_ACT
        for j in range(L2):
            x = max(0, min(qa, trunc_div(h2pre[j], qb)))
            h2[j] = x
            h2[L2 + j] = trunc_div(x * x, qa)
        skip = (h2[L2 - 2] - h2[L2 - 1]) * qb
        h3pre = [0] * L3
        for j in range(L3):
            s = 0
            for i in range(L2_ACT):
                s += h2[i] * self.l2w[bucket][j][i]
            h3pre[j] = trunc_div(s, qa) + self.l2b[bucket][j]
        h3 = [0] * L3_ACT
        for j in range(L3):
            x = max(0, min(qa, trunc_div(h3pre[j], qb)))
            h3[j] = x
            h3[L3 + j] = trunc_div(x * x, qa)
        total = 0
        for i in range(L3_ACT):
            total += h3[i] * self.l3w[bucket][i]
        total = trunc_div(total, qa) + self.l3b[bucket] + skip
        return trunc_div(total * self.scale, qa * qb)

    def eval_parts(self, fen: str) -> dict[str, int]:
        """Centipawn split: L3 affine, L3 bias, skip. Sum is eval_int."""
        if self.simple:
            raise ValueError("simple graph has no L3/skip split")
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        qa, qb = self.qa, self.qb
        half = HIDDEN // 2
        pair = [0] * HIDDEN
        for off, acc in ((0, stm_acc), (half, nstm_acc)):
            for i in range(half):
                x0 = max(0, min(qa, acc[i]))
                x1 = max(0, min(qa, acc[half + i]))
                pair[off + i] = trunc_div(x0 * x1, qa)
        bucket = per1_bucket(len(pieces))
        h2pre = [0] * L2
        for j in range(L2):
            s = 0
            for i in range(HIDDEN):
                s += pair[i] * self.l1w[bucket][j][i]
            h2pre[j] = trunc_div(s, qa) + self.l1b[bucket][j]
        h2 = [0] * L2_ACT
        for j in range(L2):
            x = max(0, min(qa, trunc_div(h2pre[j], qb)))
            h2[j] = x
            h2[L2 + j] = trunc_div(x * x, qa)
        skip = (h2[L2 - 2] - h2[L2 - 1]) * qb
        h3pre = [0] * L3
        for j in range(L3):
            s = 0
            for i in range(L2_ACT):
                s += h2[i] * self.l2w[bucket][j][i]
            h3pre[j] = trunc_div(s, qa) + self.l2b[bucket][j]
        h3 = [0] * L3_ACT
        for j in range(L3):
            x = max(0, min(qa, trunc_div(h3pre[j], qb)))
            h3[j] = x
            h3[L3 + j] = trunc_div(x * x, qa)
        mlp = 0
        for i in range(L3_ACT):
            mlp += h3[i] * self.l3w[bucket][i]
        mlp = trunc_div(mlp, qa)
        def cp(x: int) -> int:
            return trunc_div(x * self.scale, qa * qb)
        return {
            "mlp": cp(mlp),
            "l3b": cp(self.l3b[bucket]),
            "skip": cp(skip),
            "total": trunc_div((mlp + self.l3b[bucket] + skip) * self.scale, qa * qb),
            "bucket": bucket,
        }

    def l2_crelu(self, fen: str) -> list[int]:
        qa, qb = self.qa, self.qb
        return [max(0, min(qa, trunc_div(z, qb))) for z in self.l2_preacts(fen)]

    def eval_int(self, fen: str) -> int:
        pieces, stm = pieces_from_fen(fen)
        acc_w, acc_b = self._accumulators(pieces)
        stm_acc = acc_w if stm == 0 else acc_b
        nstm_acc = acc_b if stm == 0 else acc_w
        if self.simple:
            return self._simple_int(stm_acc, nstm_acc)
        if self.hl:
            return self._hl_int(stm_acc, nstm_acc)
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
        if self.hl:
            act = []
            for acc in (stm_acc, nstm_acc):
                for x in acc:
                    c = max(0.0, min(qa, float(x)))
                    act.append(c * c)
            width = 2 * self.hidden
            h = [0.0] * HL
            for j in range(HL):
                base = j * width
                pre = sum(act[i] * self.hl_w1[base + i] for i in range(width)) / qa + self.hl_b1[j]
                x = max(0.0, min(qa, pre / qb))
                h[j] = x * x
            total = sum(h[j] * self.hl_w2[j] for j in range(HL)) / qa + self.hl_b2
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
        h2pre = [0.0] * L2
        for j in range(L2):
            s = sum(pair[i] * self.l1w[bucket][j][i] for i in range(HIDDEN))
            h2pre[j] = s / qa + self.l1b[bucket][j]
        h2 = [0.0] * L2_ACT
        for j in range(L2):
            x = max(0.0, min(qa, h2pre[j] / qb))
            h2[j] = x
            h2[L2 + j] = x * x / qa
        skip = (h2[L2 - 2] - h2[L2 - 1]) * qb
        h3pre = [0.0] * L3
        for j in range(L3):
            s = sum(h2[i] * self.l2w[bucket][j][i] for i in range(L2_ACT))
            h3pre[j] = s / qa + self.l2b[bucket][j]
        h3 = [0.0] * L3_ACT
        for j in range(L3):
            x = max(0.0, min(qa, h3pre[j] / qb))
            h3[j] = x
            h3[L3 + j] = x * x / qa
        total = sum(h3[i] * self.l3w[bucket][i] for i in range(L3_ACT))
        total = total / qa + self.l3b[bucket] + skip
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
    parser.add_argument("--max-abs-cp", type=float, default=8.0)
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
