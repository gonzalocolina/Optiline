from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from jsonl_to_bullet import RECORD, fen_bitboards, fen_to_record, to_bullet  # noqa: E402

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


class BulletPackTest(unittest.TestCase):
    def test_record_is_32_bytes(self) -> None:
        raw = fen_to_record(STARTPOS, 80)
        self.assertEqual(len(raw), 32)
        self.assertEqual(RECORD.size, 32)

    def test_startpos_kings_and_popcount(self) -> None:
        occ, pcs, score, result, ksq, opp_ksq, *_ = RECORD.unpack(fen_to_record(STARTPOS, 42))
        self.assertEqual(occ.bit_count(), 32)
        self.assertEqual(ksq, 4)
        self.assertEqual(opp_ksq, 4)
        self.assertEqual(score, 42)
        self.assertEqual(result, 1)
        self.assertTrue(occ & (1 << ksq))

    def test_black_to_move_negates_score_and_flips(self) -> None:
        occ_w, _, score_w, _, _, _, *_ = RECORD.unpack(fen_to_record(STARTPOS, 80))
        occ_b, _, score_b, _, _, _, *_ = RECORD.unpack(fen_to_record(E4, 80))
        self.assertEqual(score_w, 80)
        self.assertEqual(score_b, -80)
        self.assertEqual(occ_w.bit_count(), 32)
        self.assertEqual(occ_b.bit_count(), 32)

    def test_refuses_missing_kings(self) -> None:
        bbs, stm = fen_bitboards(STARTPOS)
        bbs[7] = 0
        with self.assertRaises(ValueError):
            to_bullet(bbs, stm, 0)

    def test_roundtrip_file_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "boards.bin"
            path.write_bytes(fen_to_record(STARTPOS, 10) + fen_to_record(E4, -3))
            self.assertEqual(path.stat().st_size, 64)
            self.assertEqual(path.stat().st_size % 32, 0)


if __name__ == "__main__":
    unittest.main()
