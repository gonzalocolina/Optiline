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
    SCALE,
    adamw_step,
    decode_records,
    forward,
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

    def test_huber_gradient_matches_finite_difference(self) -> None:
        stm, ntm, scores = decode_records(fen_to_record(STARTPOS, 80) * 4)
        params = init_params(np.random.default_rng(2))
        loss, grads = loss_and_grads(params, stm, ntm, scores, window=0.0)
        eps = 1e-3
        params["l2b"][0] += eps
        shifted, _ = loss_and_grads(params, stm, ntm, scores, window=0.0)
        params["l2b"][0] -= eps
        self.assertAlmostEqual((shifted - loss) / eps, float(grads["l2b"][0]), places=3)
        # A positive label must push the logit up when the net still outputs ~0.
        self.assertLess(float(grads["l2b"][0]), 0.0)

    def test_material_holdout_mean_cp_error_below_50(self) -> None:
        values = {
            "P": 100, "N": 320, "B": 330, "R": 500, "Q": 900,
            "p": -100, "n": -320, "b": -330, "r": -500, "q": -900,
        }

        def dataset(n: int, seed: int):
            rng = np.random.default_rng(seed)
            records = []
            for _ in range(n):
                board = [["."] * 8 for _ in range(8)]
                board[0][4] = "K"
                board[7][4] = "k"
                squares = [sq for sq in range(64) if sq not in (4, 60)]
                rng.shuffle(squares)
                cursor = 0
                cp = 0
                for piece, hi in (
                    ("P", 8), ("p", 8), ("N", 2), ("n", 2), ("B", 2), ("b", 2),
                    ("R", 2), ("r", 2), ("Q", 1), ("q", 1),
                ):
                    for _ in range(int(rng.integers(0, hi + 1))):
                        sq = squares[cursor]
                        cursor += 1
                        rank, file = divmod(sq, 8)
                        board[rank][file] = piece
                        cp += values[piece]
                rows = []
                for rank in range(7, -1, -1):
                    empty = 0
                    text = ""
                    for file in range(8):
                        if board[rank][file] == ".":
                            empty += 1
                            continue
                        if empty:
                            text += str(empty)
                            empty = 0
                        text += board[rank][file]
                    if empty:
                        text += str(empty)
                    rows.append(text)
                records.append(fen_to_record("/".join(rows) + " w - - 0 1", int(cp)))
            return decode_records(b"".join(records))

        train = dataset(8000, 1)
        hold = dataset(500, 9)
        stm, ntm, scores = train
        params = init_params(np.random.default_rng(1))
        moments = {name: np.zeros_like(value) for name, value in params.items()}
        velocity = {name: np.zeros_like(value) for name, value in params.items()}
        order = np.arange(stm.shape[0])
        rng = np.random.default_rng(3)
        batch = 512
        for _ in range(12):
            rng.shuffle(order)
            for step in range(len(order) // batch):
                pick = order[step * batch : (step + 1) * batch]
                _, grads = loss_and_grads(params, stm[pick], ntm[pick], scores[pick], window=0.05)
                adamw_step(params, grads, moments, velocity, 0.001)
        hold_stm, hold_ntm, hold_scores = hold
        pred = forward(params, hold_stm, hold_ntm)["logit"].reshape(-1) * SCALE
        mae = float(np.mean(np.abs(pred - hold_scores)))
        self.assertLess(mae, 50.0)


if __name__ == "__main__":
    unittest.main()
