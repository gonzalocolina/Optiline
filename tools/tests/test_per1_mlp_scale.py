"""MLP export must match the Bullet training graph, not a second copy of a bad scale.

Bullet stores dense weights at 64 and biases at 255*64. Pair activations are
already in QA units, so the affine is (dot + bias) / QB. These tests build
that float graph from dequantized weights and compare it to the packed eval.
"""

from __future__ import annotations

import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import pack_nsceper1 as pack  # noqa: E402
from per1_float_ref import Per1Net, per1_bucket, per1_feature, pieces_from_fen  # noqa: E402

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _zero_blobs() -> list[bytes]:
    return [
        b"\x00\x00" * (pack.FEATURES * pack.HIDDEN),
        b"\x00\x00" * pack.HIDDEN,
        b"\x00\x00" * (pack.BUCKETS * pack.L2 * pack.HIDDEN),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L2),
        b"\x00\x00" * (pack.BUCKETS * pack.L3 * pack.L2_ACT),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L3),
        b"\x00\x00" * (pack.BUCKETS * pack.L3_ACT),
        b"\x00\x00\x00\x00" * pack.BUCKETS,
    ]


def _i16(values: list[int]) -> bytes:
    return struct.pack("<" + "h" * len(values), *values)


def _i32(values: list[int]) -> bytes:
    return struct.pack("<" + "i" * len(values), *values)


def _crelu(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def bullet_mlp_cp(net: Per1Net, fen: str) -> float:
    """Training graph: CReLU pair, concat(CReLU, SCReLU), skip of the last two L2 units."""
    qa = float(net.qa)
    qb = float(net.qb)
    pieces, stm = pieces_from_fen(fen)
    acc_w, acc_b = net._accumulators(pieces)
    stm_acc = acc_w if stm == 0 else acc_b
    nstm_acc = acc_b if stm == 0 else acc_w
    half = pack.HIDDEN // 2

    def pairs(acc: list[int]) -> list[float]:
        return [
            _crelu(acc[i] / qa) * _crelu(acc[half + i] / qa) for i in range(half)
        ]

    hidden = pairs(stm_acc) + pairs(nstm_acc)
    bucket = per1_bucket(len(pieces))

    def affine(rows: list[list[int]], bias: list[int], inputs: list[float]) -> list[float]:
        out = []
        for j, row in enumerate(rows):
            total = bias[j] / (qa * qb)
            total += sum((row[i] / qb) * inputs[i] for i in range(len(inputs)))
            out.append(total)
        return out

    h2 = affine(net.l1w[bucket], net.l1b[bucket], hidden)
    c2 = [_crelu(z) for z in h2]
    skip = c2[pack.L2 - 2] - c2[pack.L2 - 1]
    h3 = affine(net.l2w[bucket], net.l2b[bucket], c2 + [z * z for z in c2])
    c3 = [_crelu(z) for z in h3]
    output = net.l3b[bucket] / (qa * qb) + skip
    output += sum((net.l3w[bucket][i] / qb) * z for i, z in enumerate(c3 + [z * z for z in c3]))
    return output * net.scale


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy)


def _fen(n_pieces: int, salt: int) -> str:
    board = [None] * 64
    board[0] = "K"
    board[63] = "k"
    placed = 2
    cursor = (salt * 5 + 8) % 64
    while placed < n_pieces:
        if board[cursor] is None:
            board[cursor] = "P" if placed % 2 == 0 else "p"
            placed += 1
        cursor = (cursor + 1) % 64
    rows = []
    for rank in range(7, -1, -1):
        empty = 0
        row = []
        for file in range(8):
            piece = board[rank * 8 + file]
            if piece is None:
                empty += 1
                continue
            if empty:
                row.append(str(empty))
                empty = 0
            row.append(piece)
        if empty:
            row.append(str(empty))
        rows.append("".join(row))
    stm = "w" if salt % 2 == 0 else "b"
    return "/".join(rows) + f" {stm} - - 0 1"


