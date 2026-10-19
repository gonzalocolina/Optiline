from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from experiment_common import sha256_file  # noqa: E402
from train_identity import (  # noqa: E402
    build_train_manifest,
    expected_graph_id,
    game_relation,
    shuffle_decision,
    split_games,
    write_sidecar,
)


def _record(game: int) -> bytes:
    raw = bytearray(32)
    raw[29] = game & 0xFF
    raw[30] = (game >> 8) & 0xFF
    raw[31] = (game >> 16) & 0xFF
    return bytes(raw)


class ShuffleIdentityTest(unittest.TestCase):
    def test_same_size_without_matching_hash_is_reshuffled(self) -> None:
        self.assertEqual(
            shuffle_decision("abc", 3200, 3200, "def", True),
            "reshuffle",
        )
        self.assertEqual(shuffle_decision("abc", 3200, 3200, None, True), "reshuffle")

    def test_matching_hash_and_validation_reuses(self) -> None:
        self.assertEqual(shuffle_decision("abc", 3200, 3200, "abc", True), "reuse")
        self.assertEqual(shuffle_decision("abc", 3200, 3200, "abc", False), "reshuffle")
        self.assertEqual(shuffle_decision("abc", 3200, 6400, "abc", True), "reshuffle")

    def test_sidecar_records_the_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "gen.bin"
            source.write_bytes(b"positions")
            sidecar = Path(tmp) / "gen.shuffled.bin.sha256"
            payload = write_sidecar(source, sidecar)
            self.assertEqual(payload["source_sha256"], sha256_file(source))
            self.assertEqual(json.loads(sidecar.read_text())["source_bytes"], len(b"positions"))


class GraphAndGamesTest(unittest.TestCase):
    def test_graph_id_matches_the_rust_format(self) -> None:
        self.assertEqual(
            expected_graph_id("mlp", "0"),
            "mlp l1=512 l2=32 l3=32 buckets=8 pair=crelu*crelu skip=1 wdl=0.0000",
        )
        self.assertEqual(
            expected_graph_id("mlp", "0.75"),
            "mlp l1=512 l2=32 l3=32 buckets=8 pair=crelu*crelu skip=1 wdl=0.7500",
        )

    def test_split_holds_out_whole_games(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "all.bin"
            source.write_bytes(_record(1) + _record(1) + _record(2) + _record(3))
            train = root / "train.bin"
            test = root / "test.bin"
            summary = split_games(source, train, test, 1 / 3, seed=0)
            self.assertEqual(summary["games"], 3)
            self.assertEqual(summary["test_games"], 1)
            self.assertEqual(summary["train_positions"] + summary["test_positions"], 4)
            self.assertEqual(game_relation(train, test), "disjoint")

    def test_unmarked_and_overlapping_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain_a = root / "a.bin"
            plain_b = root / "b.bin"
            plain_a.write_bytes(bytes(32))
            plain_b.write_bytes(bytes(32))
            self.assertEqual(game_relation(plain_a, plain_b), "unmarked")
            shared = root / "shared.bin"
            shared.write_bytes(_record(7) + _record(8))
            other = root / "other.bin"
            other.write_bytes(_record(8))
            self.assertEqual(game_relation(shared, other), "overlap")
            with self.assertRaises(ValueError):
                split_games(plain_a, root / "t.bin", root / "v.bin", 0.5, 1)

    def test_manifest_pins_dataset_and_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "gen.bin"
            shuffled = root / "gen.shuffled.bin"
            graph = root / "bullet_nsce.rs"
            source.write_bytes(_record(1) + _record(2))
            shuffled.write_bytes(_record(2) + _record(1))
            graph.write_text("graph\n", encoding="utf-8")
            test = root / "test.bin"
            test.write_bytes(_record(9))
            out = root / "manifest.json"
            manifest = build_train_manifest(source, shuffled, graph, "mlp", root / "ckpt", test, out)
            self.assertEqual(manifest["dataset"]["sha256"], sha256_file(source))
            self.assertEqual(manifest["graph"]["sha256"], sha256_file(graph))
            self.assertEqual(manifest["validation"]["game_relation"], "disjoint")
            self.assertIn("wdl", manifest["parameters"])
            self.assertEqual(manifest["graph"]["graph_id"], expected_graph_id("mlp", manifest["parameters"]["wdl"]))


if __name__ == "__main__":
    unittest.main()
