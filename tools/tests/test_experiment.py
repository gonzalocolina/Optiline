from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from experiment_common import paired_schedule  # noqa: E402
from sprt import llr, pentanomial_llr  # noqa: E402
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

    def test_pentanomial_sprt_direction(self) -> None:
        self.assertGreater(pentanomial_llr([1, 2, 4, 8, 12], -5, 5), 0.0)
        self.assertLess(pentanomial_llr([12, 8, 4, 2, 1], -5, 5), 0.0)
        self.assertAlmostEqual(pentanomial_llr([0, 0, 20, 0, 0], -5, 5), 0.0)

    def test_pentanomial_does_not_explode_on_one_pair(self) -> None:
        # A 0.75 pair used to yield LLR ≈ 3500 and stop SPRT after two games.
        self.assertLess(abs(pentanomial_llr([0, 0, 0, 1, 0], -5, 5)), 1.0)
        self.assertLess(abs(pentanomial_llr([0, 0, 0, 0, 1], -5, 5)), 1.0)


class FitControllerTest(unittest.TestCase):
    def test_fits_nscectl2_from_synthetic_telemetry(self) -> None:
        import struct
        from pathlib import Path

        out = Path("/tmp/nsce_ctl2_synth.bin")
        packed = struct.pack(
            "<8s10i",
            b"NSCECTL2",
            40,
            50,
            1,
            20,
            -1,
            -120,
            10,
            -8,
            12,
            0,
        )
        out.write_bytes(packed)
        raw = out.read_bytes()
        self.assertTrue(raw.startswith(b"NSCECTL2"))
        self.assertEqual(len(raw), 8 + 10 * 4)


if __name__ == "__main__":
    unittest.main()
