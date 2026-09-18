"""Sample-check live/finished gen0.bin without reading the whole file."""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN0 = ROOT / "train/data/gen0.bin"
RECORD = struct.Struct("<Q16sh6B")  # occ, pcs[16], score, result, ksq, opp_ksq, extra[3]


def _check_record(raw: bytes, idx: int) -> None:
    occ, pcs, score, result, ksq, opp_ksq, *_ = RECORD.unpack(raw)
    pop = occ.bit_count()
    if pop < 2 or pop > 32:
        raise AssertionError(f"record {idx}: occ popcount {pop}")
    if result not in (0, 1, 2):
        raise AssertionError(f"record {idx}: result {result}")
    if ksq >= 64 or opp_ksq >= 64:
        raise AssertionError(f"record {idx}: ksq={ksq} opp_ksq={opp_ksq}")
    if not (occ & (1 << ksq)):
        raise AssertionError(f"record {idx}: ksq {ksq} not in occ")
    if abs(score) > 30000:
        raise AssertionError(f"record {idx}: score {score}")
    kings = [0, 0]
    for i in range(pop):
        byte = pcs[i // 2]
        nibble = (byte >> (4 * (i & 1))) & 0x0F
        piece = nibble & 7
        colour = (nibble >> 3) & 1
        if piece > 5:
            raise AssertionError(f"record {idx}: piece {piece} at slot {i}")
        if piece == 5:
            kings[colour] += 1
    if kings != [1, 1]:
        raise AssertionError(f"record {idx}: kings {kings}")


class Gen0BulletFormatTest(unittest.TestCase):
    def test_aligned_samples_are_valid_chessboards(self) -> None:
        if not GEN0.is_file() or GEN0.stat().st_size < 32:
            self.skipTest("train/data/gen0.bin missing")
        size = GEN0.stat().st_size
        self.assertEqual(size % 32, 0)
        nrec = size // 32
        # Leave the last ~2 MiB; the live writer keeps per-thread 1 MiB buffers.
        usable = max(1, nrec - (2 * 1024 * 1024 // 32))
        offsets = [0, usable // 3, (2 * usable) // 3, usable - 1]
        with GEN0.open("rb") as fh:
            for idx in offsets:
                fh.seek(idx * 32)
                raw = fh.read(32)
                self.assertEqual(len(raw), 32, idx)
                _check_record(raw, idx)
            # 256 stride samples through the usable prefix
            step = max(1, usable // 256)
            for i in range(0, usable, step):
                fh.seek(i * 32)
                raw = fh.read(32)
                self.assertEqual(len(raw), 32, i)
                _check_record(raw, i)


if __name__ == "__main__":
    unittest.main()
