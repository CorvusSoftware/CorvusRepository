#!/usr/bin/env python3
# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Stage reviewed upstream release assets without loading native code."""

import copy
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from tools.validate_catalog import MAX_ARCHIVE_SIZE, MAX_CATALOG_SIZE, validate

CENTRAL = "CorvusSoftware/CorvusRepository"
TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}")
SHA = re.compile(r"[a-f0-9]{40}")


def _distribution():
    from tools import core_distribution
    return core_distribution


def gh_json(endpoint):
    result = subprocess.run(["gh", "api", endpoint], check=True,
                            capture_output=True, text=True)
    return json.loads(result.stdout)


def source_commit(repository, tag):
    item = gh_json(f"repos/{repository}/git/ref/tags/{tag}").get("object", {})
    for _ in range(5):
        if not isinstance(item, dict) or not SHA.fullmatch(str(item.get("sha", ""))):
            break
        if item.get("type") == "commit":
            return item["sha"]
        if item.get("type") != "tag":
            break
        item = gh_json(f"repos/{repository}/git/tags/{item['sha']}").get("object", {})
    raise ValueError("upstream tag does not resolve to an immutable source commit")


def _asset(release, repository, tag, filename, limit):
    if not isinstance(filename, str) or not FILENAME.fullmatch(filename):
        raise ValueError("unsafe upstream asset name")
    matches = [asset for asset in release["assets"] if asset.get("name") == filename]
    if len(matches) != 1:
        raise ValueError("missing or duplicate upstream release asset: " + filename)
    asset = matches[0]
    expected = f"https://github.com/{repository}/releases/download/{tag}/{filename}"
    digest = asset.get("digest", "")
    if (asset.get("browser_download_url") != expected
            or type(asset.get("size")) is not int or not 0 < asset["size"] <= limit
            or not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest)):
        raise ValueError("invalid upstream asset metadata: " + filename)
    return asset


def _download(repository, tag, asset, directory, limit):
    destination = directory / asset["name"]
    if destination.exists() or destination.is_symlink():
        raise ValueError("duplicate asset output")
    subprocess.run(["gh", "release", "download", tag, "--repo", repository,
                    "--pattern", asset["name"], "--dir", str(directory)],
                   check=True, capture_output=True, text=True)
    if (destination.is_symlink() or not destination.is_file()
            or destination.stat().st_size != asset["size"]
            or destination.stat().st_size > limit):
        raise ValueError("downloaded asset size mismatch")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    if "sha256:" + digest != asset["digest"]:
        raise ValueError("downloaded asset checksum mismatch")
    return destination


def _upstream_name(address, repository, tag):
    if (not isinstance(address, str) or len(address) > 512
            or any(ord(c) < 33 or ord(c) > 126 or c in "\\%" for c in address)):
        raise ValueError("invalid upstream archive URL")
    parsed = urlsplit(address)
    prefix = f"/{repository}/releases/download/{tag}/"
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or parsed.query or parsed.fragment or not parsed.path.startswith(prefix)):
        raise ValueError("upstream archive must belong to the approved repository and release")
    filename = parsed.path[len(prefix):]
    if not FILENAME.fullmatch(filename) or not filename.endswith(".zip"):
        raise ValueError("unsafe upstream ZIP filename")
    return filename


def import_bundle(name, upstream_tag, tag, output):
    """Verify upstream provenance and stage a central-origin candidate bundle.

    This function never publishes a release, modifies Git, or executes a core.
    The CLI separately invokes the publisher unless explicitly using dry-run.
    """
    if (not isinstance(upstream_tag, str) or len(upstream_tag) > 64
            or not TAG.fullmatch(upstream_tag) or not isinstance(tag, str)
            or len(tag) > 64 or not TAG.fullmatch(tag)):
        raise ValueError("release tags must be vX.Y.Z")
    distribution = _distribution()
    registry = distribution.provider(name)
    if name == "corvuscore":
        raise ValueError("official CorvusCore must use the qualified source build workflow")
    output = Path(output)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("output directory must be absent or empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    repository = registry["repository"]
    release = gh_json(f"repos/{repository}/releases/tags/{upstream_tag}")
    if (not isinstance(release, dict) or release.get("tag_name") != upstream_tag
            or release.get("draft") is not False or not isinstance(release.get("assets"), list)
            or any(not isinstance(item, dict) for item in release["assets"])):
        raise ValueError("upstream release is not public or does not match the requested tag")
    with tempfile.TemporaryDirectory(prefix=".corvus-import-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        metadata = Path(temporary) / "metadata"
        metadata.mkdir()
        documents = []
        for field in ("manifest_asset", "provenance_asset"):
            asset = _asset(release, repository, upstream_tag, registry[field], MAX_CATALOG_SIZE)
            document = _download(repository, upstream_tag, asset, metadata, MAX_CATALOG_SIZE)
            documents.append(json.loads(document.read_text(encoding="utf-8")))
        upstream_catalog, provenance = documents
        distribution.check_source(registry, provenance)
        # Keep only the documented source contract in public provenance.
        # Upstream metadata cannot smuggle unrelated release fields into ours.
        source_fields = {"format", "provider", "repository", "source_sha",
                         "version", "ci_run_id", "corvusapi_sha"}
        provenance = {key: value for key, value in provenance.items() if key in source_fields}
        provenance["upstream_tag"] = upstream_tag
        if provenance["source_sha"] != source_commit(repository, upstream_tag):
            raise ValueError("upstream release tag and qualified source commit differ")
        catalog = copy.deepcopy(upstream_catalog)
        if not isinstance(catalog, dict) or not isinstance(catalog.get("cores"), list):
            raise ValueError("invalid upstream catalog")
        filenames = []
        for entry in catalog["cores"]:
            if not isinstance(entry, dict):
                raise ValueError("invalid upstream core entry")
            filename = _upstream_name(entry.get("archive_url"), repository, upstream_tag)
            filenames.append(filename)
            entry["archive_url"] = f"https://github.com/{CENTRAL}/releases/download/{tag}/{filename}"
        entries = validate(catalog, name + ".json")
        if not entries or len(set(filenames)) != len(filenames):
            raise ValueError("empty catalog or duplicate upstream archive names")
        for entry, filename in zip(entries, filenames):
            asset = _asset(release, repository, upstream_tag, filename, MAX_ARCHIVE_SIZE)
            if asset["size"] != entry["size"] or asset["digest"] != "sha256:" + entry["sha256"]:
                raise ValueError("upstream catalog and release asset metadata differ")
            _download(repository, upstream_tag, asset, staging, MAX_ARCHIVE_SIZE)
        distribution.validate_bundle(name, tag, catalog, provenance, staging)
        (staging / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        (staging / "source.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        if output.exists():
            output.rmdir()
        staging.rename(output)
    return catalog, provenance
