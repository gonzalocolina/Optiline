from __future__ import annotations

import sys
import unittest
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAIN))

from collect_leaves import keep_leaf, roots_from_game, stamp_leaf  # noqa: E402


class RootsFromGameTest(unittest.TestCase):
    def test_uses_opening_and_spaced_path_positions(self) -> None:
        game = {
            "fen": "start w - - 0 1",
            "result": "1-0",
            "records": [
                {"fen": "a w - - 0 1", "ply": 0},
                {"fen": "b w - - 0 1", "ply": 1},
                {"fen": "c w - - 0 1", "ply": 2},
                {"fen": "d w - - 0 1", "ply": 3},
            ],
        }
        roots = roots_from_game(game, 3)
        self.assertEqual(roots[0], "start w - - 0 1")
        self.assertEqual(len(roots), 3)
        self.assertEqual(roots[-1], "d w - - 0 1")

    def test_one_position_is_just_the_opening(self) -> None:
        game = {"fen": "start w - - 0 1", "result": "0-1", "records": [{"fen": "a w - - 0 1"}]}
        self.assertEqual(roots_from_game(game, 1), ["start w - - 0 1"])


class StampLeafTest(unittest.TestCase):
    def test_copies_result_and_source_game(self) -> None:
        game = {
            "result": "1-0",
            "termination": "checkmate",
            "opening_index": 4,
            "color": "flipped",
        }
        stamped = stamp_leaf({"fen": "x", "site": "static"}, game)
        self.assertEqual(stamped["result"], "1-0")
        self.assertEqual(stamped["source_game"], "selfplay:4")
        self.assertEqual(stamped["source"], "leaf")


class KeepLeafTest(unittest.TestCase):
    def test_dedups_by_fen_key(self) -> None:
        seen: set[str] = set()
        sites = {"static"}
        self.assertTrue(keep_leaf({"fen": "a b c d 0 1", "site": "static"}, sites, seen))
        self.assertFalse(keep_leaf({"fen": "a b c d 5 9", "site": "static"}, sites, seen))
        self.assertFalse(keep_leaf({"fen": "e f g h 0 1", "site": "q_max"}, sites, seen))


if __name__ == "__main__":
    unittest.main()
