#!/usr/bin/env python3
"""Export NSCE NNUE weights (NSCENNUE binary) from a simple HCE distillation.

Requires only the Python stdlib. For full PyTorch training see train_nnue_torch.py.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

FEATURES = 12 * 64
HIDDEN = 128
SCALE = 64
PIECE_VALUE = [100, 320, 330, 500, 900, 0]


def clamp_i16(v: int) -> int:
    return max(-32768, min(32767, int(v)))


def export(path: Path) -> None:
    w0 = [[0] * HIDDEN for _ in range(FEATURES)]
    b0 = [0] * HIDDEN
    w1 = [SCALE] * HIDDEN
    b1 = 0
    for pc in range(12):
        pt = pc % 6
        color = 0 if pc < 6 else 1
        for sq in range(64):
            val = PIECE_VALUE[pt]
            if color == 1:
                val = -val
            for h in range(HIDDEN):
                w = (val * SCALE) // HIDDEN
                w += ((h * 17 + sq * 3 + pc) & 7) - 3
                w0[pc * 64 + sq][h] = clamp_i16(w)

    with path.open("wb") as f:
        f.write(b"NSCENNUE")
        f.write(struct.pack("<ii", FEATURES, HIDDEN))
        for feat in w0:
            f.write(struct.pack(f"<{HIDDEN}h", *feat))
        f.write(struct.pack(f"<{HIDDEN}h", *b0))
        f.write(struct.pack(f"<{HIDDEN}h", *w1))
        f.write(struct.pack("<i", b1))
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="nets/nnue_default.bin")
    args = ap.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    export(out)


if __name__ == "__main__":
    main()
