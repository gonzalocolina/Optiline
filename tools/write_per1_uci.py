#!/usr/bin/env python3
"""Write a one-change PER1 candidate UCI from baseline.uci.

Used so gen1+ packs do not share EvalFile with a promoted net. Does not
invent weights.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from eval_contract import parse_uci_options, resolve_eval_file  # noqa: E402
from promote_eval import rewrite_uci  # noqa: E402


def write_per1_uci(
    out: Path,
    *,
    eval_file: str | None = None,
    extras: bool | None = None,
    baseline: Path | None = None,
) -> dict[str, str]:
    baseline = baseline or (ROOT / "tools/configs/baseline.uci")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline, out)
    updates: dict[str, str] = {}
    if eval_file is not None:
        updates["EvalFile"] = eval_file
    if extras is not None:
        updates["UseExtras"] = "true" if extras else "false"
    if updates:
        rewrite_uci(out, updates)
    return parse_uci_options(out)


def baseline_eval_path(root: Path | None = None, baseline: Path | None = None) -> Path | None:
    root = root or ROOT
    baseline = baseline or (root / "tools/configs/baseline.uci")
    options = parse_uci_options(baseline)
    return resolve_eval_file(root, options.get("EvalFile", ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--eval-file", default=None)
    ap.add_argument("--extras", choices=("true", "false", "keep"), default="keep")
    ap.add_argument("--baseline", type=Path, default=ROOT / "tools/configs/baseline.uci")
    args = ap.parse_args()
    extras = None if args.extras == "keep" else args.extras == "true"
    write_per1_uci(args.output, eval_file=args.eval_file, extras=extras, baseline=args.baseline)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