class Per1MlpScaleTest(unittest.TestCase):
    def test_unit_weight_chain_matches_training_scale(self) -> None:
        blobs = _zero_blobs()
        b0 = [0] * pack.HIDDEN
        b0[0] = pack.QA
        b0[pack.HIDDEN // 2] = pack.QA
        blobs[1] = _i16(b0)
        l1w = [0] * (pack.BUCKETS * pack.L2 * pack.HIDDEN)
        l2w = [0] * (pack.BUCKETS * pack.L3 * pack.L2_ACT)
        l3w = [0] * (pack.BUCKETS * pack.L3_ACT)
        for b in range(pack.BUCKETS):
            l1w[(b * pack.L2) * pack.HIDDEN] = pack.QB
            l2w[(b * pack.L3) * pack.L2_ACT] = pack.QB
            l3w[b * pack.L3_ACT] = pack.QB
        blobs[2] = _i16(l1w)
        blobs[4] = _i16(l2w)
        blobs[6] = _i16(l3w)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.bin"
            pack.write_per1(path, *blobs)
            net = Per1Net(path)
            # Legacy (dot / QA + bias) / QB collapses this chain to 0.
            self.assertEqual(net.l2_preacts(STARTPOS)[0], pack.QA * pack.QB)
            self.assertEqual(net.eval_int(STARTPOS), pack.SCALE)
            self.assertAlmostEqual(net.eval_float(STARTPOS), float(pack.SCALE), places=5)
            self.assertAlmostEqual(bullet_mlp_cp(net, STARTPOS), float(pack.SCALE), places=5)
            engine_bin = TOOLS.parent / "build" / "nsce"
            if engine_bin.is_file():
                from uci_common import UciEngine

                engine = UciEngine([str(engine_bin)], "nsce", cwd=TOOLS.parent)
                try:
                    engine.apply_options(
                        {
                            "UseNNUE": "true",
                            "EvalFile": str(path),
                            "UseExtras": "false",
                            "Hash": "16",
                            "Threads": "1",
                        }
                    )
                    details = engine.evaluate_details(STARTPOS)
                finally:
                    engine.close()
                self.assertEqual(details["nnue"], pack.SCALE)

    def test_output_weight_is_not_divided_before_bias(self) -> None:
        blobs = _zero_blobs()
        unit = pack.QA * pack.QB
        blobs[3] = _i32([unit] * (pack.BUCKETS * pack.L2))
        blobs[5] = _i32([unit] * (pack.BUCKETS * pack.L3))
        l3w = [0] * (pack.BUCKETS * pack.L3_ACT)
        l3b = []
        for b in range(pack.BUCKETS):
            l3w[b * pack.L3_ACT] = pack.QB // 2
            l3b.append(unit // 2)
        blobs[6] = _i16(l3w)
        blobs[7] = _i32(l3b)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mix.bin"
            pack.write_per1(path, *blobs)
            net = Per1Net(path)
            self.assertEqual(net.eval_int(STARTPOS), pack.SCALE)
            self.assertAlmostEqual(bullet_mlp_cp(net, STARTPOS), float(pack.SCALE), places=5)
            parts = net.eval_parts(STARTPOS)
            self.assertEqual(parts["total"], pack.SCALE)
            self.assertEqual(parts["mlp"], pack.SCALE // 2)
            self.assertEqual(parts["l3b"], pack.SCALE // 2)
            self.assertEqual(parts["skip"], 0)

    def test_skip_stays_on_the_output_scale(self) -> None:
        blobs = _zero_blobs()
        l1b = [0] * (pack.BUCKETS * pack.L2)
        for b in range(pack.BUCKETS):
            l1b[b * pack.L2 + (pack.L2 - 2)] = pack.QA * pack.QB
        blobs[3] = _i32(l1b)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skip.bin"
            pack.write_per1(path, *blobs)
            net = Per1Net(path)
            self.assertEqual(net.eval_int(STARTPOS), pack.SCALE)
            self.assertAlmostEqual(bullet_mlp_cp(net, STARTPOS), float(pack.SCALE), places=5)
            self.assertEqual(net.eval_parts(STARTPOS)["skip"], pack.SCALE)

    def test_quantized_eval_tracks_training_graph_per_bucket(self) -> None:
        rng_state = 1

        def rnd() -> int:
            nonlocal rng_state
            rng_state = (1103515245 * rng_state + 12345) & 0x7FFFFFFF
            return rng_state

        # Factor 4 keeps the signal tens of centipawns wide. A unit factor
        # is a correct net whose values sit inside quantization noise, so
        # Pearson looks worse than the centipawn error.
        scale = 4
        w0 = [0] * (pack.FEATURES * pack.HIDDEN)
        for pc in range(12):
            for sq in range(64):
                feat = per1_feature(0, pc, sq)
                for h in (0, 1, 17, 40, 200, 256, 300, 511):
                    w0[feat * pack.HIDDEN + h] = ((rnd() % 7) - 3) * scale
        b0 = [((rnd() % 41) - 20) * scale for _ in range(pack.HIDDEN)]
        l1w = [0] * (pack.BUCKETS * pack.L2 * pack.HIDDEN)
        l1b = [((rnd() % 9) - 4) * 64 * scale for _ in range(pack.BUCKETS * pack.L2)]
        for b in range(pack.BUCKETS):
            for j in range(pack.L2):
                base = (b * pack.L2 + j) * pack.HIDDEN
                for i in range(0, pack.HIDDEN, 32):
                    l1w[base + i] = ((rnd() % 5) - 2) * scale
        l2w = [0] * (pack.BUCKETS * pack.L3 * pack.L2_ACT)
        l2b = [((rnd() % 9) - 4) * 64 * scale for _ in range(pack.BUCKETS * pack.L3)]
        for b in range(pack.BUCKETS):
            for j in range(pack.L3):
                base = (b * pack.L3 + j) * pack.L2_ACT
                for i in range(0, pack.L2_ACT, 4):
                    l2w[base + i] = ((rnd() % 5) - 2) * scale
        l3w = [0] * (pack.BUCKETS * pack.L3_ACT)
        for b in range(pack.BUCKETS):
            for i in range(0, pack.L3_ACT, 2):
                l3w[b * pack.L3_ACT + i] = ((rnd() % 5) - 2) * scale
        l3b = [((rnd() % 9) - 4) * 64 * scale for _ in range(pack.BUCKETS)]
        blobs = [
            _i16(w0),
            _i16(b0),
            _i16(l1w),
            _i32(l1b),
            _i16(l2w),
            _i32(l2b),
            _i16(l3w),
            _i32(l3b),
        ]
        fens = [_fen(2 + 4 * bucket, salt) for bucket in range(pack.BUCKETS) for salt in range(12)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rand.bin"
            pack.write_per1(path, *blobs)
            net = Per1Net(path)
            by_bucket: dict[int, list[float]] = {b: [] for b in range(pack.BUCKETS)}
            engine = []
            trained = []
            for fen in fens:
                q = net.eval_int(fen)
                ref = bullet_mlp_cp(net, fen)
                engine.append(float(q))
                trained.append(ref)
                by_bucket[per1_bucket(len(pieces_from_fen(fen)[0]))].append(abs(q - ref))
                self.assertLessEqual(abs(net.eval_float(fen) - q), 2.0)
            err = [abs(a - b) for a, b in zip(engine, trained)]
            mae = sum(err) / len(err)
            rmse = math.sqrt(sum(e * e for e in err) / len(err))
            self.assertGreater(_pearson(engine, trained), 0.998)
            self.assertLess(mae, 2.0)
            self.assertLess(rmse, 2.0)
            for bucket, errs in by_bucket.items():
                self.assertEqual(len(errs), 12, bucket)
                self.assertLess(sum(errs) / len(errs), 2.0, bucket)


if __name__ == "__main__":
    unittest.main()
