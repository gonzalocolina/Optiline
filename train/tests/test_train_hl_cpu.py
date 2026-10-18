from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "tools"))

from jsonl_to_bullet import fen_to_record  # noqa: E402
from train_hl_cpu import (  # noqa: E402
    FEATURES,
    FT,
    HL,
    QA,
    QB,
    decode_records,
    init_params,
    loss_and_grads,
    quantise,
)

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class TrainHlCpuTest(unittest.TestCase):
    def test_startpos_features_stay_inside_chess768(self) -> None:
        stm, ntm, scores = decode_records(fen_to_record(STARTPOS, 35))
        self.assertEqual(stm.shape, (1, 32))
        self.assertEqual(int(scores[0]), 35)
        active = stm[0][stm[0] >= 0]
        self.assertEqual(active.size, 32)
        self.assertTrue(np.all(active < FEATURES))
        self.assertTrue(np.all(ntm[0][ntm[0] >= 0] < FEATURES))
        # White pawn on a2 is square 8, side to move, piece 0.
        self.assertIn(8, active.tolist())

    def test_quantised_layout_matches_the_hl_packer(self) -> None:
        params = init_params(np.random.default_rng(1))
        raw = quantise(params)
        expected = (
            FEATURES * FT * 2
            + FT * 2
            + HL * (2 * FT) * 2
            + HL * 2
            + HL * 2
            + 2
        )
        self.assertEqual(len(raw), expected)
        self.assertEqual(QA, 255)
        self.assertEqual(QB, 64)

    def test_window_pulls_a_dead_unit_back_toward_the_interval(self) -> None:
        stm, ntm, scores = decode_records(fen_to_record(STARTPOS, 20) * 8)
        params = init_params(np.random.default_rng(0))
        params["l0b"][:] = -3.0
        _, grads = loss_and_grads(params, stm, ntm, scores, window=0.05)
        self.assertLess(float(grads["l0b"][0]), 0.0)
        _, bare = loss_and_grads(params, stm, ntm, scores, window=0.0)
        self.assertEqual(float(bare["l0b"][0]), 0.0)


if __name__ == "__main__":
    unittest.main()
