# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Offline regression tests for the catalog schema and trust boundary."""

import copy
import json
import unittest
from pathlib import Path

from tools.validate_catalog import validate

CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "cores-v3.json"


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
            "archive_url", x["cores"][0]["archive_url"].replace("CorvusRetro", "OtherRepo")))

    def test_path_traversal(self):
        self.reject(lambda x: x["cores"][0].__setitem__(
            "archive_url", x["cores"][0]["archive_url"].replace("/v0.13.0/", "/../")))

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


if __name__ == "__main__":
    unittest.main()
