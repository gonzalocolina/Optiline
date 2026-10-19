from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import pack_nsceper1 as pack  # noqa: E402
from per1_float_ref import Per1Net  # noqa: E402
from per1_pair_stats import pair_stats  # noqa: E402

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _blobs(b0: list[int]) -> tuple[bytes, ...]:
    return (
        b"\x00\x00" * (pack.FEATURES * pack.HIDDEN),
        struct.pack("<" + "h" * pack.HIDDEN, *b0),
        b"\x00\x00" * (pack.BUCKETS * pack.L2 * pack.HIDDEN),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L2),
        b"\x00\x00" * (pack.BUCKETS * pack.L3 * pack.L2_ACT),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L3),
        b"\x00\x00" * (pack.BUCKETS * pack.L3_ACT),
        b"\x00\x00\x00\x00" * pack.BUCKETS,
    )


class PairStatsTest(unittest.TestCase):
    def test_zero_accumulator_is_all_dead_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "z.bin"
            pack.write_per1(path, *_blobs([0] * pack.HIDDEN))
            stats = pair_stats(Per1Net(path), [STARTPOS])
            self.assertEqual(stats["pair_factor_zero"], 1.0)
            self.assertEqual(stats["pair_quant_zero"], 1.0)
            self.assertEqual(stats["half_saturated"], 1.0)
            self.assertEqual(stats["l2_saturated"], 1.0)

    def test_unit_halves_have_no_zero_product(self) -> None:
        b0 = [0] * pack.HIDDEN
        for i in range(pack.HIDDEN):
            b0[i] = pack.QA
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.bin"
            pack.write_per1(path, *_blobs(b0))
            stats = pair_stats(Per1Net(path), [STARTPOS])
            self.assertEqual(stats["pair_factor_zero"], 0.0)
            self.assertEqual(stats["pair_quant_zero"], 0.0)
            self.assertEqual(stats["half_saturated"], 1.0)


if __name__ == "__main__":
    unittest.main()
