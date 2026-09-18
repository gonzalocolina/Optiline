#!/usr/bin/env python3
"""Append one Findings bullet from a fastchess match JSON. Does not edit older entries."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, required=True)
    ap.add_argument("--knowledge", type=Path, default=ROOT / "docs/knowledge.md")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    summary = json.loads(args.json.read_text())
    report = args.json.parent / "report.md"
    rel = report.resolve().relative_to(ROOT).as_posix()
    text = args.knowledge.read_text()
    if rel in text:
        print(f"already logged {rel}")
        return 0
    w, d, l = summary.get("W"), summary.get("D"), summary.get("L")
    n = summary.get("games")
    elo = summary.get("elo_a_minus_b")
    err = summary.get("elo_err_95")
    name_a = summary.get("name_a", "A")
    name_b = summary.get("name_b", "B")
    tc = summary.get("st_ms") or summary.get("tc")
    seed = summary.get("seed")
    note = f" {args.note}" if args.note else ""
    day = date.today().isoformat()
    bullet = (
        f"- {name_a} vs {name_b}, {tc}, N={n}, seed {seed}: "
        f"**{w}-{d}-{l}**, **{elo:+.1f} ± {err:.1f}**.{note} "
        f"([{args.json.parent.name}](../{rel}))\n"
    )
    marker = f"### {day}\n"
    if marker in text:
        text = text.replace(marker, marker + bullet, 1)
    else:
        log = "## Findings log\n"
        if log not in text:
            raise SystemExit("no Findings log heading")
        text = text.replace(log, log + f"\n{marker}\n" + bullet, 1)
    args.knowledge.write_text(text)
    print(f"logged {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
