from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import pack_nsceper1 as pack  # noqa: E402


class PackNsceper1Test(unittest.TestCase):
    def test_header_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "l0w").write_bytes(b"\x00\x00" * (pack.FEATURES * pack.HIDDEN))
            (d / "l0b").write_bytes(b"\x00\x00" * pack.HIDDEN)
            (d / "l1w").write_bytes(b"\x00\x00" * (pack.BUCKETS * 2 * pack.HIDDEN))
            (d / "l1b").write_bytes(b"\x00\x00\x00\x00" * pack.BUCKETS)
            out = d / "nsceper1.bin"
            sys.argv = [
                "pack_nsceper1.py",
                "--l0w",
                str(d / "l0w"),
                "--l0b",
                str(d / "l0b"),
                "--l1w",
                str(d / "l1w"),
                "--l1b",
                str(d / "l1b"),
                "-o",
                str(out),
            ]
            self.assertEqual(pack.main(), 0)
            data = out.read_bytes()
            self.assertEqual(data[:8], b"NSCEPER1")
            hidden, features, buckets, qa, qb, scale = struct.unpack_from("<6i", data, 8)
            self.assertEqual((hidden, features, buckets, qa, qb, scale), (512, 768, 8, 255, 64, 400))
            expected = 8 + 24 + (768 * 512 * 2) + (512 * 2) + (8 * 2 * 512 * 2) + (8 * 4)
            self.assertEqual(len(data), expected)


    def test_pack_from_quantised_sign_extends_bias(self) -> None:
        l0w = b"\x00\x00" * (pack.FEATURES * pack.HIDDEN)
        l0b = b"\x00\x00" * pack.HIDDEN
        l1w = b"\x00\x00" * (pack.BUCKETS * 2 * pack.HIDDEN)
        l1b16 = struct.pack("<8h", 1, 2, 3, 4, 5, 6, 7, -8)
        padded = l0w + l0b + l1w + l1b16 + b"bullet" * 8
        got_l0w, got_l0b, got_l1w, got_l1b = pack.pack_from_quantised(padded)
        self.assertEqual(got_l0w, l0w)
        self.assertEqual(got_l1w, l1w)
        self.assertEqual(struct.unpack("<8i", got_l1b), (1, 2, 3, 4, 5, 6, 7, -8))


if __name__ == "__main__":
    unittest.main()
