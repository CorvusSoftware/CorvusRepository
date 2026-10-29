#!/usr/bin/env python3
# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Validate every curated catalog in catalog/; never fetch or execute modules."""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

CORE_NAMES = {
    "corvus.gb": ("CorvusGB", "libcorvus_gb.so"),
    "corvus.gbc": ("CorvusGBC", "libcorvus_gbc.so"),
    "corvus.gba": ("CorvusGBA", "libcorvus_gba.so"),
}
ABIS = {"arm64-v8a", "x86_64"}
FIELDS = {"id", "name", "description", "version", "abi", "api_version",
          "library_name", "size", "sha256", "archive_url"}
MAX_ARCHIVE_SIZE = 32 * 1024 * 1024
MAX_CATALOG_SIZE = 96 * 1024
MAX_CATALOGS = 16
MAX_CORES = 32
PROVIDER = re.compile(r"[a-z][a-z0-9_-]{0,39}\.json")
CORE_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}(?:\.[a-z0-9_-]{1,39})+")
LIBRARY = re.compile(r"lib[a-z0-9_]{1,60}\.so")
RELEASE = re.compile(r"/CorvusSoftware/(CorvusRetro|CorvusRepository)/releases/download/(v[0-9]+\.[0-9]+\.[0-9]+)/([A-Za-z0-9][A-Za-z0-9._-]*\.zip)")


def release_asset(address):
    """Return the approved repository, release tag and exact asset filename."""
    if (not isinstance(address, str) or len(address) > 256
            or any(ord(c) <= 32 or ord(c) >= 127 or c in "\\%" for c in address)):
        raise ValueError("invalid archive URL")
    url = urlsplit(address)
    match = RELEASE.fullmatch(url.path)
    if (url.scheme != "https" or url.netloc != "github.com" or url.query or url.fragment
            or match is None):
        raise ValueError("untrusted release URL")
    return "CorvusSoftware/" + match.group(1), match.group(2), match.group(3)


def validate(payload, provider="corvuscore.json"):
    if not isinstance(provider, str) or not PROVIDER.fullmatch(provider):
        raise ValueError("unsafe catalog file name")
    if (not isinstance(payload, dict) or set(payload) != {"format", "cores"}
            or type(payload["format"]) is not int or payload["format"] != 3):
        raise ValueError("expected a format-3 catalog with only format and cores")

    entries = payload["cores"]
    if not isinstance(entries, list) or len(entries) > MAX_CORES:
        raise ValueError("invalid number of entries")

    found = set()
    prefix = provider[:-5] + "."
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise ValueError("invalid entry fields")
        ident, name, library = entry["id"], entry["name"], entry["library_name"]
        if not isinstance(ident, str) or len(ident) > 95 or not CORE_ID.fullmatch(ident):
            raise ValueError("unsafe core identifier")
        if provider == "corvuscore.json":
            if ident not in CORE_NAMES:
                raise ValueError("unknown official core")
            expected_name, expected_library = CORE_NAMES[ident]
            if name != expected_name or library != expected_library:
                raise ValueError("official identity mismatch")
        elif not ident.startswith(prefix):
            raise ValueError("provider/core namespace mismatch")
        if not isinstance(library, str) or not LIBRARY.fullmatch(library):
            raise ValueError("unsafe library name")
        for field in ("name", "description"):
            value = entry[field]
            if (not isinstance(value, str) or not 1 <= len(value) <= 128
                    or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
                raise ValueError("invalid " + field)
        version = entry["version"]
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise ValueError("invalid core version")
        abi = entry["abi"]
        if not isinstance(abi, str) or abi not in ABIS:
            raise ValueError("unsupported Android architecture")
        if type(entry["api_version"]) is not int or entry["api_version"] != 0:
            raise ValueError("unsupported CorvusAPI version")
        if type(entry["size"]) is not int or not 0 < entry["size"] <= MAX_ARCHIVE_SIZE:
            raise ValueError("invalid archive size")
        digest = entry["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid archive checksum")

        _, _, filename = release_asset(entry["archive_url"])
        if provider == "corvuscore.json":
            expected_file = f"{name}-{version}-android-{abi}.zip"
            if filename != expected_file:
                raise ValueError("official release asset mismatch")

        key = (ident, abi)
        if key in found:
            raise ValueError("duplicate core/architecture")
        found.add(key)

    if provider == "corvuscore.json":
        expected = {(ident, abi) for ident in CORE_NAMES for abi in ABIS}
        if found != expected:
            raise ValueError("missing or extra official core/architecture")
    return entries


def validate_directory(directory):
    paths = sorted(directory.glob("*.json"))
    if not paths or len(paths) > MAX_CATALOGS:
        raise ValueError("invalid catalog count")
    ids = set()
    total = 0
    for path in paths:
        if path.stat().st_size > MAX_CATALOG_SIZE:
            raise ValueError("catalog too large: " + path.name)
        entries = validate(json.loads(path.read_text(encoding="utf-8")), path.name)
        for core in entries:
            key = (core["id"], core["abi"])
            if key in ids:
                raise ValueError("duplicate core across catalog files")
            ids.add(key)
            total += 1
    if not (directory / "corvuscore.json").is_file() or total > MAX_CORES:
        raise ValueError("missing CorvusCore feed or too many cores")
    return len(paths), total


def main():
    target = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("catalog")
    if target.is_dir():
        count, entries = validate_directory(target)
        print(f"OK: {count} catalogs, {entries} core/ABI entries")
    else:
        entries = validate(json.loads(target.read_text(encoding="utf-8")), target.name)
        print(f"OK: {len(entries)} verified schema entries")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Catalog validation failed: {error}")
