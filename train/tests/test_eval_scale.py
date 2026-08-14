from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAIN))

from eval_scale import (  # noqa: E402
    NSCE_SEARCH_WDL_SCALE,
    cp_to_wdl,
    teacher_family,
    to_white_cp,
    training_target,
    wdl_to_search_cp,
)


class EvalScaleTest(unittest.TestCase):
    def test_nsce_roundtrip_is_identity(self) -> None:
        for cp in (-800.0, -90.0, 0.0, 42.0, 350.0):
            wdl = cp_to_wdl(cp, NSCE_SEARCH_WDL_SCALE)
            self.assertAlmostEqual(wdl_to_search_cp(wdl, NSCE_SEARCH_WDL_SCALE), cp, places=4)

    def test_stockfish_cp_is_rescaled_into_nsce_coin(self) -> None:
        teacher_cp = 200.0
        teacher_scale = 90.0
        nsce = training_target(
            teacher_cp,
            target_mode="wdl",
            teacher_wdl_scale=teacher_scale,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
        )
        expected = wdl_to_search_cp(cp_to_wdl(teacher_cp, teacher_scale), NSCE_SEARCH_WDL_SCALE)
        self.assertAlmostEqual(nsce, expected)
        self.assertGreater(abs(nsce - teacher_cp), 50.0)

    def test_residualize_extras_after_currency_conversion(self) -> None:
        teacher_cp = 200.0
        extras = 30.0
        converted = training_target(
            teacher_cp,
            target_mode="wdl",
            teacher_wdl_scale=90.0,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
        )
        residual = training_target(
            teacher_cp,
            target_mode="wdl",
            teacher_wdl_scale=90.0,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            extras_cp_white=extras,
            residualize_extras=True,
        )
        self.assertAlmostEqual(residual, converted - extras)
        peeled_first = training_target(
            teacher_cp - extras,
            target_mode="wdl",
            teacher_wdl_scale=90.0,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
        )
        self.assertGreater(abs(residual - peeled_first), 1.0)

    def test_clone_cp_mode_peels_extras_in_nsce_units(self) -> None:
        target = training_target(
            42.0,
            target_mode="cp",
            teacher_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            extras_cp_white=10.0,
            residualize_extras=True,
        )
        self.assertEqual(target, 32.0)

    def test_result_blend_lives_in_wdl_space(self) -> None:
        teacher_only = training_target(
            800.0,
            target_mode="wdl",
            teacher_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            result_white=0.0,
            result_weight=0.0,
        )
        mixed = training_target(
            800.0,
            target_mode="wdl",
            teacher_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            search_wdl_scale=NSCE_SEARCH_WDL_SCALE,
            result_white=0.0,
            result_weight=0.5,
        )
        self.assertLess(mixed, teacher_only)

    def test_black_to_move_flips_side_to_move_scores(self) -> None:
        fen = "8/8/8/8/8/8/8/8 b - - 0 1"
        self.assertEqual(to_white_cp(25.0, fen, "side_to_move"), -25.0)
        self.assertEqual(to_white_cp(25.0, fen, "white"), 25.0)

    def test_teacher_family(self) -> None:
        self.assertEqual(teacher_family({"id_name": "NSCE 0.10"}, "build/nsce"), "nsce")
        self.assertEqual(teacher_family({"id_name": "Stockfish 18"}, "stockfish"), "stockfish")
        self.assertTrue(math.isfinite(NSCE_SEARCH_WDL_SCALE))


if __name__ == "__main__":
    unittest.main()
