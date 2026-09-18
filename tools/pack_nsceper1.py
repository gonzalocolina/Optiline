#!/usr/bin/env python3
"""Pack a dual-perspective SCReLU net into the NSCEPER1 binary the engine loads.

Layout (little-endian):
  magic[8] = NSCEPER1
  i32 hidden=512 features=768 buckets=8 qa=255 qb=64 scale=400
  i16 w0[features * hidden]     # l0w, feature-major
  i16 b0[hidden]                # l0b
  i16 w1[buckets][2 * hidden]   # l1w transposed, bucket-major, stm then nstm
  i32 b1[buckets]               # l1b (QA*QB scale)
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

HIDDEN = 512
FEATURES = 768
BUCKETS = 8
QA = 255
QB = 64
SCALE = 400


def read_i16(path: Path, count: int) -> bytes:
    data = path.read_bytes()
    if len(data) != count * 2:
        raise ValueError(f"{path} is {len(data)} bytes, expected {count * 2}")
    return data


def read_i32(path: Path, count: int) -> bytes:
    data = path.read_bytes()
    if len(data) != count * 4:
        raise ValueError(f"{path} is {len(data)} bytes, expected {count * 4}")
    return data


def write_per1(
    path: Path,
    l0w: bytes,
    l0b: bytes,
    l1w: bytes,
    l1b: bytes,
    qa: int = QA,
    qb: int = QB,
    scale: int = SCALE,
) -> None:
    if len(l0w) != FEATURES * HIDDEN * 2:
        raise ValueError(f"l0w is {len(l0w)} bytes, expected {FEATURES * HIDDEN * 2}")
    if len(l0b) != HIDDEN * 2:
        raise ValueError(f"l0b is {len(l0b)} bytes, expected {HIDDEN * 2}")
    if len(l1w) != BUCKETS * 2 * HIDDEN * 2:
        raise ValueError(f"l1w is {len(l1w)} bytes, expected {BUCKETS * 2 * HIDDEN * 2}")
    if len(l1b) != BUCKETS * 4:
        raise ValueError(f"l1b is {len(l1b)} bytes, expected {BUCKETS * 4}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        out.write(b"NSCEPER1")
        out.write(struct.pack("<6i", HIDDEN, FEATURES, BUCKETS, qa, qb, scale))
        out.write(l0w)
        out.write(l0b)
        out.write(l1w)
        out.write(l1b)


def pack_from_quantised(quantised: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """Split bullet `quantised.bin` (l0w, l0b, transposed l1w, i16 l1b, 64-byte pad)."""
    l0w_n = FEATURES * HIDDEN * 2
    l0b_n = HIDDEN * 2
    l1w_n = BUCKETS * 2 * HIDDEN * 2
    l1b_n = BUCKETS * 2
    need = l0w_n + l0b_n + l1w_n + l1b_n
    if len(quantised) < need:
        raise ValueError(f"quantised.bin is {len(quantised)} bytes, expected at least {need}")
    off = 0
    l0w = quantised[off : off + l0w_n]
    off += l0w_n
    l0b = quantised[off : off + l0b_n]
    off += l0b_n
    l1w = quantised[off : off + l1w_n]
    off += l1w_n
    l1b16 = struct.unpack_from(f"<{BUCKETS}h", quantised, off)
    l1b = struct.pack(f"<{BUCKETS}i", *l1b16)
    return l0w, l0b, l1w, l1b


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-quantised", type=Path, help="bullet checkpoint quantised.bin")
    parser.add_argument("--l0w", type=Path)
    parser.add_argument("--l0b", type=Path)
    parser.add_argument("--l1w", type=Path)
    parser.add_argument("--l1b", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("nets/nsceper1.bin"))
    parser.add_argument("--qa", type=int, default=QA)
    parser.add_argument("--qb", type=int, default=QB)
    parser.add_argument("--scale", type=int, default=SCALE)
    args = parser.parse_args()

    if args.from_quantised:
        l0w, l0b, l1w, l1b = pack_from_quantised(args.from_quantised.read_bytes())
    else:
        if not all([args.l0w, args.l0b, args.l1w, args.l1b]):
            parser.error("need --from-quantised or --l0w --l0b --l1w --l1b")
        l0w = read_i16(args.l0w, FEATURES * HIDDEN)
        l0b = read_i16(args.l0b, HIDDEN)
        l1w = read_i16(args.l1w, BUCKETS * 2 * HIDDEN)
        l1b = read_i32(args.l1b, BUCKETS)

    write_per1(args.output, l0w, l0b, l1w, l1b, args.qa, args.qb, args.scale)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
