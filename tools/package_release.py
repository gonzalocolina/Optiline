#!/usr/bin/env python3
"""Assemble GitHub Release archives for NSCE and keep version metadata consistent.

CMake ``project(nsce VERSION X.Y.Z)`` is the source of truth. A release tag must
be ``vX.Y.Z`` or ``vX.Y.Z-<prerelease>``. The UCI ``id name`` string is injected
from that same CMake version at build time.

Usage:
  python3 tools/package_release.py version
  python3 tools/package_release.py meta --ref refs/tags/v0.11.0
  python3 tools/package_release.py pack --binary build/nsce --platform linux-x86_64-avx2 --outdir dist
  python3 tools/package_release.py verify-uci --binary build/nsce --version 0.11.0
  python3 tools/package_release.py checksums --outdir dist
  python3 tools/package_release.py notes --version 0.11.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CMAKE_VERSION_RE = re.compile(
    r"project\s*\(\s*nsce\s+VERSION\s+(\d+\.\d+\.\d+)\b",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)(?:-([0-9A-Za-z.-]+))?$")

# Default UCI EvalFile plus the promoted baseline network.
RELEASE_NETS = (
    Path("nets/nnue_trained.bin"),
    Path("nets/nnue_search_leaves40k_rw0.bin"),
)
RELEASE_CONFIG = Path("tools/configs/baseline.uci")

WINDOWS_PLATFORMS = {"windows-x86_64"}

PLAYING_TXT = """NSCE / Optiline — UCI chess engine
=================================

This archive is a ready-to-run release of the engine.

  Linux:   point Arena, Cute Chess, or any UCI GUI at ./nsce
  Windows: point the GUI at nsce.exe

The engine resolves EvalFile relative to the GUI working directory. Either
start the GUI from this extracted folder, or set EvalFile to the absolute
path of nets/nnue_search_leaves40k_rw0.bin.

Promoted baseline (Hash 16, Threads 1, extras on):

  configs/baseline.uci

UCI default EvalFile is nets/nnue_trained.bin; the current promoted net is
nets/nnue_search_leaves40k_rw0.bin. Copy the SHA256SUMS file from the GitHub
Release next to these archives if you want to verify the download.

