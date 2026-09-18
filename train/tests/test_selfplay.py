from __future__ import annotations

import sys
import unittest
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAIN))

from selfplay import (  # noqa: E402
    color_flip_fen,
    completed_schedule_indices,
    format_duration,
    game_schedule,
    load_games,
    position_payload,
    terminal_result,
)


class TerminalResultTest(unittest.TestCase):
    def test_checkmate_uses_the_side_that_just_moved(self) -> None:
        self.assertEqual(terminal_result("checkmate", 0), ("1-0", "checkmate"))
        self.assertEqual(terminal_result("checkmate", 1), ("0-1", "checkmate"))

    def test_draw_and_stalemate_are_draws(self) -> None:
        self.assertEqual(terminal_result("draw", 10), ("1/2-1/2", "draw"))
        self.assertEqual(terminal_result("stalemate", 10), ("1/2-1/2", "stalemate"))

    def test_ongoing_is_not_a_draw(self) -> None:
        self.assertEqual(terminal_result("ongoing", 59), (None, "ongoing"))


class PositionPayloadTest(unittest.TestCase):
    def test_omits_result_when_the_game_was_cut_off(self) -> None:
        game = {"result": None, "termination": "max_plies"}
        payload = position_payload("fen", game, "selfplay:0", 12)
        self.assertNotIn("result", payload)
        self.assertEqual(payload["termination"], "max_plies")

    def test_keeps_a_real_result(self) -> None:
        game = {"result": "1-0", "termination": "checkmate"}
        payload = position_payload("fen", game, "selfplay:1", 40)
        self.assertEqual(payload["result"], "1-0")


class ColorFlipTest(unittest.TestCase):
    def test_startpos_placement_is_symmetric_but_stm_flips(self) -> None:
        start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        flipped = color_flip_fen(start)
        self.assertEqual(flipped.split()[0], start.split()[0])
        self.assertEqual(flipped.split()[1], "b")
        self.assertEqual(color_flip_fen(flipped), start)

    def test_e4_flips_to_e5(self) -> None:
        e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        flipped = color_flip_fen(e4)
        self.assertEqual(flipped, "rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR w KQkq e6 0 1")
        self.assertEqual(color_flip_fen(flipped), e4)

    def test_both_colors_pairs_each_opening(self) -> None:
        openings = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        ]
        schedule = game_schedule(openings, 4, True)
        self.assertEqual([row[0] for row in schedule], [0, 0, 1, 1])
        self.assertEqual([row[2] for row in schedule], ["as_written", "flipped", "as_written", "flipped"])
        self.assertEqual(schedule[0][1], openings[0])
        self.assertEqual(schedule[1][1], color_flip_fen(openings[0]))
        self.assertEqual(schedule[3][1], color_flip_fen(openings[1]))

    def test_both_colors_rejects_odd_games(self) -> None:
        with self.assertRaises(ValueError):
            game_schedule(["fen"], 3, True)


class LoadGamesTest(unittest.TestCase):
    def test_drops_a_truncated_last_line(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.jsonl"
            path.write_text('{"fen": "a", "result": "1-0"}\n{"fen": "b", "res', encoding="utf-8")
            games = load_games(path)
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0]["fen"], "a")


class ResumeIndexTest(unittest.TestCase):
    def test_legacy_file_order_is_0_through_n_minus_1(self) -> None:
        games = [{"result": "1-0"}, {"result": "0-1"}]
        self.assertEqual(completed_schedule_indices(games), {0, 1})

    def test_stamped_indices_can_have_holes(self) -> None:
        games = [
            {"result": "1-0"},
            {"result": "0-1"},
            {"schedule_index": 5, "result": "*"},
        ]
        self.assertEqual(completed_schedule_indices(games), {0, 1, 5})


class FormatDurationTest(unittest.TestCase):
    def test_minutes_and_seconds(self) -> None:
        self.assertEqual(format_duration(5), "5s")
        self.assertEqual(format_duration(65), "1m05s")
        self.assertEqual(format_duration(3661), "1h01m")


if __name__ == "__main__":
    unittest.main()
