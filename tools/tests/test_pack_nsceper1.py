from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import pack_nsceper1 as pack  # noqa: E402


def _zeros() -> tuple[bytes, ...]:
    return (
        b"\x00\x00" * (pack.FEATURES * pack.HIDDEN),
        b"\x00\x00" * pack.HIDDEN,
        b"\x00\x00" * (pack.BUCKETS * pack.L2 * pack.HIDDEN),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L2),
        b"\x00\x00" * (pack.BUCKETS * pack.L3 * pack.L2_ACT),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L3),
        b"\x00\x00" * (pack.BUCKETS * pack.L3_ACT),
        b"\x00\x00\x00\x00" * pack.BUCKETS,
    )


class PackNsceper1Test(unittest.TestCase):
    def test_header_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nsceper1.bin"
            pack.write_per1(out, *_zeros())
            data = out.read_bytes()
            self.assertEqual(data[:8], b"NSCEPER1")
            hidden, features, buckets, l2, l3, qa, qb, scale = struct.unpack_from("<8i", data, 8)
            self.assertEqual(
                (hidden, features, buckets, l2, l3, qa, qb, scale),
                (512, 768, 8, 32, 32, 255, 64, 400),
            )
            self.assertEqual(len(data), pack.expected_size())

    def test_pack_from_quantised_sign_extends_bias(self) -> None:
        l0w = b"\x00\x00" * (pack.FEATURES * pack.HIDDEN)
        l0b = b"\x00\x00" * pack.HIDDEN
        l1w = b"\x00\x00" * (pack.BUCKETS * pack.L2 * pack.HIDDEN)
        l1b16 = struct.pack(f"<{pack.BUCKETS * pack.L2}h", *([0] * (pack.BUCKETS * pack.L2 - 8) + [1, 2, 3, 4, 5, 6, 7, -8]))
        l2w = b"\x00\x00" * (pack.BUCKETS * pack.L3 * pack.L2_ACT)
        l2b16 = b"\x00\x00" * (pack.BUCKETS * pack.L3)
        l3w = b"\x00\x00" * (pack.BUCKETS * pack.L3_ACT)
        l3b16 = struct.pack("<8h", 1, 2, 3, 4, 5, 6, 7, -8)
        padded = l0w + l0b + l1w + l1b16 + l2w + l2b16 + l3w + l3b16 + b"bullet" * 8
        blobs = pack.pack_from_quantised(padded)
        self.assertEqual(blobs[0], l0w)
        self.assertEqual(blobs[2], l1w)
        self.assertEqual(struct.unpack("<8i", blobs[7]), (1, 2, 3, 4, 5, 6, 7, -8))

    def test_simple_header_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "simple.bin"
            pack.write_per1_simple(
                out,
                b"\x00\x00" * (pack.FEATURES * pack.SIMPLE_HIDDEN),
                b"\x00\x00" * pack.SIMPLE_HIDDEN,
                b"\x00\x00" * (2 * pack.SIMPLE_HIDDEN),
                struct.pack("<i", 0),
            )
            data = out.read_bytes()
            self.assertEqual(data[:8], b"NSCEPER1")
            hidden, features, buckets, l2, l3, qa, qb, scale = struct.unpack_from("<8i", data, 8)
            self.assertEqual((hidden, features, buckets, l2, l3), (512, 768, 0, 0, 0))
            self.assertEqual((qa, qb, scale), (255, 64, 400))
            self.assertEqual(len(data), pack.expected_size_simple())

    def test_pack_from_quantised_simple_widens_bias(self) -> None:
        l0w = b"\x00\x00" * (pack.FEATURES * pack.SIMPLE_HIDDEN)
        l0b = b"\x00\x00" * pack.SIMPLE_HIDDEN
        l1w = b"\x00\x00" * (2 * pack.SIMPLE_HIDDEN)
        l1b16 = struct.pack("<h", -8)
        blobs = pack.pack_from_quantised_simple(l0w + l0b + l1w + l1b16 + b"pad")
        self.assertEqual(struct.unpack("<i", blobs[3]), (-8,))


if __name__ == "__main__":
    unittest.main()
