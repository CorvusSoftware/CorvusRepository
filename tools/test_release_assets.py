# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Verify release metadata routing without downloading archives or using HTTP."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.check_release_assets import verify, verify_path
from tools.validate_catalog import release_asset

CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "corvuscore.json"


def release(entries, tag):
    return {"tag_name": tag, "draft": False, "assets": [
        {"name": release_asset(entry["archive_url"])[2],
         "browser_download_url": entry["archive_url"], "size": entry["size"],
         "digest": "sha256:" + entry["sha256"]} for entry in entries]}


class ReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.tag = "v1.2.3"
        for entry in self.catalog["cores"]:
            _, _, filename = release_asset(entry["archive_url"])
            entry["archive_url"] = (
                f"https://github.com/CorvusSoftware/CorvusRepository/releases/download/{self.tag}/{filename}")

    def mock_releases(self, releases):
        def response(request, timeout):
            self.assertEqual(timeout, 20)
            return io.BytesIO(json.dumps(releases[request.full_url]).encode("utf-8"))
        return patch("tools.check_release_assets.urlopen", side_effect=response)

    def api(self, repository):
        return f"https://api.github.com/repos/CorvusSoftware/{repository}/releases/tags/{self.tag}"

    def additional_provider(self):
        entry = copy.deepcopy(self.catalog["cores"][0])
        entry.update(id="example.handheld", name="Example", library_name="libexample_handheld.so",
                     archive_url=("https://github.com/CorvusSoftware/CorvusRepository/releases/download/"
                                  + self.tag + "/example-handheld.zip"))
        return {"format": 3, "cores": [entry]}

    def test_independent_official_release_fetched_once(self):
        metadata = release(self.catalog["cores"], self.tag)
        with self.mock_releases({self.api("CorvusRepository"): metadata}) as fetch:
            self.assertEqual(verify(self.catalog), 6)
            self.assertEqual(fetch.call_count, 1)

    def test_same_tag_in_two_repositories_has_separate_cache_entries(self):
        first, second = self.catalog["cores"][:3], self.catalog["cores"][3:]
        for entry in second:
            entry["archive_url"] = entry["archive_url"].replace("CorvusRepository", "CorvusRetro")
        responses = {self.api("CorvusRepository"): release(first, self.tag),
                     self.api("CorvusRetro"): release(second, self.tag)}
        with self.mock_releases(responses) as fetch:
            self.assertEqual(verify(self.catalog), 6)
            self.assertEqual(fetch.call_count, 2)

    def test_provider_catalog_file_and_directory(self):
        other = self.additional_provider()
        metadata = release(self.catalog["cores"] + other["cores"], self.tag)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "corvuscore.json").write_text(json.dumps(self.catalog))
            (root / "example.json").write_text(json.dumps(other))
            with self.mock_releases({self.api("CorvusRepository"): metadata}) as fetch:
                self.assertEqual(verify_path(root / "example.json"), 1)
                self.assertEqual(fetch.call_count, 1)
            with self.mock_releases({self.api("CorvusRepository"): metadata}) as fetch:
                self.assertEqual(verify_path(root), 7)
                self.assertEqual(fetch.call_count, 1)

    def test_invalid_later_catalog_rejected_before_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "corvuscore.json").write_text(json.dumps(self.catalog))
            other = self.additional_provider()
            other["cores"][0]["api_version"] = True
            (root / "example.json").write_text(json.dumps(other))
            with patch("tools.check_release_assets.urlopen") as fetch:
                with self.assertRaises(ValueError):
                    verify_path(root)
                fetch.assert_not_called()

    def test_duplicate_core_across_catalogs_rejected_before_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "corvuscore.json").write_text(json.dumps(self.catalog))
            (root / "corvus.json").write_text(json.dumps({
                "format": 3, "cores": [self.catalog["cores"][0]]}))
            with patch("tools.check_release_assets.urlopen") as fetch:
                with self.assertRaisesRegex(ValueError, "duplicate core across"):
                    verify_path(root)
                fetch.assert_not_called()

    def test_mismatched_asset_records_fail(self):
        metadata = release(self.catalog["cores"], self.tag)
        for field, value in (("size", 1), ("digest", "sha256:" + "0" * 64),
                             ("browser_download_url", "https://example.test/core.zip")):
            bad = copy.deepcopy(metadata)
            bad["assets"][0][field] = value
            with self.subTest(field=field), self.mock_releases({self.api("CorvusRepository"): bad}):
                with self.assertRaises(ValueError):
                    verify(self.catalog)
        metadata["assets"].pop(0)
        with self.mock_releases({self.api("CorvusRepository"): metadata}):
            with self.assertRaises(ValueError):
                verify(self.catalog)

    def test_wrong_tag_draft_and_malformed_metadata_fail(self):
        metadata = release(self.catalog["cores"], self.tag)
        for bad in ([], dict(metadata, tag_name="v9.9.9"), dict(metadata, draft=True),
                    dict(metadata, assets=None), dict(metadata, assets=[None])):
            with self.subTest(metadata=bad), self.mock_releases({self.api("CorvusRepository"): bad}):
                with self.assertRaises(ValueError):
                    verify(self.catalog)


if __name__ == "__main__":
    unittest.main()
