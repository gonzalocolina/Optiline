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

    def test_bucketed_simple_keeps_rows_and_i32_biases(self) -> None:
        hidden, buckets = 768, pack.BUCKETS
        l0w = b"\x00\x00" * (pack.FEATURES * hidden)
        l0b = b"\x00\x00" * hidden
        # Row b holds the value b + 1, so a transposed or shifted layout shows.
        l1w = b"".join(struct.pack("<h", b + 1) * (2 * hidden) for b in range(buckets))
        # 70000 does not fit i16: bullet writes these biases as i32.
        l1b = struct.pack(f"<{buckets}i", 70000, -70000, 3, 4, 5, 6, 7, -8)
        raw = l0w + l0b + l1w + l1b
        raw += b"\x00" * (-len(raw) % 64)
        blobs = pack.pack_from_quantised_simple_buckets(raw, hidden, buckets)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "simple_buckets.bin"
            pack.write_per1_simple_buckets(out, hidden, buckets, *blobs)
            data = out.read_bytes()
        self.assertEqual(struct.unpack_from("<8i", data, 8), (768, 768, 8, 0, 0, 255, 64, 400))
        self.assertEqual(len(data), pack.expected_size_simple(hidden, buckets))
        rows = 8 + 32 + pack.FEATURES * hidden * 2 + hidden * 2
        for b in range(buckets):
            row = struct.unpack_from(f"<{2 * hidden}h", data, rows + b * 2 * hidden * 2)
            self.assertEqual(set(row), {b + 1})
        biases = struct.unpack_from(f"<{buckets}i", data, rows + buckets * 2 * hidden * 2)
        self.assertEqual(biases, (70000, -70000, 3, 4, 5, 6, 7, -8))

    def test_bucketed_simple_rejects_another_width(self) -> None:
        hidden, buckets = 512, pack.BUCKETS
        raw = b"\x00" * (pack.expected_size_simple(hidden, buckets) - 40)
        raw += b"\x00" * (-len(raw) % 64)
        with self.assertRaises(ValueError):
            pack.pack_from_quantised_simple_buckets(raw, 768, buckets)
        with self.assertRaises(ValueError):
            pack.pack_from_quantised_simple_buckets(raw, 256, buckets)


if __name__ == "__main__":
    unittest.main()
