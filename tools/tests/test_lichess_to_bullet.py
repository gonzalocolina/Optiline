from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from jsonl_to_bullet import RECORD  # noqa: E402
from lichess_to_bullet import convert, iter_packed, position_key, shuffle_bin  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def line(fen: str, cp: int, depth: int, mate: int | None = None) -> str:
    pv: dict = {"line": "e2e4"}
    if mate is None:
        pv["cp"] = cp
    else:
        pv["mate"] = mate
    return json.dumps({"fen": fen, "evals": [{"depth": depth, "pvs": [pv]}]})


class LichessToBulletTest(unittest.TestCase):
    def test_filters_depth_mates_and_duplicates(self) -> None:
        lines = [
            line(START, 20, 8),
            line(START, 40, 24),
            line(START, 30, 30),
            line(E4, 15, 18),
            line("8/8/8/8/8/8/8/K6k w - - 0 1", 0, 30, mate=1),
            "{not json",
        ]
        packed = list(iter_packed(lines, limit=10, min_depth=12, max_abs_cp=3000))
        self.assertEqual(len(packed), 2)
        self.assertEqual(packed[0][1], 40)
        self.assertEqual(packed[1][0].split()[1], "b")
        crowded = "QQQQQQQQ/QQQQQQQQ/QQQQQQQQ/QQQQQQQQ/QQQQQQQQ/QQQQQQQQ/QQQQQQQQ/KQQQQQQk w - - 0 1"
        skipped = list(iter_packed([line(crowded, 10, 20), line(E4, 15, 18)], limit=10, min_depth=12, max_abs_cp=3000))
        self.assertEqual(len(skipped), 1)
        self.assertEqual(struct.unpack_from("<h", packed[1][3], 24)[0], -15)

    def test_holdout_is_excluded_from_the_bin(self) -> None:
        body = "\n".join((line(START, 12, 20), line(E4, -7, 16))) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "train.bin"
            hold = Path(tmp) / "hold.jsonl"
            train_n, hold_n = convert(body.splitlines(), out, hold, limit=10, holdout=1, min_depth=12, max_abs_cp=3000)
            self.assertEqual((train_n, hold_n), (1, 1))
            self.assertEqual(out.stat().st_size, 32)
            held = json.loads(hold.read_text().splitlines()[0])
            self.assertEqual(held["score_cp"], 12)
            occ, _, score, result, *_ = RECORD.unpack(out.read_bytes())
            self.assertEqual(occ.bit_count(), 32)
            self.assertEqual(score, 7)
            self.assertEqual(result, 1)

    def test_shuffle_keeps_every_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "boards.bin"
            raw = b"".join(struct.pack("<I28x", i) for i in range(6))
            path.write_bytes(raw)
            self.assertEqual(shuffle_bin(path, 1), 6)
            got = {struct.unpack_from("<I", path.read_bytes(), i * 32)[0] for i in range(6)}
            self.assertEqual(got, set(range(6)))

    def test_position_key_ignores_move_counters(self) -> None:
        a = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        b = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 4 9"
        self.assertEqual(position_key(a), position_key(b))


if __name__ == "__main__":
    unittest.main()
