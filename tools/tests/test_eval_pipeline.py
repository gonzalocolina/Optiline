from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "train"))

from distill import keep_source_record  # noqa: E402
from eval_contract import (  # noqa: E402
    equal_node_clearly_winning,
    equal_node_not_losing,
    extras_contract_errors,
    one_change_errors,
    parse_uci_options,
)


def _write_net(directory: Path, magic: bytes, name: str) -> Path:
    path = directory / name
    path.write_bytes(magic + b"\x00" * 16)
    return path


class ExtrasContractTest(unittest.TestCase):
    def test_internal_768_requires_extras_on(self) -> None:
        self.assertEqual(extras_contract_errors("internal", "true"), [])
        self.assertTrue(extras_contract_errors("internal", "false"))

    def test_kat_rejects_extras_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kat = _write_net(Path(tmp), b"NSCEKAT1", "kat.bin")
            self.assertTrue(extras_contract_errors(str(kat), "true"))
            self.assertEqual(extras_contract_errors(str(kat), "false"), [])


class OneChangeTest(unittest.TestCase):
    def test_eval_file_alone_is_one_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            net = _write_net(Path(tmp), b"NSCENNUE", "cand.bin")
            baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
            candidate = dict(baseline)
            candidate["EvalFile"] = str(net)
            self.assertEqual(one_change_errors(baseline, candidate), [])

    def test_new_net_plus_evalscale_is_illegal(self) -> None:
        baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
        candidate = dict(baseline)
        candidate["EvalFile"] = "nets/nnue_trained.bin"
        candidate["EvalScale"] = "1519"
        errors = one_change_errors(baseline, candidate)
        self.assertTrue(any("more than one contract group" in error for error in errors))

    def test_search_retune_blocked_until_eval_wins(self) -> None:
        baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
        candidate = dict(baseline)
        candidate["EvalScale"] = "1091"
        self.assertTrue(one_change_errors(baseline, candidate, allow_search_retune=False))
        self.assertEqual(one_change_errors(baseline, candidate, allow_search_retune=True), [])


class EqualNodeGateTest(unittest.TestCase):
    def test_n40_is_not_a_gate(self) -> None:
        result = {
            "nodes_per_move": 25000,
            "games": 40,
            "W": 5,
            "D": 32,
            "L": 3,
            "elo_diff_a_minus_b": 17.0,
            "elo_err_95": 50.0,
        }
        self.assertTrue(equal_node_not_losing(result, min_games=200))

    def test_sf25k_n400_is_a_loss(self) -> None:
        result = {
            "nodes_per_move": 25000,
            "games": 400,
            "W": 43,
            "D": 338,
            "L": 19,
            "elo_diff_a_minus_b": 21.0,
            "elo_err_95": 13.0,
        }
        self.assertTrue(equal_node_not_losing(result))
        self.assertTrue(equal_node_clearly_winning(result))

    def test_clear_win(self) -> None:
        result = {
            "nodes_per_move": 25000,
            "games": 200,
            "W": 20,
            "D": 120,
            "L": 60,
            "elo_diff_a_minus_b": -40.0,
            "elo_err_95": 18.0,
        }
        self.assertEqual(equal_node_not_losing(result), [])
        self.assertEqual(equal_node_clearly_winning(result), [])


class DistillLeafFilterTest(unittest.TestCase):
    def test_keeps_quiet_leaves_and_drops_other_sites(self) -> None:
        sites = {"q_stand_pat", "static", "in_check_static"}
        self.assertTrue(keep_source_record({"fen": "x", "site": "q_stand_pat"}, sites))
        self.assertFalse(keep_source_record({"fen": "x", "site": "max_ply"}, sites))
        self.assertTrue(keep_source_record({"fen": "x"}, sites))

    def test_reservoir_sample_is_seeded_and_sized(self) -> None:
        from distill import reservoir_sample

        records = ({"fen": f"fen-{i}"} for i in range(50))
        sample = reservoir_sample(records, 10, seed=7)
        self.assertEqual(len(sample), 10)
        again = reservoir_sample(({"fen": f"fen-{i}"} for i in range(50)), 10, seed=7)
        self.assertEqual([row["fen"] for row in sample], [row["fen"] for row in again])


class PromotionGateStageTest(unittest.TestCase):
    def test_mae_only_does_not_promote(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            validation = Path(tmp) / "val.json"
            validation.write_text(
                json.dumps(
                    {
                        "trained": {"mae_cp": 12.0},
                        "trained_options": {"EvalFile": "internal", "UseExtras": True},
                        "clone": {"pass": True, "max_clone_mae_cp": 15.0},
                    }
                )
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/promotion_gate.py"),
                    "--stage",
                    "eval",
                    "--validation",
                    str(validation),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("FAIL", proc.stdout)


if __name__ == "__main__":
    unittest.main()
