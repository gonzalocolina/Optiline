from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import pack_nsceper1 as pack  # noqa: E402
from per1_float_ref import Per1Net, trunc_div  # noqa: E402


STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _zero_blobs() -> tuple[bytes, ...]:
    return (
        b"\x00\x00" * (pack.FEATURES * pack.HIDDEN),
        b"\x00\x00" * pack.HIDDEN,
        b"\x00\x00" * (pack.BUCKETS * pack.L2 * pack.HIDDEN),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L2),
        b"\x00\x00" * (pack.BUCKETS * pack.L3 * pack.L2),
        b"\x00\x00\x00\x00" * (pack.BUCKETS * pack.L3),
        b"\x00\x00" * (pack.BUCKETS * pack.L3),
        b"\x00\x00\x00\x00" * pack.BUCKETS,
    )


def _ones_net(path: Path) -> None:
    # Pairwise then /QA /QB kills a pure-ones MLP (startpos acc is only 32).
    # QA*QB L1/L2 bias saturates SCReLU so the test actually exercises the stack.
    blobs = list(_zero_blobs())
    blobs[0] = b"\x01\x00" * (pack.FEATURES * pack.HIDDEN)
    blobs[2] = b"\x01\x00" * (pack.BUCKETS * pack.L2 * pack.HIDDEN)
    blobs[3] = struct.pack(
        f"<{pack.BUCKETS * pack.L2}i", *([pack.QA * pack.QB] * (pack.BUCKETS * pack.L2))
    )
    blobs[4] = b"\x01\x00" * (pack.BUCKETS * pack.L3 * pack.L2)
    blobs[5] = struct.pack(
        f"<{pack.BUCKETS * pack.L3}i", *([pack.QA * pack.QB] * (pack.BUCKETS * pack.L3))
    )
    blobs[6] = b"\x01\x00" * (pack.BUCKETS * pack.L3)
    pack.write_per1(path, *blobs)


class Per1FloatRefTest(unittest.TestCase):
    def test_zero_net_is_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "z.bin"
            pack.write_per1(path, *_zero_blobs())
            net = Per1Net(path)
            self.assertEqual(net.eval_int(STARTPOS), 0)
            self.assertEqual(net.eval_float(STARTPOS), 0.0)

    def test_float_within_one_cp_of_quantized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ones.bin"
            _ones_net(path)
            net = Per1Net(path)
            q = net.eval_int(STARTPOS)
            fl = net.eval_float(STARTPOS)
            self.assertGreater(q, 0)
            self.assertLessEqual(abs(fl - q), 1.0)

    def test_bias_qa_qb_is_scale_cp(self) -> None:
        # startpos has 32 pieces → bucket (32-2)/4 = 7. Bullet stores bias at QA*QB.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bias.bin"
            blobs = list(_zero_blobs())
            l3b = [0] * pack.BUCKETS
            l3b[7] = pack.QA * pack.QB
            blobs[7] = struct.pack("<8i", *l3b)
            pack.write_per1(path, *blobs)
            net = Per1Net(path)
            self.assertEqual(net.eval_int(STARTPOS), pack.SCALE)
            self.assertAlmostEqual(net.eval_float(STARTPOS), float(pack.SCALE), places=5)

    def test_simple_bias_is_scale_cp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "simple.bin"
            l0w = b"\x00\x00" * (pack.FEATURES * pack.SIMPLE_HIDDEN)
            l0b = b"\x00\x00" * pack.SIMPLE_HIDDEN
            l1w = b"\x00\x00" * (2 * pack.SIMPLE_HIDDEN)
            l1b = struct.pack("<i", pack.QA * pack.QB)
            pack.write_per1_simple(path, l0w, l0b, l1w, l1b)
            net = Per1Net(path)
            self.assertTrue(net.simple)
            self.assertEqual(net.eval_int(STARTPOS), pack.SCALE)
            self.assertAlmostEqual(net.eval_float(STARTPOS), float(pack.SCALE), places=5)

    def test_trunc_div_matches_cpp_toward_zero(self) -> None:
        self.assertEqual(trunc_div(-753668, 255), -2955)
        self.assertEqual(trunc_div(-2955 * 400, 255 * 64), -72)
        self.assertEqual(trunc_div(255, 255), 1)
        self.assertEqual(trunc_div(-1, 255), 0)

    def test_engine_nnue_matches_python(self) -> None:
        engine_bin = ROOT / "build" / "nsce"
        if not engine_bin.is_file():
            self.skipTest("build/nsce missing")
        from uci_common import UciEngine

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ones.bin"
            _ones_net(path)
            net = Per1Net(path)
            engine = UciEngine([str(engine_bin)], "nsce", cwd=ROOT)
            try:
                engine.apply_options(
                    {
                        "UseNNUE": "true",
                        "EvalFile": str(path),
                        "UseExtras": "false",
                        "Hash": "16",
                        "Threads": "1",
                    }
                )
                details = engine.evaluate_details(STARTPOS)
            finally:
                engine.close()
            self.assertEqual(details["nnue"], net.eval_int(STARTPOS))
            self.assertLessEqual(abs(net.eval_float(STARTPOS) - details["nnue"]), 1.0)


if __name__ == "__main__":
    unittest.main()
