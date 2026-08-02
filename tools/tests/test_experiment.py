from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from experiment_common import paired_schedule  # noqa: E402
from sprt import llr  # noqa: E402
from uci_common import elo_from_wdl  # noqa: E402


class PairedScheduleTest(unittest.TestCase):
    def test_reverses_colors_for_each_opening(self) -> None:
        schedule = paired_schedule(["fen-a", "fen-b"], games=4, seed=7)
        for first, second in zip(schedule[::2], schedule[1::2]):
            self.assertEqual(first[0], second[0])
            self.assertEqual(first[1], second[1])
            self.assertTrue(first[2])
            self.assertFalse(second[2])

    def test_is_deterministic(self) -> None:
        self.assertEqual(
            paired_schedule(["a", "b", "c"], games=10, seed=42),
            paired_schedule(["a", "b", "c"], games=10, seed=42),
        )

    def test_rejects_unpaired_game_count(self) -> None:
        with self.assertRaises(ValueError):
            paired_schedule(["fen"], games=3, seed=1)


class StatisticsTest(unittest.TestCase):
    def test_all_draws_retain_uncertainty(self) -> None:
        elo, error = elo_from_wdl(0, 20, 0)
        self.assertAlmostEqual(elo, 0.0)
        self.assertGreater(error, 0.0)

    def test_sprt_direction(self) -> None:
        self.assertGreater(llr(20, 5, 10, -5, 5), 0.0)
        self.assertLess(llr(5, 20, 10, -5, 5), 0.0)


if __name__ == "__main__":
    unittest.main()
