#!/usr/bin/env python3
# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Build official Android cores directly from qualified CorvusCore sources."""

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

from tools.validate_catalog import CORE_NAMES, MAX_ARCHIVE_SIZE, validate

SOURCE_REPOSITORY = "CorvusSoftware/CorvusCore"
NDK_VERSION = "27.2.12479018"
CMAKE_VERSION = "3.22.1"
ABIS = ("arm64-v8a", "x86_64")
EXPORTS = {"corvus_get_api", "corvus_get_achievements_api",
           "corvus_get_options_api", "corvus_get_subsystem_api"}
SYSTEM_LIBRARIES = {"libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so"}
REVISION = re.compile(r"[a-f0-9]{40}")
TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")


def project_version(text):
    match = re.search(r"\bproject\(\s*CorvusCore\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)\s+LANGUAGES\b", text)
    if match is None:
        raise ValueError("CorvusCore project version is missing")
    return match.group(1)


def check_cmake_version(reported):
    # Google's SDK build includes its Git revision after the package version.
    if re.fullmatch(r"cmake version " + re.escape(CMAKE_VERSION) + r"(?:-g[0-9a-f]+)?", reported) is None:
        raise ValueError("the pinned CMake version is required")


def qualified_run(payload, source_sha):
    """Accept only the upstream workflow's successful main push of this source."""
    if not isinstance(source_sha, str) or REVISION.fullmatch(source_sha) is None:
        raise ValueError("expected a complete lowercase source revision")
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    valid = [run["id"] for run in runs if isinstance(run, dict)
             and type(run.get("id")) is int and run["id"] > 0
             and run.get("head_sha") == source_sha
             and run.get("head_branch") == "main" and run.get("event") == "push"
             and run.get("status") == "completed" and run.get("conclusion") == "success"
             and isinstance(run.get("path"), str)
             and run.get("path", "").split("@", 1)[0] == ".github/workflows/ci.yml"
             and isinstance(run.get("head_repository"), dict)
             and run.get("head_repository", {}).get("full_name") == SOURCE_REPOSITORY]
    if not valid:
        raise ValueError("no successful upstream main CI exists for this exact source")
    return max(valid)


def elf_layout(data, abi):
    if abi not in ABIS or len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("expected a little-endian ELF64 module")
    kind, machine = struct.unpack_from("<HH", data, 16)
    if kind != 3 or machine != {"arm64-v8a": 183, "x86_64": 62}[abi]:
        raise ValueError("wrong shared-library type or Android architecture")
    offset = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    if stride < 56 or not 0 < count <= 256 or offset + stride * count > len(data):
        raise ValueError("invalid ELF program header bounds")
    loads = 0
    for index in range(count):
        position = offset + index * stride
        if struct.unpack_from("<I", data, position)[0] != 1:
            continue
        loads += 1
        file_offset, address, _, file_size, memory_size, align = struct.unpack_from("<QQQQQQ", data, position + 8)
        if (align < 16384 or align & (align - 1) or file_offset % align != address % align
                or file_size > memory_size or file_offset + file_size > len(data)):
            raise ValueError("invalid or non-16-KiB load segment")
    if not loads:
        raise ValueError("ELF has no loadable segment")


def verify_module(module, abi, llvm):
    data = module.read_bytes()
    elf_layout(data, abi)
    symbols = subprocess.check_output([str(llvm / "llvm-nm"), "-D", "--defined-only", str(module)], text=True)
    exported = {line.split()[-1] for line in symbols.splitlines() if line.split()}
    if not EXPORTS <= exported:
        raise ValueError("official module is missing a CorvusAPI extension export")
    dynamic = subprocess.check_output([str(llvm / "llvm-readelf"), "--dynamic", "--wide", str(module)], text=True)
    needed = set(re.findall(r"\(NEEDED\).*\[([^\]]+)\]", dynamic))
    if not needed <= SYSTEM_LIBRARIES:
        raise ValueError("module depends on an unshipped native library")
    return data


