#!/usr/bin/env python3
"""Fit policy / controller priors from self-play JSONL + telemetry CSV.

Writes NSCEPOLY / NSCECTRL binaries loadable by the engine.
No PyTorch required (stdlib only). Optional torch path documented in README.
"""

from __future__ import annotations

import argparse
import json
import struct
from collections import defaultdict
from pathlib import Path


def clamp_i16(v: int) -> int:
    return max(-32768, min(32767, int(v)))


def write_policy(path: Path, from_to_counts: dict[tuple[int, int], int]) -> None:
    w_piece_to = [[0] * 64 for _ in range(12)]
    w_from_to = [[0] * 64 for _ in range(64)]
    # Bootstrap center prior
    for pc in range(12):
        for to in range(64):
            f, r = to & 7, to >> 3
            w_piece_to[pc][to] = clamp_i16(3 - abs(f - 3) - abs(r - 3))
    for (frm, to), c in from_to_counts.items():
        w_from_to[frm][to] = clamp_i16(c * 8)
    with path.open("wb") as f:
        f.write(b"NSCEPOLY")
        for pc in range(12):
            f.write(struct.pack("<64h", *w_piece_to[pc]))
        for frm in range(64):
            f.write(struct.pack("<64h", *w_from_to[frm]))
    print(f"wrote {path}")


def write_controller(path: Path, avg_reduce: float, late_cut_rate: float) -> None:
    # Map telemetry stats into linear weights
    w_depth = 80
    w_index = int(50 + 100 * late_cut_rate)
    w_eval_gap = 2
    w_quiet = 40
    w_policy = -1
    bias = int(-50 + 20 * (avg_reduce - 1.5))
    with path.open("wb") as f:
        f.write(b"NSCECTRL")
        f.write(struct.pack("<6i", w_depth, w_index, w_eval_gap, w_quiet, w_policy, bias))
    print(f"wrote {path} avg_reduce={avg_reduce:.2f} late_cut={late_cut_rate:.2f}")


def sq(uci: str, i: int) -> int:
    return (ord(uci[i]) - ord("a")) + 8 * (ord(uci[i + 1]) - ord("1"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfplay", default="train/data/selfplay.jsonl")
    ap.add_argument("--telemetry", default="")
    ap.add_argument("--policy-out", default="nets/policy.bin")
    ap.add_argument("--controller-out", default="nets/controller.bin")
    args = ap.parse_args()

    from_to: dict[tuple[int, int], int] = defaultdict(int)
    sp = Path(args.selfplay)
    if sp.exists():
        for line in sp.read_text().splitlines():
            if not line.strip():
                continue
            g = json.loads(line)
            for mv in g.get("moves", []):
                if len(mv) >= 4:
                    from_to[(sq(mv, 0), sq(mv, 2))] += 1

    Path(args.policy_out).parent.mkdir(parents=True, exist_ok=True)
    write_policy(Path(args.policy_out), from_to)

    reduces = []
    cuts_late = 0
    total_late = 0
    tel = Path(args.telemetry) if args.telemetry else None
    if tel and tel.exists():
        for line in tel.read_text().splitlines():
            parts = line.split(",")
            if len(parts) < 6:
                continue
            depth = int(parts[1])
            idx = int(parts[2])
            red = int(parts[3])
            cut = int(parts[5])
            reduces.append(red)
            if idx >= 4:
                total_late += 1
                cuts_late += cut
    avg_r = sum(reduces) / len(reduces) if reduces else 1.5
    late = (cuts_late / total_late) if total_late else 0.2
    write_controller(Path(args.controller_out), avg_r, late)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
