from __future__ import annotations

import io
import json
import stat
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import package_release as rel  # noqa: E402


class VersionMetaTest(unittest.TestCase):
    def test_cmake_version_matches_project(self) -> None:
        version = rel.cmake_version(ROOT)
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn(f"project(nsce VERSION {version}", cmake)

    def test_uci_source_uses_cmake_macro(self) -> None:
        uci = (ROOT / "engine/src/uci.cpp").read_text(encoding="utf-8")
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("NSCE_VERSION", uci)
        self.assertNotRegex(uci, r'id name NSCE \d')
        self.assertIn("NSCE_VERSION=", cmake)
        self.assertIn("${PROJECT_VERSION}", cmake)

    def test_tag_must_match_cmake_version(self) -> None:
        version = rel.cmake_version(ROOT)
        info = rel.meta(f"refs/tags/v{version}", root=ROOT)
        self.assertEqual(info["version"], version)
        self.assertEqual(info["tag"], f"v{version}")
        self.assertEqual(info["prerelease"], "false")
        self.assertEqual(info["uci_name"], f"NSCE {version}")
        self.assertEqual(info["archive_stem"], f"nsce-{version}")

        with self.assertRaises(rel.ReleaseError):
            rel.meta("refs/tags/v0.0.0", root=ROOT)
        with self.assertRaises(rel.ReleaseError):
            rel.meta("refs/tags/not-a-version", root=ROOT)

    def test_prerelease_tag_and_branch_ref(self) -> None:
        version = rel.cmake_version(ROOT)
        info = rel.meta(f"v{version}-rc.1", root=ROOT)
        self.assertEqual(info["prerelease"], "true")
        self.assertEqual(info["tag"], f"v{version}-rc.1")
        self.assertEqual(info["archive_stem"], f"nsce-{version}-rc.1")

        branch = rel.meta("refs/heads/master", root=ROOT)
        self.assertEqual(branch["tag"], "")
        self.assertEqual(branch["version"], version)
        self.assertEqual(branch["prerelease"], "false")

    def test_meta_cli_writes_github_output(self) -> None:
        version = rel.cmake_version(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "github_output"
            buffer = io.StringIO()
            old = sys.stdout
            sys.stdout = buffer
            try:
                rc = rel.main(
                    [
                        "meta",
                        "--ref",
                        f"refs/tags/v{version}",
                        "--github-output",
                        str(out),
                        "--json",
                    ]
                )
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["version"], version)
            self.assertEqual(payload["tag"], f"v{version}")
            text = out.read_text(encoding="utf-8")
            self.assertIn(f"version={version}", text)
            self.assertIn(f"tag=v{version}", text)
            self.assertIn("prerelease=false", text)

    def test_release_notes_include_archive_table(self) -> None:
        text = rel.release_notes("0.11.0", generated="- shipped the packager")
        self.assertIn("NSCE 0.11.0", text)
        self.assertIn("nsce-0.11.0-linux-x86_64-avx2.tar.gz", text)
        self.assertIn("nsce-0.11.0-windows-x86_64.zip", text)
        self.assertIn("configs/baseline.uci", text)
        self.assertIn("- shipped the packager", text)


class PackArchiveTest(unittest.TestCase):
    def _fake_root(self, tmp: Path) -> Path:
        (tmp / "nets").mkdir()
        (tmp / "tools/configs").mkdir(parents=True)
        (tmp / "LICENSE").write_text("GPL\n", encoding="utf-8")
        (tmp / "README.md").write_text("# NSCE\n", encoding="utf-8")
        (tmp / "CMakeLists.txt").write_text(
            "project(nsce VERSION 0.11.0 LANGUAGES CXX)\n", encoding="utf-8"
        )
        for net in rel.RELEASE_NETS:
            (tmp / net).write_bytes(b"NET")
        (tmp / rel.RELEASE_CONFIG).write_text("setoption name Hash value 16\n", encoding="utf-8")
        return tmp

    def test_linux_archive_layout_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = self._fake_root(Path(raw))
            binary = root / "nsce"
            binary.write_bytes(b"#!/bin/sh\n")
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
            outdir = root / "dist"
            archive = rel.pack(
                binary=binary,
                platform="linux-x86_64-avx2",
                version="0.11.0",
                outdir=outdir,
                root=root,
            )
            self.assertEqual(archive.name, "nsce-0.11.0-linux-x86_64-avx2.tar.gz")
            with tarfile.open(archive, "r:gz") as tar:
                names = set(tar.getnames())
            prefix = "nsce-0.11.0-linux-x86_64-avx2"
            self.assertIn(f"{prefix}/nsce", names)
            self.assertIn(f"{prefix}/LICENSE", names)
            self.assertIn(f"{prefix}/PLAYING.txt", names)
            self.assertIn(f"{prefix}/configs/baseline.uci", names)
            self.assertIn(f"{prefix}/nets/nnue_trained.bin", names)
            self.assertIn(f"{prefix}/nets/nnue_search_leaves40k_rw0.bin", names)
            with tarfile.open(archive, "r:gz") as tar:
                nsce = tar.getmember(f"{prefix}/nsce")
                self.assertTrue(nsce.mode & stat.S_IXUSR)
            checksums = rel.write_checksums(outdir)
            line = checksums.read_text(encoding="utf-8").strip()
            self.assertIn(archive.name, line)
            digest, name = line.split()
            self.assertEqual(len(digest), 64)
            self.assertEqual(name, archive.name)

    def test_windows_archive_uses_exe_and_zip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = self._fake_root(Path(raw))
            binary = root / "nsce.exe"
            binary.write_bytes(b"MZ")
            archive = rel.pack(
                binary=binary,
                platform="windows-x86_64",
                version="0.11.0",
                outdir=root / "dist",
                root=root,
                tag="v0.11.0-rc.1",
            )
            self.assertEqual(archive.name, "nsce-0.11.0-rc.1-windows-x86_64.zip")
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
            prefix = "nsce-0.11.0-rc.1-windows-x86_64"
            self.assertIn(f"{prefix}/nsce.exe", names)
            self.assertNotIn(f"{prefix}/nsce", names)

    def test_missing_binary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = self._fake_root(Path(raw))
            with self.assertRaises(rel.ReleaseError):
                rel.pack(
                    binary=root / "missing",
                    platform="linux-x86_64-avx2",
                    version="0.11.0",
                    outdir=root / "dist",
                    root=root,
                )


class WorkflowContractTest(unittest.TestCase):
    def test_release_workflow_is_tag_driven(self) -> None:
        text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("name: Release", text)
        self.assertIn("v*.*.*", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn("tools/package_release.py", text)
        self.assertIn("cmake/mingw-w64-x86_64.cmake", text)
        self.assertIn("contents: write", text)
        self.assertIn("gh release create", text)


if __name__ == "__main__":
    unittest.main()
