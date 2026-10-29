# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Offline regression tests for the catalog schema and trust boundary."""

import copy
import json
import unittest
from pathlib import Path

from tools.validate_catalog import release_asset, validate

CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "corvuscore.json"


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def reject(self, mutate):
        bad = copy.deepcopy(self.catalog)
        mutate(bad)
        with self.assertRaises(ValueError):
            validate(bad)

    def test_published_catalog(self):
        self.assertEqual(len(validate(self.catalog)), 6)

    def test_duplicate_core_and_abi(self):
        self.reject(lambda x: x["cores"].__setitem__(1, dict(x["cores"][0])))

    def test_missing_architecture(self):
        self.reject(lambda x: x["cores"].pop())

    def test_untrusted_domain(self):
        self.reject(lambda x: x["cores"][0].__setitem__(
            "archive_url", x["cores"][0]["archive_url"].replace("github.com", "example.org")))

    def test_untrusted_repository(self):
        self.reject(lambda x: x["cores"][0].__setitem__(
            "archive_url", x["cores"][0]["archive_url"].replace(
                release_asset(x["cores"][0]["archive_url"])[0], "CorvusSoftware/OtherRepo")))

    def test_official_archives_in_repository_and_legacy_releases(self):
        for repository in ("CorvusRetro", "CorvusRepository"):
            catalog = copy.deepcopy(self.catalog)
            for entry in catalog["cores"]:
                _, tag, filename = release_asset(entry["archive_url"])
                entry["archive_url"] = (
                    f"https://github.com/CorvusSoftware/{repository}/releases/download/{tag}/{filename}")
            with self.subTest(repository=repository):
                self.assertEqual(len(validate(catalog)), 6)

    def test_release_asset_origin_and_route(self):
        valid = "https://github.com/CorvusSoftware/CorvusRepository/releases/download/v0.15.0/core.zip"
        self.assertEqual(release_asset(valid),
                         ("CorvusSoftware/CorvusRepository", "v0.15.0", "core.zip"))
        for invalid in (
                valid.replace("https:", "http:"), valid + "?token=1", valid + "#fragment",
                valid.replace("github.com", "github.com.evil.test"),
                valid.replace("github.com", "user@github.com"),
                valid.replace("CorvusSoftware", "AnotherOwner"),
                valid.replace("CorvusRepository", "CorvusRepositoryExtra"),
                valid.replace("v0.15.0", "corvuscore-v0.15.0"),
                valid.replace("/core.zip", "/../core.zip"),
                valid.replace("/core.zip", "/%63ore.zip"),
                valid.replace("/core.zip", "/.hidden.zip"),
                valid.replace("/core.zip", "/core\\file.zip")):
            with self.subTest(address=invalid), self.assertRaises(ValueError):
                release_asset(invalid)

    def test_path_traversal(self):
        self.reject(lambda x: x["cores"][0].__setitem__(
            "archive_url", x["cores"][0]["archive_url"].replace("/releases/download/", "/releases/download/../")))

    def test_mismatched_filename(self):
        self.reject(lambda x: x["cores"][0].__setitem__(
            "archive_url", x["cores"][0]["archive_url"].replace("CorvusGB-", "CorvusGBA-")))

    def test_bad_hash(self):
        self.reject(lambda x: x["cores"][0].__setitem__("sha256", "0" * 63))

    def test_bad_size(self):
        self.reject(lambda x: x["cores"][0].__setitem__("size", 0))

    def test_bool_is_not_integer(self):
        self.reject(lambda x: x["cores"][0].__setitem__("api_version", False))

    def test_unknown_extra_field(self):
        self.reject(lambda x: x["cores"][0].__setitem__("unsigned", True))

    def test_additional_provider(self):
        base = dict(self.catalog["cores"][0])
        base.update(id="demo.handheld", name="Demo", library_name="libdemo_handheld.so",
                    archive_url="https://github.com/CorvusSoftware/CorvusRepository/releases/download/v0.1.0/demo-x86_64.zip")
        self.assertEqual(len(validate({"format": 3, "cores": [base]}, "demo.json")), 1)
        base["id"] = "corvus.gb"
        with self.assertRaises(ValueError):
            validate({"format": 3, "cores": [base]}, "demo.json")
        base["id"] = "demo.handheld"
        base["library_name"] = "../unsafe.so"
        with self.assertRaises(ValueError):
            validate({"format": 3, "cores": [base]}, "demo.json")

    def test_directory_discovers_json_without_manifest(self):
        import tempfile
        from tools.validate_catalog import validate_directory
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "corvuscore.json").write_text(json.dumps(self.catalog))
            (root / "demo.json").write_text(json.dumps({"format": 3, "cores": []}))
            self.assertEqual(validate_directory(root), (2, 6))
            (root / "not-a-catalog.json").write_text("{}")
            with self.assertRaises(ValueError):
                validate_directory(root)


if __name__ == "__main__":
    unittest.main()
