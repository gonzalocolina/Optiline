import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastchess_match import parse_summary  # noqa: E402

FINAL = """Results of final1024 vs base768 (8+0.08, 1t, 16MB, openings_balanced.epd):
Elo: 5957.30 +/- 39.70, nElo: 5957.30 +/- 39.70
LOS: 100.00 %, DrawRatio: 0.00 %, PairsRatio: inf
Games: 294, Wins: 293, Losses: 0, Draws: 1, Points: 293.5 (99.83 %)
Ptnml(0-2): [0, 0, 0, 1, 146], WL/DD Ratio: 0.00
LLR: 2.96 (100.4%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
"""


class FastchessSummaryTest(unittest.TestCase):
    def test_reads_llr_with_percentage_and_the_accepted_hypothesis(self) -> None:
        out = parse_summary(FINAL)
        self.assertEqual(out["llr"], 2.96)
        self.assertEqual(out["llr_bounds"], [-2.94, 2.94])
        self.assertEqual(out["sprt_decision"], "H1")
        self.assertEqual(out["W"], 293)

    def test_unfinished_sprt_stays_inconclusive(self) -> None:
        text = FINAL.replace("SPRT ([0.00, 5.00]) completed - H1 was accepted\n", "")
        self.assertEqual(parse_summary(text)["sprt_decision"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
