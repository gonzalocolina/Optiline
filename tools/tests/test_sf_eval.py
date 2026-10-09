from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "train"))

from eval_scale import NSCE_SEARCH_WDL_SCALE, fit_logistic_scale, wdl_permille_to_winrate  # noqa: E402
from sf_eval import parse_sf_eval_report, parse_wdl_info, sfnnv16_to_nsce_cp  # noqa: E402

STARTPOS_EVAL = """
NNUE evaluation          -1 (side to move, internal units)
NNUE evaluation        +0.00 (white side)
Final evaluation      +0.00 (white side) [with scaled NNUE, ...]
""".strip().splitlines()

E4_EVAL = """
NNUE evaluation          21 (side to move, internal units)
NNUE evaluation        +0.21 (white side)
Final evaluation      +0.27 (white side) [with scaled NNUE, ...]
""".strip().splitlines()

KIWIPETE_EVAL = """
NNUE evaluation        -198 (side to move, internal units)
NNUE evaluation        -1.98 (white side)
Final evaluation      -2.48 (white side) [with scaled NNUE, ...]
""".strip().splitlines()


class SfEvalParseTest(unittest.TestCase):
    def test_startpos_nnue_white_is_zero(self) -> None:
        ev = parse_sf_eval_report(STARTPOS_EVAL)
        self.assertEqual(ev.nnue_white_cp, 0)
        self.assertEqual(ev.final_white_cp, 0)
        self.assertFalse(ev.in_check)

    def test_e4_and_kiwipete_pawn_units_become_cp(self) -> None:
        self.assertEqual(parse_sf_eval_report(E4_EVAL).nnue_white_cp, 21)
        self.assertEqual(parse_sf_eval_report(KIWIPETE_EVAL).nnue_white_cp, -198)

    def test_wdl_info_line(self) -> None:
        lines = ["info depth 1 score cp 0 wdl 18 964 18 nodes 0", "bestmove a2a3"]
        self.assertEqual(parse_wdl_info(lines), (18, 964, 18))
        self.assertAlmostEqual(wdl_permille_to_winrate(18, 964, 18), 0.5)

    def test_sfnnv16_conversion_is_not_identity(self) -> None:
        nsce = sfnnv16_to_nsce_cp(200.0, teacher_wdl_scale=90.0)
        self.assertGreater(abs(nsce - 200.0), 50.0)
        self.assertLess(abs(nsce), 2000.0)

    def test_refuses_identical_scales(self) -> None:
        with self.assertRaises(ValueError):
            sfnnv16_to_nsce_cp(100.0, teacher_wdl_scale=NSCE_SEARCH_WDL_SCALE)

    def test_fit_logistic_recovers_scale(self) -> None:
        true_s = 120.0
        cps = [-400.0, -200.0, -80.0, -20.0, 20.0, 80.0, 200.0, 400.0]
        rates = [1.0 / (1.0 + __import__("math").exp(-c / true_s)) for c in cps]
        fitted = fit_logistic_scale(cps, rates)
        self.assertLess(abs(fitted - true_s), 6.0)


class SfEvalLiveTest(unittest.TestCase):
    def test_sf19_eval_startpos(self) -> None:
        from sf_eval import DEFAULT_SF19, StockfishEvalEngine

        if not DEFAULT_SF19.is_file():
            self.skipTest("stockfish-19 missing")
        with StockfishEvalEngine(DEFAULT_SF19) as eng:
            ev = eng.eval_sfnnv16("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self.assertIsInstance(ev.nnue_white_cp, int)
        self.assertLessEqual(abs(ev.nnue_white_cp), 80)


if __name__ == "__main__":
    unittest.main()
