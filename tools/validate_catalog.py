#!/usr/bin/env python3
# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Validate the current CorvusRetro native core catalog without downloading code."""

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
FIELDS = {
    "id", "name", "description", "version", "abi", "api_version",
    "library_name", "size", "sha256", "archive_url",
}
RELEASE_PREFIX = "/CorvusSoftware/CorvusRetro/releases/download/"
MAX_ARCHIVE_SIZE = 32 * 1024 * 1024


def validate(payload):
    if (not isinstance(payload, dict) or set(payload) != {"format", "cores"}
            or type(payload["format"]) is not int or payload["format"] != 3):
        raise ValueError("expected a format-3 catalog with only format and cores")

    entries = payload["cores"]
    if not isinstance(entries, list) or len(entries) > 32:
        raise ValueError("invalid number of entries")

    found = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise ValueError("invalid entry fields")
        ident = entry["id"]
        if not isinstance(ident, str) or ident not in CORE_NAMES:
            raise ValueError("unsupported core identifier")
        expected_name, expected_library = CORE_NAMES[ident]
        if entry["name"] != expected_name or entry["library_name"] != expected_library:
            raise ValueError("core name or library mismatch")
        description = entry["description"]
        if (not isinstance(description, str) or not 1 <= len(description) <= 128
                or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in description)):
            raise ValueError("invalid description")
        version = entry["version"]
        if (not isinstance(version, str)
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)):
            raise ValueError("invalid core version")
        abi = entry["abi"]
        if not isinstance(abi, str) or abi not in ABIS:
            raise ValueError("unsupported Android architecture")
        if type(entry["api_version"]) is not int or entry["api_version"] != 0:
            raise ValueError("unsupported CorvusAPI version")
        if (type(entry["size"]) is not int
                or not 0 < entry["size"] <= MAX_ARCHIVE_SIZE):
            raise ValueError("invalid archive size")
        digest = entry["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid archive checksum")

        address = entry["archive_url"]
        if (not isinstance(address, str) or len(address) > 256
                or any(ord(c) <= 32 or ord(c) >= 127 or c in "\\%" for c in address)):
            raise ValueError("invalid archive URL")
        parsed = urlsplit(address)
        if (parsed.scheme != "https" or parsed.netloc != "github.com"
                or parsed.query or parsed.fragment
                or not parsed.path.startswith(RELEASE_PREFIX)):
            raise ValueError("untrusted release host")
        relative = parsed.path[len(RELEASE_PREFIX):].split("/")
        expected_archive = f"{expected_name}-{version}-android-{abi}.zip"
        if (len(relative) != 2 or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", relative[0])
                or relative[1] != expected_archive):
            raise ValueError("unexpected release tag or archive name")

        key = (ident, abi)
        if key in found:
            raise ValueError("duplicate core/architecture")
        found.add(key)

    expected = {(ident, abi) for ident in CORE_NAMES for abi in ABIS}
    if found != expected:
        raise ValueError("missing or extra core/architecture entries")
    return entries


def main():
    catalog = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("cores-v3.json")
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    entries = validate(payload)
    print(f"OK: {len(entries)} verified schema entries (offline; asset bytes not fetched)")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Catalog validation failed: {error}")
