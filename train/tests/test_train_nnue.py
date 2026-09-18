from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

TRAIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAIN))

from train_nnue import (  # noqa: E402
    _sparse_forward,
    _sparse_variant,
    augment_training,
    encode_fen,
    hce_internal_weights,
    pack_active_rows,
    train_sparse,
)


def _board_fen(pieces: dict[tuple[int, int], str]) -> str:
    rows = []
    for rank in range(7, -1, -1):
        row = ""
        empty = 0
        for file in range(8):
            piece = pieces.get((file, rank))
            if piece is None:
                empty += 1
                continue
            if empty:
                row += str(empty)
                empty = 0
            row += piece
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows) + " w - - 0 1"


def _toy_fens(count: int = 80) -> list[str]:
    fens = []
    extras = "QRBNP"
    for index in range(count):
        white_file, white_rank = index % 8, 1 + (index % 6)
        pieces = {(4, 0): "K", (4, 7): "k", (white_file, white_rank): extras[index % len(extras)]}
        fens.append(_board_fen(pieces))
    return fens


def _labeled(fens: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x = np.stack([encode_fen(fen) for fen in fens])
    rows = [np.flatnonzero(row).astype(np.int32) for row in x]
    prediction, *_ = _sparse_forward(rows, *hce_internal_weights(), True)
    return x, prediction.astype(np.float32)


class AugmentContractTest(unittest.TestCase):
    def test_augment_lengths(self) -> None:
        x = np.zeros((5, 768), dtype=np.float32)
        y = np.arange(5, dtype=np.float32)
        none_x, none_y = augment_training(x, y, "none")
        mirror_x, mirror_y = augment_training(x, y, "mirror")
        full_x, full_y = augment_training(x, y, "full")
        self.assertEqual(len(none_x), 5)
        self.assertEqual(len(mirror_x), 10)
        self.assertEqual(len(full_x), 20)
        np.testing.assert_array_equal(none_y, y)
        np.testing.assert_array_equal(mirror_y, np.concatenate([y, y]))
        np.testing.assert_array_equal(full_y, np.concatenate([y, y, -y, -y]))

    def test_color_flip_is_not_odd_on_relu_hce(self) -> None:
        fen = _board_fen({(4, 0): "K", (4, 7): "k", (4, 1): "P"})
        indices = np.flatnonzero(encode_fen(fen)).astype(np.int32)
        init = hce_internal_weights()
        identity, *_ = _sparse_forward([indices], *init, True)
        flipped, *_ = _sparse_forward([_sparse_variant(indices, 2)], *init, True)
        self.assertLess(float(np.abs(identity[0])), 400.0)
        self.assertGreater(float(np.abs(flipped[0] + identity[0])), 50.0)

    def test_mirror_stays_close_on_internal(self) -> None:
        fen = _board_fen({(4, 0): "K", (4, 7): "k", (4, 1): "P"})
        indices = np.flatnonzero(encode_fen(fen)).astype(np.int32)
        init = hce_internal_weights()
        identity, *_ = _sparse_forward([indices], *init, True)
        mirrored, *_ = _sparse_forward([_sparse_variant(indices, 1)], *init, True)
        self.assertLess(float(np.abs(mirrored[0] - identity[0])), 5.0)


class PackActiveRowsTest(unittest.TestCase):
    def test_matches_per_row_flatnonzero_including_empty(self) -> None:
        x = np.zeros((5, 8), dtype=np.float32)
        x[0, [1, 4]] = 1.0
        x[2, 0] = 1.0
        x[4, [2, 3, 7]] = 1.0
        packed = pack_active_rows(x)
        expected = [np.flatnonzero(row).astype(np.int32) for row in x]
        self.assertEqual(len(packed), 5)
        for got, want in zip(packed, expected):
            np.testing.assert_array_equal(got, want)

    def test_empty_matrix(self) -> None:
        self.assertEqual(pack_active_rows(np.zeros((0, 8), dtype=np.float32)), [])


class StayOnTeacherTest(unittest.TestCase):
    def test_identity_init_matches_its_own_forward(self) -> None:
        x, y = _labeled(_toy_fens(32))
        pred, *_ = _sparse_forward(
            [np.flatnonzero(row).astype(np.int32) for row in x],
            *hce_internal_weights(),
            True,
        )
        self.assertLess(float(np.mean(np.abs(pred - y))), 1e-5)

    def test_color_flip_targets_are_far_from_relu_hce(self) -> None:
        x, y = _labeled(_toy_fens(32))
        rows = [np.flatnonzero(row).astype(np.int32) for row in x]
        flipped, *_ = _sparse_forward(
            [_sparse_variant(row, 2) for row in rows], *hce_internal_weights(), True
        )
        self.assertGreater(float(np.mean(np.abs(flipped + y))), 100.0)

    def test_keeps_epoch_zero_when_a_later_epoch_is_worse(self) -> None:
        x, y = _labeled(_toy_fens(80))
        w0, b0, w1, b1, report = train_sparse(
            x, y, np.arange(64), np.arange(64, 80),
            epochs=4, batch_size=16, learning_rate=0.01, seed=1,
            init=hce_internal_weights(), augment="none",
        )
        self.assertEqual(report["history"][0]["epoch"], 0)
        self.assertLess(report["history"][0]["validation_mae_cp"], 1.0)
        self.assertEqual(report["best_epoch"], 0)
        restored, *_ = _sparse_forward(
            [np.flatnonzero(row).astype(np.int32) for row in x[64:80]],
            w0, b0, w1, b1,
            True,
        )
        self.assertLess(float(np.mean(np.abs(restored - y[64:80]))), 1.0)

    def test_real_clone_leaves_color_flip_is_far(self) -> None:
        path = TRAIN / "data/nsce_static_clone.jsonl"
        if not path.exists():
            self.skipTest("clone labels missing")
        from train_nnue import load_dataset

        x, y, _fens, _digest = load_dataset(path, 2000.0, "cp", residualize_extras=True)
        sample = slice(0, 512)
        rows = [np.flatnonzero(row).astype(np.int32) for row in x[sample]]
        init = hce_internal_weights()
        identity, *_ = _sparse_forward(rows, *init, True)
        flipped, *_ = _sparse_forward([_sparse_variant(row, 2) for row in rows], *init, True)
        self.assertLess(float(np.mean(np.abs(identity - y[sample]))), 1.0)
        self.assertGreater(float(np.mean(np.abs(flipped + y[sample]))), 100.0)


if __name__ == "__main__":
    unittest.main()
