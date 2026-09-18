#!/usr/bin/env python3
"""Copy an eval candidate into baseline.uci only after promotion_gate PASS.

Does not invent a net. Does not change search options. One eval-group UCI
update (EvalFile and, if the winning candidate also flipped it, UseExtras).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from eval_contract import (  # noqa: E402
    EVAL_GROUP,
    changed_options,
    one_change_errors,
    parse_uci_options,
)

PROMOTE_KEYS = frozenset({"EvalFile", "UseExtras"})


def rewrite_uci(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 5 and parts[0].lower() == "setoption" and parts[1].lower() == "name":
            try:
                value_index = parts.index("value")
            except ValueError:
                out.append(line)
                continue
            name = " ".join(parts[2:value_index])
            if name in updates:
                out.append(f"setoption name {name} value {updates[name]}")
                seen.add(name)
                continue
        out.append(line)
    for name, value in updates.items():
        if name not in seen:
            out.append(f"setoption name {name} value {value}")
    path.write_text("\n".join(out) + "\n")


def promotion_updates(baseline: dict[str, str], candidate: dict[str, str]) -> dict[str, str]:
    errors = one_change_errors(baseline, candidate)
    if errors:
        raise SystemExit("one-change contract failed:\n" + "\n".join(f"- {e}" for e in errors))
    changed = changed_options(baseline, candidate)
    extra = set(changed) - PROMOTE_KEYS
    if extra:
        raise SystemExit(f"refusing to promote non-eval keys: {sorted(extra)}")
    if set(changed) - EVAL_GROUP:
        raise SystemExit(f"refusing to promote non-eval-group keys: {sorted(changed)}")
    return {key: candidate[key] for key in changed}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprt", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, default=ROOT / "tools/configs/baseline.uci")
    ap.add_argument("--cfg-b", type=Path, help="override candidate UCI (default: sprt JSON cfg_b)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gate = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/promotion_gate.py"),
            "--stage",
            "eval",
            "--sprt",
            str(args.sprt),
            "--manifest",
            str(args.manifest),
        ],
        cwd=ROOT,
    )
    if gate.returncode != 0:
        return gate.returncode

    import json

    sprt = json.loads(args.sprt.read_text())
    cfg_b = Path(str(args.cfg_b or sprt.get("cfg_b") or ""))
    if not cfg_b.is_file():
        print(f"missing candidate UCI {cfg_b}", file=sys.stderr)
        return 1
    baseline = parse_uci_options(args.baseline)
    candidate = parse_uci_options(cfg_b)
    updates = promotion_updates(baseline, candidate)
    if not updates:
        print("candidate UCI matches baseline; nothing to promote")
        return 1
    print("promote", updates)
    if args.dry_run:
        return 0
    shutil.copy2(args.baseline, args.baseline.with_suffix(args.baseline.suffix + ".bak"))
    rewrite_uci(args.baseline, updates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
