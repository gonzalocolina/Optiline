#!/usr/bin/env python3
"""Pack the NSCEPER1 net.

MLP layout (little-endian), SF19-shaped 512/32/32:
  magic[8] = NSCEPER1
  i32 hidden=512 features=768 buckets=8 l2=32 l3=32 qa=255 qb=64 scale=400
  i16 w0[features * hidden]
  i16 b0[hidden]
  i16 l1w[buckets][l2][hidden]
  i32 l1b[buckets][l2]
  i16 l2w[buckets][l3][2*l2]   # pair-act concat(CReLU, SCReLU)
  i32 l2b[buckets][l3]
  i16 l3w[buckets][2*l3]
  i32 l3b[buckets]

Simple (768→512)×2 layout: hidden=512, buckets=l2=l3=0, then
  i16 w0[768*512], i16 b0[512], i16 l1w[1024] (not transposed), i32 l1b.

HL layout: hidden=512, buckets=0, l2=32, l3=1, then
  i16 w0[768*512], i16 b0[512],
  i16 l1w[32][1024] (transposed), i32 l1b[32], i16 l2w[32], i32 l2b.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

HIDDEN = 512
SIMPLE_HIDDEN = 512
HL = 32
FEATURES = 768
BUCKETS = 8
L2 = 32
L3 = 32
L2_ACT = 2 * L2
L3_ACT = 2 * L3
QA = 255
QB = 64
SCALE = 400


def _i16_n(count: int) -> int:
    return count * 2


def expected_size() -> int:
    return (
        8
        + 8 * 4
        + FEATURES * HIDDEN * 2
        + HIDDEN * 2
        + BUCKETS * L2 * HIDDEN * 2
        + BUCKETS * L2 * 4
        + BUCKETS * L3 * L2_ACT * 2
        + BUCKETS * L3 * 4
        + BUCKETS * L3_ACT * 2
        + BUCKETS * 4
    )


def write_per1(
    path: Path,
    l0w: bytes,
    l0b: bytes,
    l1w: bytes,
    l1b: bytes,
    l2w: bytes,
    l2b: bytes,
    l3w: bytes,
    l3b: bytes,
    qa: int = QA,
    qb: int = QB,
    scale: int = SCALE,
) -> None:
    sizes = {
        "l0w": (l0w, FEATURES * HIDDEN * 2),
        "l0b": (l0b, HIDDEN * 2),
        "l1w": (l1w, BUCKETS * L2 * HIDDEN * 2),
        "l1b": (l1b, BUCKETS * L2 * 4),
        "l2w": (l2w, BUCKETS * L3 * L2_ACT * 2),
        "l2b": (l2b, BUCKETS * L3 * 4),
        "l3w": (l3w, BUCKETS * L3_ACT * 2),
        "l3b": (l3b, BUCKETS * 4),
    }
    for name, (blob, n) in sizes.items():
        if len(blob) != n:
            raise ValueError(f"{name} is {len(blob)} bytes, expected {n}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        out.write(b"NSCEPER1")
        out.write(struct.pack("<8i", HIDDEN, FEATURES, BUCKETS, L2, L3, qa, qb, scale))
        out.write(l0w)
        out.write(l0b)
        out.write(l1w)
        out.write(l1b)
        out.write(l2w)
        out.write(l2b)
        out.write(l3w)
        out.write(l3b)
    n = path.stat().st_size
    if n != expected_size():
        raise RuntimeError(f"{path} is {n} bytes, expected {expected_size()}")


def expected_size_simple() -> int:
    return (
        8
        + 8 * 4
        + FEATURES * SIMPLE_HIDDEN * 2
        + SIMPLE_HIDDEN * 2
        + 2 * SIMPLE_HIDDEN * 2
        + 4
    )


def expected_size_hl() -> int:
    return (
        8
        + 8 * 4
        + FEATURES * SIMPLE_HIDDEN * 2
        + SIMPLE_HIDDEN * 2
        + HL * (2 * SIMPLE_HIDDEN) * 2
        + HL * 4
        + HL * 2
        + 4
    )


def write_per1_hl(
    path: Path,
    l0w: bytes,
    l0b: bytes,
    l1w: bytes,
    l1b: bytes,
    l2w: bytes,
    l2b: bytes,
    qa: int = QA,
    qb: int = QB,
    scale: int = SCALE,
) -> None:
    sizes = {
        "l0w": (l0w, FEATURES * SIMPLE_HIDDEN * 2),
        "l0b": (l0b, SIMPLE_HIDDEN * 2),
        "l1w": (l1w, HL * 2 * SIMPLE_HIDDEN * 2),
        "l1b": (l1b, HL * 4),
        "l2w": (l2w, HL * 2),
        "l2b": (l2b, 4),
    }
    for name, (blob, n) in sizes.items():
        if len(blob) != n:
            raise ValueError(f"{name} is {len(blob)} bytes, expected {n}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        out.write(b"NSCEPER1")
        out.write(struct.pack("<8i", SIMPLE_HIDDEN, FEATURES, 0, HL, 1, qa, qb, scale))
        out.write(l0w)
        out.write(l0b)
        out.write(l1w)
        out.write(l1b)
        out.write(l2w)
        out.write(l2b)
    n = path.stat().st_size
    if n != expected_size_hl():
        raise RuntimeError(f"{path} is {n} bytes, expected {expected_size_hl()}")


def pack_from_quantised_hl(quantised: bytes) -> tuple[bytes, bytes, bytes, bytes, bytes, bytes]:
    """Split bullet hl.rs quantised.bin. l1w is already transposed to [32][1024]."""
    parts = [
        FEATURES * SIMPLE_HIDDEN * 2,
        SIMPLE_HIDDEN * 2,
        HL * (2 * SIMPLE_HIDDEN) * 2,
        HL * 2,
        HL * 2,
        2,
    ]
    need = sum(parts)
    if len(quantised) < need:
        raise ValueError(f"quantised.bin is {len(quantised)} bytes, expected at least {need}")
    off = 0
    blobs: list[bytes] = []
    for n in parts:
        blobs.append(quantised[off : off + n])
        off += n
    l0w, l0b, l1w, l1b16, l2w, l2b16 = blobs

    def i16_to_i32(raw: bytes, count: int) -> bytes:
        vals = struct.unpack(f"<{count}h", raw)
        return struct.pack(f"<{count}i", *vals)

    return l0w, l0b, l1w, i16_to_i32(l1b16, HL), l2w, i16_to_i32(l2b16, 1)


def write_per1_simple(
    path: Path,
    l0w: bytes,
    l0b: bytes,
    l1w: bytes,
    l1b: bytes,
    qa: int = QA,
    qb: int = QB,
    scale: int = SCALE,
) -> None:
    sizes = {
        "l0w": (l0w, FEATURES * SIMPLE_HIDDEN * 2),
        "l0b": (l0b, SIMPLE_HIDDEN * 2),
        "l1w": (l1w, 2 * SIMPLE_HIDDEN * 2),
        "l1b": (l1b, 4),
    }
    for name, (blob, n) in sizes.items():
        if len(blob) != n:
            raise ValueError(f"{name} is {len(blob)} bytes, expected {n}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        out.write(b"NSCEPER1")
        out.write(struct.pack("<8i", SIMPLE_HIDDEN, FEATURES, 0, 0, 0, qa, qb, scale))
        out.write(l0w)
        out.write(l0b)
        out.write(l1w)
        out.write(l1b)
    n = path.stat().st_size
    if n != expected_size_simple():
        raise RuntimeError(f"{path} is {n} bytes, expected {expected_size_simple()}")


def pack_from_quantised(quantised: bytes) -> tuple[bytes, ...]:
    """Split bullet quantised.bin: l0 i16, l1/l2/l3 transposed i16 weights, i16 biases."""
    parts = [
        FEATURES * HIDDEN * 2,  # l0w
        HIDDEN * 2,  # l0b
        BUCKETS * L2 * HIDDEN * 2,  # l1w
        BUCKETS * L2 * 2,  # l1b i16
        BUCKETS * L3 * L2_ACT * 2,  # l2w
        BUCKETS * L3 * 2,  # l2b i16
        BUCKETS * L3_ACT * 2,  # l3w
        BUCKETS * 2,  # l3b i16
    ]
    need = sum(parts)
    if len(quantised) < need:
        raise ValueError(f"quantised.bin is {len(quantised)} bytes, expected at least {need}")
    off = 0
    blobs: list[bytes] = []
    for n in parts:
        blobs.append(quantised[off : off + n])
        off += n
    l0w, l0b, l1w, l1b16, l2w, l2b16, l3w, l3b16 = blobs

    def i16_to_i32(raw: bytes, count: int) -> bytes:
        vals = struct.unpack(f"<{count}h", raw)
        return struct.pack(f"<{count}i", *vals)

    return (
        l0w,
        l0b,
        l1w,
        i16_to_i32(l1b16, BUCKETS * L2),
        l2w,
        i16_to_i32(l2b16, BUCKETS * L3),
        l3w,
        i16_to_i32(l3b16, BUCKETS),
    )


def pack_from_quantised_simple(quantised: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """Split bullet simple.rs quantised.bin: l0 i16, l1w not transposed, l1b i16."""
    parts = [
        FEATURES * SIMPLE_HIDDEN * 2,
        SIMPLE_HIDDEN * 2,
        2 * SIMPLE_HIDDEN * 2,
        2,
    ]
    need = sum(parts)
    if len(quantised) < need:
        raise ValueError(f"quantised.bin is {len(quantised)} bytes, expected at least {need}")
    off = 0
    blobs: list[bytes] = []
    for n in parts:
        blobs.append(quantised[off : off + n])
        off += n
    l0w, l0b, l1w, l1b16 = blobs
    (bias,) = struct.unpack("<h", l1b16)
    return l0w, l0b, l1w, struct.pack("<i", bias)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-quantised", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("nets/nsceper1.bin"))
    parser.add_argument("--simple", action="store_true")
    parser.add_argument("--hl", action="store_true")
    parser.add_argument("--qa", type=int, default=QA)
    parser.add_argument("--qb", type=int, default=QB)
    parser.add_argument("--scale", type=int, default=SCALE)
    args = parser.parse_args()
    if not args.from_quantised:
        parser.error("need --from-quantised")
    raw = args.from_quantised.read_bytes()
    simple_need = FEATURES * SIMPLE_HIDDEN * 2 + SIMPLE_HIDDEN * 2 + 2 * SIMPLE_HIDDEN * 2 + 2
    mlp_need = (
        FEATURES * HIDDEN * 2
        + HIDDEN * 2
        + BUCKETS * L2 * HIDDEN * 2
        + BUCKETS * L2 * 2
        + BUCKETS * L3 * L2_ACT * 2
        + BUCKETS * L3 * 2
        + BUCKETS * L3_ACT * 2
        + BUCKETS * 2
    )
    hl_need = (
        FEATURES * SIMPLE_HIDDEN * 2
        + SIMPLE_HIDDEN * 2
        + HL * (2 * SIMPLE_HIDDEN) * 2
        + HL * 2
        + HL * 2
        + 2
    )
    if args.hl and args.simple:
        parser.error("--hl and --simple are exclusive")
    if args.hl:
        blobs = pack_from_quantised_hl(raw)
        write_per1_hl(args.output, *blobs, qa=args.qa, qb=args.qb, scale=args.scale)
        print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
        return 0
    if args.simple:
        simple = True
    elif len(raw) >= mlp_need:
        simple = False
    elif len(raw) == hl_need:
        parser.error("quantised.bin looks like the hl graph; pass --hl")
    elif len(raw) >= simple_need:
        simple = True
    else:
        simple = False
    if simple:
        blobs = pack_from_quantised_simple(raw)
        write_per1_simple(args.output, *blobs, qa=args.qa, qb=args.qb, scale=args.scale)
    else:
        blobs = pack_from_quantised(raw)
        write_per1(args.output, *blobs, qa=args.qa, qb=args.qb, scale=args.scale)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
