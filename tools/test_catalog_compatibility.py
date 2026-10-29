# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Keep the published 0.18.0 feed isolated from canonical catalog promotion."""

import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from tools import core_distribution as dist
from tools.validate_catalog import release_asset, validate, validate_directory


class CatalogCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.legacy_path = dist.ROOT / "catalog" / "corvuscore.json"
        self.canonical_path = dist.ROOT / "catalog" / "v1" / "corvuscore.json"
        self.legacy = json.loads(self.legacy_path.read_text())
        self.canonical = json.loads(self.canonical_path.read_text())

    def test_legacy_feed_is_byte_exact_published_0180_catalog(self):
        # Git commit 43218e491e181e4966f0a7a20748f340539e10c6, before central migration.
        self.assertEqual(hashlib.sha256(self.legacy_path.read_bytes()).hexdigest(),
                         "4eb5c5efac3e5d899f83071233ca0384cb148c8ed891818eb0d1711e3258aa52")
        self.assertEqual(validate_directory(self.legacy_path.parent), (1, 6))
        for entry in self.legacy["cores"]:
            self.assertEqual(release_asset(entry["archive_url"])[:2],
                             ("CorvusSoftware/CorvusRetro", "v0.18.0"))

    def test_canonical_feed_has_six_central_archives_with_same_core_identity(self):
        validate_directory(self.canonical_path.parent)
        self.assertEqual(len(validate(self.canonical)), 6)
        identity = lambda entry: tuple(entry[key] for key in
                                      ("id", "abi", "api_version", "library_name"))
        self.assertEqual({identity(item) for item in self.legacy["cores"]},
                         {identity(item) for item in self.canonical["cores"]})
        for entry in self.canonical["cores"]:
            self.assertEqual(release_asset(entry["archive_url"])[0],
                             "CorvusSoftware/CorvusRepository")

    def test_promotion_writes_only_versioned_catalog(self):
        entry = dict(self.canonical["cores"][0], id="example.gb", name="ExampleGB",
                     library_name="libexample.so", archive_url=
                     "https://github.com/CorvusSoftware/CorvusRepository/releases/download/v1.0.0/Example.zip")
        catalog = {"format": 3, "cores": [entry]}
        prefix = "repos/CorvusSoftware/CorvusRepository/"
        legacy_before = self.legacy_path.read_bytes()
        writes = []
        reads = []

        def fake_api(endpoint, **fields):
            if "contents/" in endpoint:
                # Fail immediately if any contents access reaches the legacy path.
                self.assertTrue(endpoint.startswith(prefix + "contents/catalog/v1"), endpoint)
            if endpoint == prefix + "git/ref/heads/main":
                return {"object": {"sha": "a" * 40}}
            if endpoint == prefix + "contents/catalog/v1?ref=" + "a" * 40:
                return [{"name": "corvuscore.json", "sha": "b" * 40}]
            if endpoint.startswith(prefix + "contents/catalog/v1/corvuscore.json?ref="):
                reads.append(endpoint)
                return {"content": base64.b64encode(self.canonical_path.read_bytes()).decode()}
            if endpoint.startswith(prefix + "git/matching-refs/"):
                return []
            if endpoint == prefix + "git/refs":
                return {}
            if endpoint == prefix + "contents/catalog/v1/example.json":
                self.assertEqual(fields["_method"], "PUT")
                writes.append(json.loads(base64.b64decode(fields["content"])))
                return {}
            if endpoint.startswith(prefix + "pulls?"):
                return [{"html_url": "https://github.com/CorvusSoftware/CorvusRepository/pull/123"}]
            self.fail("unexpected API call: " + endpoint)

        with patch.object(dist, "api", side_effect=fake_api), patch.object(dist, "gh"):
            result = dist.promote_catalog("example", "v1.0.0", catalog)
        self.assertTrue(reads)
        self.assertEqual(writes, [catalog])
        self.assertEqual(result["branch"], "catalog/example-v1.0.0")
        self.assertEqual(self.legacy_path.read_bytes(), legacy_before)


if __name__ == "__main__":
    unittest.main()
