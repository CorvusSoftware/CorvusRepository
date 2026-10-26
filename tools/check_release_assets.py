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
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from tools.validate_catalog import RELEASE_PREFIX, validate


def verify(catalog):
    entries = validate(catalog)
    releases = {}
    for entry in entries:
        relative = urlsplit(entry["archive_url"]).path[len(RELEASE_PREFIX):]
        tag, filename = relative.split("/")
        if tag not in releases:
            address = f"https://api.github.com/repos/CorvusSoftware/CorvusRetro/releases/tags/{tag}"
            request = Request(address, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "CorvusRepository-asset-check",
            })
            with urlopen(request, timeout=20) as response:
                releases[tag] = json.load(response)
        asset = next((item for item in releases[tag].get("assets", [])
                      if item.get("name") == filename), None)
        if (asset is None or asset.get("browser_download_url") != entry["archive_url"]
                or asset.get("size") != entry["size"]
                or asset.get("digest") != "sha256:" + entry["sha256"]):
            raise ValueError(f"Release asset metadata mismatch: {tag}/{filename}")
    return len(entries)


if __name__ == "__main__":
    try:
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("catalog/corvuscore.json")
        count = verify(json.loads(path.read_text(encoding="utf-8")))
        print(f"OK: {count} GitHub release asset size/digest records match")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Asset verification failed: {error}")
