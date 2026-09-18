from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from experiment_common import paired_schedule  # noqa: E402
from generate_uho_book import epd_line, normalized_key  # noqa: E402
from sprt import llr, pentanomial_llr  # noqa: E402
from uci_common import elo_from_wdl  # noqa: E402


class TuneSpsaMapTest(unittest.TestCase):
    def test_spsa_json_names_match_tune_header(self) -> None:
        header = (TOOLS.parent / "engine/include/nsce/tune.hpp").read_text()
        names = re.findall(r'\{\"([A-Za-z0-9]+)\", &SearchTune::', header)
        spsa = json.loads((TOOLS / "configs/spsa.json").read_text())
        self.assertEqual(sorted(names), sorted(spsa))
        self.assertGreaterEqual(len(names), 40)


class UhoBookFormatTest(unittest.TestCase):
    def test_normalized_key_drops_clocks(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        self.assertEqual(
            normalized_key(fen),
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3",
        )

    def test_epd_line_is_four_fields(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        self.assertEqual(
            epd_line(fen),
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3",
        )
        self.assertNotIn(";", epd_line(fen))

    def test_openings_uho_is_four_field_epd(self) -> None:
        path = TOOLS / "openings_uho.epd"
        lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 4096)
        for line in lines:
            parts = line.split()
            self.assertEqual(len(parts), 4, line)
            self.assertNotIn(";", line)
            self.assertIn(parts[1], ("w", "b"))


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