Source: https://github.com/gonzalocolina/Optiline
License: GNU GPL v3 (see LICENSE)
"""


class ReleaseError(Exception):
    """User-facing packaging failure."""


def cmake_version(root: Path = ROOT) -> str:
    text = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    match = CMAKE_VERSION_RE.search(text)
    if not match:
        raise ReleaseError("could not parse project(nsce VERSION ...) in CMakeLists.txt")
    return match.group(1)


def parse_tag(value: str) -> tuple[str, str, bool]:
    """Return (tag, numeric version, prerelease)."""
    tag = value[len("refs/tags/") :] if value.startswith("refs/tags/") else value
    match = TAG_RE.match(tag)
    if not match:
        raise ReleaseError(
            f"tag {tag!r} is not vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-prerelease"
        )
    return tag, match.group(1), bool(match.group(2))


def archive_stem(version: str, tag: str | None = None) -> str:
    if tag:
        return f"nsce-{tag[1:]}" if tag.startswith("v") else f"nsce-{tag}"
    return f"nsce-{version}"


def archive_filename(stem: str, platform: str) -> str:
    ext = "zip" if platform in WINDOWS_PLATFORMS else "tar.gz"
    return f"{stem}-{platform}.{ext}"


def binary_name(platform: str) -> str:
    return "nsce.exe" if platform in WINDOWS_PLATFORMS else "nsce"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_github_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def meta(ref: str | None, root: Path = ROOT) -> dict[str, str]:
    version = cmake_version(root)
    tag = ""
    prerelease = "false"
    if ref:
        stripped = ref.strip()
        looks_like_tag = stripped.startswith("refs/tags/") or bool(TAG_RE.match(stripped))
        if looks_like_tag:
            tag, tag_version, is_pre = parse_tag(stripped)
            if tag_version != version:
                raise ReleaseError(
                    f"tag {tag} does not match CMake version {version}; "
                    "bump project(nsce VERSION ...) before tagging"
                )
            prerelease = "true" if is_pre else "false"
        elif stripped.startswith("refs/heads/") or stripped == "":
            pass
        else:
            raise ReleaseError(
                f"ref {ref!r} is not a vMAJOR.MINOR.PATCH tag or a branch ref"
            )
    stem = archive_stem(version, tag or None)
    return {
        "version": version,
        "tag": tag,
        "prerelease": prerelease,
        "archive_stem": stem,
        "uci_name": f"NSCE {version}",
    }


def _copy_into(staging: Path, src: Path, dest_rel: Path) -> None:
    target = staging / dest_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(src.read_bytes())
    if src.stat().st_mode & stat.S_IXUSR:
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def stage_release(
    binary: Path,
    platform: str,
    version: str,
    root: Path = ROOT,
    tag: str | None = None,
) -> Path:
    if not binary.is_file():
        raise ReleaseError(f"binary not found: {binary}")
    missing = [str(path) for path in (*RELEASE_NETS, RELEASE_CONFIG, Path("LICENSE")) if not (root / path).is_file()]
    if missing:
        raise ReleaseError("missing release files: " + ", ".join(missing))

    stem = archive_stem(version, tag)
    folder = f"{stem}-{platform}"
    staging = root / "dist" / ".staging" / folder
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    dest_binary = Path(binary_name(platform))
    _copy_into(staging, binary, dest_binary)
    if platform not in WINDOWS_PLATFORMS:
        exe = staging / dest_binary
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    _copy_into(staging, root / "LICENSE", Path("LICENSE"))
    readme = root / "README.md"
    if readme.is_file():
        _copy_into(staging, readme, Path("README.md"))
    (staging / "PLAYING.txt").write_text(PLAYING_TXT, encoding="utf-8")
    for net in RELEASE_NETS:
        _copy_into(staging, root / net, Path("nets") / net.name)
    _copy_into(staging, root / RELEASE_CONFIG, Path("configs/baseline.uci"))
    (staging / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    return staging


def write_archive(staging: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffixes[-2:] == [".tar", ".gz"] or out_path.name.endswith(".tar.gz"):
        with tarfile.open(out_path, "w:gz") as tar:
            tar.add(staging, arcname=staging.name)
    elif out_path.suffix == ".zip":
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(p for p in staging.rglob("*") if p.is_file()):
                zf.write(file_path, file_path.relative_to(staging.parent).as_posix())
    else:
        raise ReleaseError(f"unsupported archive type: {out_path.name}")
    return out_path


def pack(
    binary: Path,
    platform: str,
    version: str,
    outdir: Path,
    root: Path = ROOT,
    tag: str | None = None,
) -> Path:
    staging = stage_release(binary, platform, version, root=root, tag=tag)
    stem = archive_stem(version, tag)
    archive = outdir / archive_filename(stem, platform)
    try:
        write_archive(staging, archive)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        staging_root = staging.parent
        if staging_root.exists() and not any(staging_root.iterdir()):
            staging_root.rmdir()
    return archive


def write_checksums(outdir: Path) -> Path:
    archives = sorted(
        p
        for p in outdir.iterdir()
        if p.is_file() and p.name.startswith("nsce-") and not p.name.endswith(".sha256")
    )
    if not archives:
        raise ReleaseError(f"no nsce-* archives in {outdir}")
    lines = [f"{_sha256(path)}  {path.name}" for path in archives]
    checksums = outdir / "SHA256SUMS"
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums


def release_notes(version: str, generated: str = "") -> str:
    stem = f"nsce-{version}"
    body = (
        f"Precompiled UCI binaries for NSCE {version}.\n"
        "\n"
        "| Archive | Target |\n"
        "| --- | --- |\n"
        f"| `{stem}-linux-x86_64-avx2.tar.gz` | Linux x86-64, AVX2 NNUE kernels |\n"
        f"| `{stem}-windows-x86_64.zip` | Windows x86-64, AVX2+BMI2, statically linked |\n"
        "\n"
        "Point a UCI GUI at the engine binary. Load `configs/baseline.uci`, or set "
        "`EvalFile` to `nets/nnue_search_leaves40k_rw0.bin` (paths are relative to the "
        "working directory). Verify downloads with `SHA256SUMS`.\n"
    )
    generated = generated.strip()
    if generated:
        body += "\n" + generated + "\n"
    return body


def verify_uci(binary: Path, version: str, timeout: float = 15.0) -> str:
    if not binary.is_file():
        raise ReleaseError(f"binary not found: {binary}")
    try:
        proc = subprocess.run(
            [str(binary)],
            input="uci\nquit\n",
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"failed to run {binary}: {exc}") from exc
    expected = f"id name NSCE {version}"
    for line in (proc.stdout or "").splitlines():
        if line.strip() == expected:
            return expected
    snippet = (proc.stdout or proc.stderr or "").strip().splitlines()[:8]
    raise ReleaseError(
        f"{binary} did not advertise {expected!r}; output starts with: {snippet}"
    )


def _cmd_version(_args: argparse.Namespace) -> int:
    print(cmake_version())
    return 0


def _cmd_meta(args: argparse.Namespace) -> int:
    info = meta(args.ref)
    if args.github_output:
        _append_github_output(Path(args.github_output), info)
    if args.json:
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        for key in ("version", "tag", "prerelease", "archive_stem", "uci_name"):
            print(f"{key}={info[key]}")
    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    version = args.version or cmake_version()
    archive = pack(
        binary=args.binary,
        platform=args.platform,
        version=version,
        outdir=args.outdir,
        tag=args.tag or None,
    )
    print(archive)
    return 0


def _cmd_checksums(args: argparse.Namespace) -> int:
    path = write_checksums(args.outdir)
    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def _cmd_verify_uci(args: argparse.Namespace) -> int:
    version = args.version or cmake_version()
    print(verify_uci(args.binary, version))
    return 0


def _cmd_notes(args: argparse.Namespace) -> int:
    version = args.version or cmake_version()
    generated = ""
    if args.generated_notes_file:
        generated = Path(args.generated_notes_file).read_text(encoding="utf-8")
    sys.stdout.write(release_notes(version, generated))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print CMake project version")

    meta_p = sub.add_parser("meta", help="resolve version / tag metadata")
    meta_p.add_argument("--ref", default=os.environ.get("GITHUB_REF", ""), help="git ref (refs/tags/vX.Y.Z)")
    meta_p.add_argument("--github-output", type=Path, default=None)
    meta_p.add_argument("--json", action="store_true")

    pack_p = sub.add_parser("pack", help="stage and archive a release folder")
    pack_p.add_argument("--binary", type=Path, required=True)
    pack_p.add_argument("--platform", required=True)
    pack_p.add_argument("--version", default=None)
    pack_p.add_argument("--tag", default=None)
    pack_p.add_argument("--outdir", type=Path, default=ROOT / "dist")

    sum_p = sub.add_parser("checksums", help="write SHA256SUMS for nsce-* archives")
    sum_p.add_argument("--outdir", type=Path, default=ROOT / "dist")

    verify_p = sub.add_parser("verify-uci", help="require id name NSCE <version>")
    verify_p.add_argument("--binary", type=Path, required=True)
    verify_p.add_argument("--version", default=None)

    notes_p = sub.add_parser("notes", help="print GitHub Release preamble")
    notes_p.add_argument("--version", default=None)
    notes_p.add_argument("--generated-notes-file", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "version": _cmd_version,
        "meta": _cmd_meta,
        "pack": _cmd_pack,
        "checksums": _cmd_checksums,
        "verify-uci": _cmd_verify_uci,
        "notes": _cmd_notes,
    }
    try:
        return commands[args.command](args)
    except ReleaseError as exc:
        print(f"package_release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
