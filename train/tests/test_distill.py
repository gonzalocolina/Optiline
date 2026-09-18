from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAIN))

from distill import keep_source_record, load_exclude_keys  # noqa: E402


class ExcludeFensTest(unittest.TestCase):
    def test_skips_keys_from_previous_mix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.jsonl"
            path.write_text(
                json.dumps({"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"})
                + "\n",
                encoding="utf-8",
            )
            keys = load_exclude_keys(path)
            self.assertTrue(
                not keep_source_record(
                    {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 5 9", "site": "static"},
                    {"static"},
                    {"search_leaf"},
                    keys,
                )
            )
            self.assertTrue(
                keep_source_record(
                    {"fen": "8/8/8/8/8/8/8/K6k w - - 0 1", "site": "static", "label_kind": "search_leaf"},
                    {"static"},
                    {"search_leaf"},
                    keys,
                )
            )


class AttachSourceTest(unittest.TestCase):
    def test_copies_path_wdl_and_index(self) -> None:
        from distill import attach_source

        lab = attach_source(
            {"fen": "a w - - 0 1", "bestmove": "e2e4"},
            {"fen": "a w - - 0 1", "result": "1-0", "label_kind": "path"},
            3,
            20260814,
            True,
        )
        self.assertEqual(lab["result"], "1-0")
        self.assertEqual(lab["source_index"], 3)
        self.assertTrue(lab["sample_uniform"])


if __name__ == "__main__":
    unittest.main()
