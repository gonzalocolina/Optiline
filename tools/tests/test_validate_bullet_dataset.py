from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from train_identity import split_games  # noqa: E402
from validate_bullet_dataset import production_cost, split_errors, summarize  # noqa: E402


def _record(game: int, score: int = 12, result: int = 2) -> bytes:
    raw = bytearray(32)
    # Kings on a1 and h8, both occupied.
    occ = (1 << 0) | (1 << 63)
    struct.pack_into("<Q", raw, 0, occ)
    struct.pack_into("<hBBB", raw, 24, score, result, 0, 63 ^ 56)
    raw[29] = game & 0xFF
    raw[30] = (game >> 8) & 0xFF
    raw[31] = (game >> 16) & 0xFF
    return bytes(raw)


class ValidateBulletDatasetTest(unittest.TestCase):
    def test_summary_rejects_a_bad_result_and_accepts_stamped_games(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ok.bin"
            path.write_bytes(_record(0) + _record(1) + _record(1))
            summary = summarize(path)
            self.assertEqual(summary["positions"], 3)
            self.assertEqual(summary["games"], 2)
            self.assertEqual(summary["errors"], [])
            self.assertFalse(summary["only_game_zero"])
            bad = Path(tmp) / "bad.bin"
            bad.write_bytes(_record(3, result=7))
            self.assertTrue(summarize(bad)["errors"])

    def test_split_keeps_every_source_game_in_exactly_one_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "all.bin"
            source.write_bytes(b"".join(_record(game) for game in range(10) for _ in range(2)))
            train = root / "train.bin"
            test = root / "test.bin"
            split_games(source, train, test, 0.2, seed=3)
            self.assertEqual(split_errors(source, train, test), [])
            self.assertEqual(summarize(train)["errors"], [])
            self.assertEqual(summarize(test)["errors"], [])

    def test_unmarked_source_cannot_prove_independence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "old.bin"
            source.write_bytes(_record(0) + _record(0))
            train = root / "train.bin"
            test = root / "test.bin"
            train.write_bytes(_record(0))
            test.write_bytes(_record(0))
            errors = split_errors(source, train, test)
            self.assertTrue(any("no per-game ids" in error for error in errors))

    def test_cost_scales_from_the_measured_rate(self) -> None:
        cost = production_cost(1000, 10, 10.0, 4, 100_000_000, 1_200_000)
        self.assertEqual(cost["positions_per_sec"], 100.0)
        self.assertAlmostEqual(cost["hours_for_target_positions"], 100_000_000 / 100 / 3600)
        self.assertAlmostEqual(cost["hours_for_target_games"], 1_200_000 / 1 / 3600)


if __name__ == "__main__":
    unittest.main()
