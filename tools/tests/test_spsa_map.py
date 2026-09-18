from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUNE_HPP = ROOT / "engine/include/nsce/tune.hpp"
SPSA = ROOT / "tools/configs/spsa.json"
ENGINE = ROOT / "build/nsce-tune"


def parse_specs() -> dict[str, dict[str, int]]:
    text = TUNE_HPP.read_text()
    specs = {}
    for m in re.finditer(
        r'\{\s*"(\w+)",\s*&SearchTune::\w+,\s*(\d+),\s*(\d+),\s*(\d+)\s*\}',
        text,
    ):
        specs[m.group(1)] = {
            "min_value": int(m.group(2)),
            "max_value": int(m.group(3)),
            "step": int(m.group(4)),
        }
    defaults = {}
    for m in re.finditer(r"int (\w+) = (\d+);", text):
        defaults[m.group(1)] = int(m.group(2))
    field_to_name = dict(
        re.findall(r'\{\s*"(\w+)",\s*&SearchTune::(\w+),', text),
    )
    for name, field in field_to_name.items():
        specs[name]["value"] = defaults[field]
    return specs


class SpsaMapTest(unittest.TestCase):
    def test_json_matches_kTuneSpecs(self) -> None:
        specs = parse_specs()
        self.assertEqual(len(specs), 44)
        cfg = json.loads(SPSA.read_text())
        self.assertEqual(set(cfg), set(specs))
        for name, spec in specs.items():
            self.assertEqual(cfg[name], spec, name)

    def test_tune_binary_advertises_same_spins(self) -> None:
        if not ENGINE.is_file():
            self.skipTest("build/nsce-tune missing")
        out = subprocess.check_output(
            [str(ENGINE)],
            input="uci\nquit\n",
            text=True,
            cwd=ROOT,
        )
        advertised = {}
        for line in out.splitlines():
            m = re.match(
                r"option name (\w+) type spin default (-?\d+) min (-?\d+) max (-?\d+)",
                line,
            )
            if not m:
                continue
            advertised[m.group(1)] = {
                "value": int(m.group(2)),
                "min_value": int(m.group(3)),
                "max_value": int(m.group(4)),
            }
        specs = parse_specs()
        for name, spec in specs.items():
            self.assertIn(name, advertised, name)
            got = advertised[name]
            self.assertEqual(got["value"], spec["value"], name)
            self.assertEqual(got["min_value"], spec["min_value"], name)
            self.assertEqual(got["max_value"], spec["max_value"], name)


if __name__ == "__main__":
    unittest.main()
