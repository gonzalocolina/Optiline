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
    change_groups,
    changed_options,
    equal_node_clearly_winning,
    equal_node_not_losing,
    extras_contract_errors,
    one_change_errors,
    parse_uci_options,
    screen_is_clear_loss,
    sprt_is_h1,
)
import promote_eval as promote  # noqa: E402


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

    def test_per1_allows_either_extras_until_measured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            net = _write_net(Path(tmp), b"NSCEPER1", "per1.bin")
            self.assertEqual(extras_contract_errors(str(net), "true"), [])
            self.assertEqual(extras_contract_errors(str(net), "false"), [])


class OneChangeTest(unittest.TestCase):
    def test_nsceper1_uci_is_eval_file_only(self) -> None:
        baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
        candidate = parse_uci_options(ROOT / "tools/configs/nsceper1.uci")
        self.assertEqual(set(changed_options(baseline, candidate)), {"EvalFile"})
        self.assertEqual(candidate["EvalFile"], "nets/nsceper1.bin")
        self.assertEqual(candidate["UseExtras"], "true")

    def test_nsceper1_extras_off_is_still_eval_group(self) -> None:
        baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
        candidate = parse_uci_options(ROOT / "tools/configs/nsceper1_extras_off.uci")
        groups = change_groups(changed_options(baseline, candidate))
        self.assertEqual(groups, ["eval"])
        self.assertEqual(candidate["UseExtras"], "false")
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


class ScreenClearLossTest(unittest.TestCase):
    def test_coin_flip_is_not_clear(self) -> None:
        self.assertFalse(screen_is_clear_loss({"elo_a_minus_b": 3.5, "elo_err_95": 20.7}))

    def test_candidate_win_is_not_clear_loss(self) -> None:
        self.assertFalse(screen_is_clear_loss({"elo_a_minus_b": -80.0, "elo_err_95": 25.0}))

    def test_baseline_ahead_beyond_ci_is_clear(self) -> None:
        self.assertTrue(screen_is_clear_loss({"elo_a_minus_b": 80.0, "elo_err_95": 25.0}))

    def test_sprt_h1_mapping(self) -> None:
        self.assertTrue(sprt_is_h1({"sprt_decision": "H1"}))
        self.assertTrue(sprt_is_h1({"decision": "accept_H1_candidate_stronger"}))
        self.assertFalse(sprt_is_h1({"sprt_decision": "inconclusive"}))


class PromoteEvalTest(unittest.TestCase):
    def test_evalfile_only_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            net = Path(tmp) / "nsceper1.bin"
            net.write_bytes(b"NSCEPER1" + b"\x00" * 16)
            baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
            candidate = dict(baseline)
            candidate["EvalFile"] = str(net)
            self.assertEqual(promote.promotion_updates(baseline, candidate), {"EvalFile": str(net)})

    def test_extras_off_is_eval_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            net = Path(tmp) / "nsceper1.bin"
            net.write_bytes(b"NSCEPER1" + b"\x00" * 16)
            baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
            candidate = dict(baseline)
            candidate["EvalFile"] = str(net)
            candidate["UseExtras"] = "false"
            self.assertEqual(
                promote.promotion_updates(baseline, candidate),
                {"EvalFile": str(net), "UseExtras": "false"},
            )

    def test_evalscale_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            net = Path(tmp) / "nsceper1.bin"
            net.write_bytes(b"NSCEPER1" + b"\x00" * 16)
            baseline = parse_uci_options(ROOT / "tools/configs/baseline.uci")
            candidate = dict(baseline)
            candidate["EvalFile"] = str(net)
            candidate["EvalScale"] = "926"
            with self.assertRaises(SystemExit):
                promote.promotion_updates(baseline, candidate)

    def test_rewrite_uci_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "base.uci"
            path.write_text((ROOT / "tools/configs/baseline.uci").read_text())
            promote.rewrite_uci(path, {"EvalFile": "nets/nsceper1.bin"})
            got = parse_uci_options(path)
            self.assertEqual(got["EvalFile"], "nets/nsceper1.bin")
            self.assertEqual(got["UseExtras"], "true")
            self.assertEqual(got["EvalScale"], "1000")

    def test_gen1_candidate_is_evalfile_only(self) -> None:
        import write_per1_uci as write_uci

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gen0 = tmp_path / "nsceper1_gen0.bin"
            gen1 = tmp_path / "nsceper1_gen1.bin"
            gen0.write_bytes(b"NSCEPER1" + b"\x00" * 16)
            gen1.write_bytes(b"NSCEPER1" + b"\x00" * 16)
            promoted = tmp_path / "baseline.uci"
            promoted.write_text((ROOT / "tools/configs/baseline.uci").read_text())
            promote.rewrite_uci(promoted, {"EvalFile": str(gen0)})
            candidate = tmp_path / "cand.uci"
            write_uci.write_per1_uci(candidate, eval_file=str(gen1), extras=True, baseline=promoted)
            baseline = parse_uci_options(promoted)
            cand = parse_uci_options(candidate)
            self.assertEqual(set(changed_options(baseline, cand)), {"EvalFile"})
            self.assertEqual(cand["EvalFile"], str(gen1))
            extras_off = tmp_path / "off.uci"
            write_uci.write_per1_uci(extras_off, extras=False, baseline=promoted)
            off = parse_uci_options(extras_off)
            self.assertEqual(set(changed_options(baseline, off)), {"UseExtras"})
            self.assertEqual(off["EvalFile"], str(gen0))
            self.assertEqual(off["UseExtras"], "false")


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

    def test_fastchess_without_h1_does_not_demand_equal_node(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            sprt = Path(tmp) / "match.json"
            manifest = Path(tmp) / "manifest.json"
            pgn = Path(tmp) / "games.pgn"
            pgn.write_text("dummy\n")
            sprt.write_text(
                json.dumps(
                    {
                        "harness": "fastchess",
                        "fastchess_exit_code": 0,
                        "W": 40,
                        "D": 20,
                        "L": 40,
                        "games": 100,
                        "st_ms": 100,
                        "sprt_decision": "inconclusive",
                        "cfg_a": str(ROOT / "tools/configs/baseline.uci"),
                        "cfg_b": str(ROOT / "tools/configs/nnue_search_leaves40k.uci"),
                        "pgn": str(pgn),
                    }
                )
            )
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "measurement": {
                            "pairing": "color_reversed_opening_pairs",
                            "raw_game_telemetry": True,
                        },
                        "artifacts": {},
                    }
                )
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/promotion_gate.py"),
                    "--stage",
                    "eval",
                    "--sprt",
                    str(sprt),
                    "--manifest",
                    str(manifest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("not promotion-positive", proc.stdout)
            self.assertNotIn("equal-node", proc.stdout)


if __name__ == "__main__":
    unittest.main()
