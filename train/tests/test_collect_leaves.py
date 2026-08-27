from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAIN))

from collect_leaves import (  # noqa: E402
    FenStore,
    apply_honest_result,
    keep_leaf,
    path_fen_keys,
    path_index_from_games,
    path_records_from_games,
    played_path_fens,
    roots_from_game,
    stamp_leaf,
    strip_leaf_results,
)


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

    def test_played_path_keeps_every_distinct_fen(self) -> None:
        game = {
            "fen": "start w - - 0 1",
            "records": [{"fen": "a w - - 0 1"}, {"fen": "b w - - 0 1"}],
        }
        self.assertEqual(played_path_fens(game), ["start w - - 0 1", "a w - - 0 1", "b w - - 0 1"])


class StampLeafTest(unittest.TestCase):
    def test_path_root_keeps_result(self) -> None:
        game = {
            "result": "1-0",
            "termination": "checkmate",
            "opening_index": 4,
            "color": "flipped",
        }
        stamped = stamp_leaf({"fen": "root w - - 0 1", "site": "static"}, game, "root w - - 1 2")
        self.assertEqual(stamped["result"], "1-0")
        self.assertEqual(stamped["label_kind"], "path")
        self.assertEqual(stamped["source_game"], "selfplay:4")
        self.assertEqual(stamped["source"], "leaf")

    def test_search_leaf_does_not_copy_game_wdl(self) -> None:
        game = {
            "result": "1-0",
            "termination": "checkmate",
            "opening_index": 4,
            "color": "flipped",
        }
        stamped = stamp_leaf({"fen": "leaf w - - 0 1", "site": "static", "result": "1-0"}, game, "root w - - 0 1")
        self.assertNotIn("result", stamped)
        self.assertEqual(stamped["label_kind"], "search_leaf")
        self.assertEqual(stamped["source_game"], "selfplay:4")

    def test_unfinished_path_stays_unlabeled(self) -> None:
        game = {"result": None, "termination": "max_plies", "opening_index": 1}
        stamped = stamp_leaf({"fen": "root w - - 0 1"}, game, "root w - - 0 1")
        self.assertEqual(stamped["label_kind"], "path")
        self.assertNotIn("result", stamped)


class HonestResultTest(unittest.TestCase):
    def test_strips_result_unless_fen_was_played(self) -> None:
        games = [
            {
                "fen": "start w - - 0 1",
                "result": "1-0",
                "opening_index": 2,
                "color": "as_written",
                "records": [{"fen": "mid w - - 0 1"}],
            }
        ]
        index = path_index_from_games(games)
        path = apply_honest_result(
            {"fen": "mid w - - 5 9", "opening_index": 2, "color": "as_written", "result": "1-0"},
            index,
        )
        leaf = apply_honest_result(
            {"fen": "qs w - - 0 1", "opening_index": 2, "color": "as_written", "result": "1-0"},
            index,
        )
        self.assertEqual(path["label_kind"], "path")
        self.assertEqual(path["result"], "1-0")
        self.assertEqual(leaf["label_kind"], "search_leaf")
        self.assertNotIn("result", leaf)
        self.assertEqual(path_fen_keys(games[0]), {"start w - -", "mid w - -"})

    def test_strip_leaf_results_rewrites_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            games = root / "games.jsonl"
            leaves = root / "leaves.jsonl"
            games.write_text(
                json.dumps(
                    {
                        "fen": "start w - - 0 1",
                        "result": "0-1",
                        "opening_index": 0,
                        "color": "as_written",
                        "records": [{"fen": "path w - - 0 1"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            leaves.write_text(
                json.dumps({"fen": "path w - - 0 1", "opening_index": 0, "result": "0-1"})
                + "\n"
                + json.dumps({"fen": "qs w - - 0 1", "opening_index": 0, "result": "0-1"})
                + "\n",
                encoding="utf-8",
            )
            stats = strip_leaf_results(games, leaves, leaves)
            rows = [json.loads(line) for line in leaves.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(stats["path"], 1)
            self.assertEqual(stats["search_leaf"], 1)
            self.assertEqual(stats["with_result"], 1)
            self.assertEqual(rows[0]["result"], "0-1")
            self.assertNotIn("result", rows[1])

    def test_path_records_skip_unfinished_games(self) -> None:
        games = [
            {"fen": "a w - - 0 1", "result": None, "records": [{"fen": "b w - - 0 1"}]},
            {"fen": "c w - - 0 1", "result": "1-0", "opening_index": 3, "records": [{"fen": "d w - - 0 1"}]},
        ]
        rows = path_records_from_games(games)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["label_kind"] == "path" and row["result"] == "1-0" for row in rows))


class KeepLeafTest(unittest.TestCase):
    def test_dedups_by_fen_key(self) -> None:
        seen: set[str] = set()
        sites = {"static"}
        self.assertTrue(keep_leaf({"fen": "a b c d 0 1", "site": "static"}, sites, seen))
        self.assertFalse(keep_leaf({"fen": "a b c d 5 9", "site": "static"}, sites, seen))
        self.assertFalse(keep_leaf({"fen": "e f g h 0 1", "site": "q_max"}, sites, seen))

    def test_sqlite_store_rejects_duplicate_and_remembers_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FenStore(Path(tmp) / "seen.sqlite")
            self.assertTrue(store.add_fen("a b c d"))
            self.assertFalse(store.add_fen("a b c d"))
            self.assertFalse(store.has_root(1, "as_written", "root"))
            store.add_root(1, "as_written", "root")
            store.close()
            again = FenStore(Path(tmp) / "seen.sqlite")
            self.assertTrue(again.has_root(1, "as_written", "root"))
            self.assertFalse(again.add_fen("a b c d"))
            again.close()

    def test_index_existing_records_fens_and_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            games = root / "games.jsonl"
            leaves = root / "leaves.jsonl"
            sqlite_path = root / "seen.sqlite"
            games.write_text(
                json.dumps(
                    {
                        "fen": "start w - - 0 1",
                        "result": "1-0",
                        "opening_index": 9,
                        "color": "as_written",
                        "records": [{"fen": "late w - - 0 1"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            leaves.write_text(
                json.dumps({"fen": "qs1 w - - 0 1"}) + "\n" + json.dumps({"fen": "qs2 w - - 0 1"}) + "\n",
                encoding="utf-8",
            )
            from collect_leaves import index_existing_leaves

            stats = index_existing_leaves(leaves, sqlite_path, games, 3)
            store = FenStore(sqlite_path)
            self.assertEqual(stats["fen_keys"], 2)
            self.assertGreaterEqual(stats["roots"], 2)
            self.assertTrue(store.has_root(9, "as_written", "start w - -"))
            self.assertFalse(store.add_fen("qs1 w - -"))
            store.close()


if __name__ == "__main__":
    unittest.main()
