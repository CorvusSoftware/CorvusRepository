# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Offline checks for the source gate, Android ABI and native packaging."""

import hashlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.build_corvuscore import (ABIS, EXPORTS, SOURCE_REPOSITORY, check_cmake_version, configure_command,
                                   elf_layout, project_version, qualified_run,
                                   verify_module, write_archive)

SHA = "a" * 40


def run(**changes):
    data = {"id": 100, "head_sha": SHA, "head_branch": "main", "event": "push",
            "status": "completed", "conclusion": "success", "path": ".github/workflows/ci.yml",
            "head_repository": {"full_name": SOURCE_REPOSITORY}}
    data.update(changes)
    return data


def elf(abi="x86_64"):
    data = bytearray(120)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<HH", data, 16, 3, 62 if abi == "x86_64" else 183)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, len(data), len(data), 16384)
    return data


class CoreBuildTests(unittest.TestCase):
    def test_sdk_cmake_vendor_revision_is_accepted_without_version_drift(self):
        for reported in ("cmake version 3.22.1", "cmake version 3.22.1-g37088a8"):
            check_cmake_version(reported)
        for reported in ("cmake version 3.22.10", "cmake version 3.22.1-malicious", "cmake version 3.23.0"):
            with self.assertRaises(ValueError):
                check_cmake_version(reported)

    def test_exact_successful_main_source_is_required(self):
        self.assertEqual(qualified_run({"workflow_runs": [run(id=100), run(id=101)]}, SHA), 101)
        for changes in ({"head_sha": "b" * 40}, {"head_branch": "feature"}, {"event": "pull_request"},
                        {"conclusion": "failure"}, {"status": "in_progress"}, {"id": True},
                        {"path": ".github/workflows/release.yml"}, {"path": None},
                        {"head_repository": None}, {"head_repository": {"full_name": "other/Core"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                qualified_run({"workflow_runs": [run(**changes)]}, SHA)
        with self.assertRaises(ValueError):
            qualified_run({"workflow_runs": [run()]}, SHA[:7])

    def test_canonical_project_version(self):
        self.assertEqual(project_version("project(CorvusCore VERSION 0.15.0 LANGUAGES CXX)"), "0.15.0")
        for source in ("project(Other VERSION 0.15.0 LANGUAGES CXX)",
                       "project(CorvusCore VERSION 0.15 LANGUAGES CXX)"):
            with self.assertRaises(ValueError):
                project_version(source)

    def test_elf_architecture_and_page_layout(self):
        for abi in ABIS:
            elf_layout(elf(abi), abi)
        invalid = []
        bad = elf(); struct.pack_into("<Q", bad, 112, 4096); invalid.append(bad)
        bad = elf(); struct.pack_into("<Q", bad, 32, 1000); invalid.append(bad)
        bad = elf(); struct.pack_into("<Q", bad, 96, len(bad) + 1); invalid.append(bad)
        bad = elf(); struct.pack_into("<Q", bad, 72, 1); invalid.append(bad)
        bad = elf(); struct.pack_into("<I", bad, 64, 2); invalid.append(bad)
        invalid.extend((elf()[:40], elf("arm64-v8a")))
        for data in invalid:
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                elf_layout(data, "x86_64")

    def test_exports_and_standalone_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "libcorvus_gb.so"
            module.write_bytes(elf())
            symbols = "\n".join("0000 T " + item for item in EXPORTS)
            with patch("subprocess.check_output", side_effect=[symbols, "(NEEDED) Shared library: [libc.so]"]):
                self.assertEqual(verify_module(module, "x86_64", Path("/llvm")), elf())
            with patch("subprocess.check_output", return_value="0000 T corvus_get_api"), self.assertRaises(ValueError):
                verify_module(module, "x86_64", Path("/llvm"))
            with patch("subprocess.check_output", side_effect=[symbols, "(NEEDED) Shared library: [libc++_shared.so]"]), self.assertRaises(ValueError):
                verify_module(module, "x86_64", Path("/llvm"))

    def test_archive_contains_one_exact_readonly_module(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.zip", Path(directory) / "second.zip"
            write_archive(first, "libcorvus_gb.so", elf())
            write_archive(second, "libcorvus_gb.so", elf())
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["libcorvus_gb.so"])
                self.assertEqual(archive.read("libcorvus_gb.so"), elf())
                self.assertEqual((archive.infolist()[0].external_attr >> 16) & 0o777, 0o444)

    def test_build_configuration_has_no_frontend_dependency(self):
        command = configure_command(Path("/cmake"), Path("/core"), Path("/build"),
                                    Path("/ndk"), Path("/ninja"), "arm64-v8a")
        for flag in ("-DCORVUSCORE_BUILD_CORVUSAPI=ON", "-DBUILD_TESTING=OFF", "-DCORVUSCORE_INSTALL=OFF",
                     "-DANDROID_STL=c++_static", "-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON",
                     "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384"):
            self.assertIn(flag, command)
        self.assertFalse(any(word in " ".join(command) for word in ("CorvusRetro", "gradle", "apk")))


if __name__ == "__main__":
    unittest.main()
