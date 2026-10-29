#!/usr/bin/env python3
# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Check published GitHub release asset digests and sizes against the catalog.

This is an optional online verification; the normal CI validates metadata
offline and never downloads executable ZIP files.
"""

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from tools.validate_catalog import MAX_CATALOG_SIZE, release_asset, validate, validate_directory


def verify(catalog, provider="corvuscore.json", releases=None):
    entries = validate(catalog, provider)
    if releases is None:
        releases = {}
    for entry in entries:
        repository, tag, filename = release_asset(entry["archive_url"])
        key = (repository, tag)
        if key not in releases:
            address = f"https://api.github.com/repos/{repository}/releases/tags/{tag}"
            request = Request(address, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "CorvusRepository-asset-check",
            })
            with urlopen(request, timeout=20) as response:
                releases[key] = json.load(response)
        release = releases[key]
        if (not isinstance(release, dict) or release.get("tag_name") != tag
                or release.get("draft") is not False
                or not isinstance(release.get("assets"), list)
                or any(not isinstance(item, dict) for item in release["assets"])):
            raise ValueError(f"Invalid public release metadata: {repository}/{tag}")
        asset = next((item for item in release["assets"]
                      if item.get("name") == filename), None)
        if (asset is None or asset.get("browser_download_url") != entry["archive_url"]
                or type(asset.get("size")) is not int or asset["size"] != entry["size"]
                or asset.get("digest") != "sha256:" + entry["sha256"]):
            raise ValueError(f"Release asset metadata mismatch: {repository}/{tag}/{filename}")
    return len(entries)


def verify_path(path):
    """Validate all local inputs before querying any approved release metadata."""
    path = Path(path)
    if path.is_dir():
        validate_directory(path)
        paths = sorted(path.glob("*.json"))
    else:
        paths = [path]
    catalogs = []
    for source in paths:
        if source.stat().st_size > MAX_CATALOG_SIZE:
            raise ValueError("catalog too large: " + source.name)
        payload = json.loads(source.read_text(encoding="utf-8"))
        validate(payload, source.name)
        catalogs.append((source.name, payload))
    releases = {}
    return sum(verify(payload, provider, releases) for provider, payload in catalogs)


if __name__ == "__main__":
    try:
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("catalog/v1")
        count = verify_path(path)
        print(f"OK: {count} GitHub release asset size/digest records match")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Asset verification failed: {error}")