def write_archive(path, library, data):
    member = zipfile.ZipInfo(library, (2026, 1, 1, 0, 0, 0))
    member.create_system = 3
    member.external_attr = 0o100444 << 16
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(member, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if not 0 < path.stat().st_size <= MAX_ARCHIVE_SIZE:
        raise ValueError("archive exceeds the installer's size bound")


def configure_command(cmake, source, output, ndk, ninja, abi):
    if abi not in ABIS:
        raise ValueError("unsupported Android ABI")
    return [str(cmake), "-S", str(source), "-B", str(output), "-G", "Ninja",
            "-DCMAKE_MAKE_PROGRAM=" + str(ninja),
            "-DCMAKE_TOOLCHAIN_FILE=" + str(ndk / "build/cmake/android.toolchain.cmake"),
            "-DANDROID_ABI=" + abi, "-DANDROID_PLATFORM=android-26", "-DANDROID_STL=c++_static",
            "-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON", "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384",
            "-DBUILD_TESTING=OFF", "-DCORVUSCORE_BUILD_CORVUSAPI=ON", "-DCORVUSCORE_INSTALL=OFF"]


def git_revision(directory):
    return subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()


def build(args):
    if (REVISION.fullmatch(args.source_sha) is None or REVISION.fullmatch(args.repository_sha) is None
            or TAG.fullmatch(args.release_tag) is None or args.ci_run_id <= 0 or args.run_id <= 0
            or not 1 <= args.parallel <= 8):
        raise ValueError("invalid source, release or CI identity")
    source, build_root, output = args.source_dir.resolve(), args.build_root.resolve(), args.output_dir.resolve()
    if source == build_root or source in build_root.parents or source == output or source in output.parents:
        raise ValueError("build and distribution outputs must stay outside the source checkout")
    if output == build_root or output in build_root.parents or build_root in output.parents:
        raise ValueError("build and distribution directories must be separate")
    if output.exists() and any(output.iterdir()):
        raise ValueError("distribution output must be empty")
    if git_revision(source) != args.source_sha:
        raise ValueError("source checkout does not match the qualified revision")
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"], text=True)
    if dirty:
        raise ValueError("source or a pinned submodule is modified")
    api_sha = git_revision(source / "third_party/CorvusAPI")
    if REVISION.fullmatch(api_sha) is None:
        raise ValueError("invalid CorvusAPI revision")
    version = project_version((source / "CMakeLists.txt").read_text(encoding="utf-8"))
    ndk, cmake = args.ndk.resolve(), args.cmake.resolve()
    properties = (ndk / "source.properties").read_text(encoding="utf-8")
    if re.search(r"^Pkg\.Revision\s*=\s*" + re.escape(NDK_VERSION) + r"\s*$", properties, re.MULTILINE) is None:
        raise ValueError("the pinned NDK version is required")
    reported = subprocess.check_output([str(cmake), "--version"], text=True).splitlines()[0]
    check_cmake_version(reported)
    ninja = cmake.parent / "ninja"
    if not ninja.is_file():
        found = shutil.which("ninja")
        if not found:
            raise ValueError("Ninja is unavailable")
        ninja = Path(found)
    llvm = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for abi in ABIS:
        destination = build_root / abi
        subprocess.run(configure_command(cmake, source, destination, ndk, ninja, abi), check=True)
        subprocess.run([str(cmake), "--build", str(destination), "--parallel", str(args.parallel),
                        "--target", "corvus_gb", "corvus_gbc", "corvus_gba"], check=True)
        for ident, (name, library) in CORE_NAMES.items():
            data = verify_module(destination / library, abi, llvm)
            archive = output / f"{name}-{version}-android-{abi}.zip"
            write_archive(archive, library, data)
            entries.append({"id": ident, "name": name, "description": {
                "corvus.gb": "Game Boy", "corvus.gbc": "Game Boy Color", "corvus.gba": "Game Boy Advance"}[ident],
                "version": version, "abi": abi, "api_version": 0, "library_name": library,
                "size": archive.stat().st_size, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "archive_url": "https://github.com/CorvusSoftware/CorvusRepository/releases/download/" +
                               args.release_tag + "/" + archive.name})
    catalog = {"format": 3, "cores": entries}
    if git_revision(source) != args.source_sha or git_revision(source / "third_party/CorvusAPI") != api_sha:
        raise ValueError("source identity changed during the build")
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"], text=True):
        raise ValueError("source was modified during the build")
    validate(catalog)
    (output / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    provenance = {"format": 1, "provider": "corvuscore", "repository": SOURCE_REPOSITORY,
                  "source_sha": args.source_sha, "corvusapi_sha": api_sha, "version": version,
                  "ci_run_id": args.ci_run_id, "repository_sha": args.repository_sha,
                  "distribution_run_id": args.run_id, "api_version": 0,
                  "toolchain": {"ndk": NDK_VERSION, "cmake": CMAKE_VERSION,
                                "platform": 26, "stl": "c++_static", "build_type": "Release"}}
    (output / "source.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    checksums = [hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name
                 for path in sorted(output.iterdir())]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-dir", "build-root", "output-dir", "ndk", "cmake"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("source-sha", "repository-sha", "release-tag"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--ci-run-id", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--parallel", type=int, default=2)
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Core build failed: " + str(error) + "\n")
    print("PASS six standalone official Android archives, qualified source and complete provenance")


if __name__ == "__main__":
    main()
