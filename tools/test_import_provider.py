# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Offline regressions for the upstream-to-curated distribution boundary."""

import hashlib
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import import_provider as importer


class ImportProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "out"
        self.registry = {"id": "studio", "repository": "Studio/Engine",
                         "manifest_asset": "corvus-catalog.json", "provenance_asset": "source.json"}
        self.sha = "a" * 40
        self.provenance = {"format": 1, "provider": "studio", "repository": "Studio/Engine",
                           "source_sha": self.sha, "version": "1.2.3", "ci_run_id": 123}
        self.data = b"ZIP bytes inspected separately by validate_bundle"
        self.catalog = {"format": 3, "cores": [{
            "id": "studio.engine", "name": "Engine", "description": "Reviewed module",
            "version": "1.2.3", "abi": "arm64-v8a", "api_version": 0,
            "library_name": "libengine.so", "size": len(self.data),
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "archive_url": "https://github.com/Studio/Engine/releases/download/v1.2.3/Engine.zip"}]}
        self.distribution = types.SimpleNamespace(provider=Mock(return_value=self.registry),
                                                 check_source=Mock(), validate_bundle=Mock())
        self.payloads = {}
        self.release = {"tag_name": "v1.2.3", "draft": False, "assets": []}
        self.refresh()
        self.commands = []

    def refresh(self):
        self.payloads = {"corvus-catalog.json": json.dumps(self.catalog).encode(),
                         "source.json": json.dumps(self.provenance).encode(), "Engine.zip": self.data}
        self.release["assets"] = [{"name": name, "size": len(payload),
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "browser_download_url": "https://github.com/Studio/Engine/releases/download/v1.2.3/" + name}
            for name, payload in self.payloads.items()]

    def api(self, endpoint):
        if endpoint.endswith("/releases/tags/v1.2.3"):
            return self.release
        if endpoint.endswith("/git/ref/tags/v1.2.3"):
            return {"object": {"type": "commit", "sha": self.sha}}
        raise AssertionError("Unexpected API call: " + endpoint)

    def download(self, command, **kwargs):
        self.commands.append(command)
        self.assertEqual(command[:3], ["gh", "release", "download"])
        name = command[command.index("--pattern") + 1]
        destination = Path(command[command.index("--dir") + 1]) / name
        destination.write_bytes(self.payloads[name])
        return subprocess.CompletedProcess(command, 0, "", "")

    def run_import(self, **options):
        with patch.object(importer, "_distribution", return_value=self.distribution), \
                patch.object(importer, "gh_json", side_effect=self.api), \
                patch.object(importer.subprocess, "run", side_effect=self.download):
            return importer.import_bundle(options.get("name", "studio"),
                options.get("upstream_tag", "v1.2.3"), options.get("tag", "v9.0.0"), self.output)

    def test_rewrites_origin_and_only_stages_verified_bytes(self):
        catalog, provenance = self.run_import()
        self.assertEqual(catalog["cores"][0]["archive_url"],
            "https://github.com/CorvusSoftware/CorvusRepository/releases/download/v9.0.0/Engine.zip")
        self.assertEqual(provenance, dict(self.provenance, upstream_tag="v1.2.3"))
        self.assertEqual((self.output / "Engine.zip").read_bytes(), self.data)
        self.assertEqual(json.loads((self.output / "catalog.json").read_text()), catalog)
        self.distribution.check_source.assert_called_once_with(self.registry, self.provenance)
        self.distribution.validate_bundle.assert_called_once()
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(self.catalog["cores"][0]["archive_url"],
                         "https://github.com/Studio/Engine/releases/download/v1.2.3/Engine.zip")

    def test_foreign_redirect_encoded_path_or_wrong_tag_fail_before_archive_fetch(self):
        for address in (
            "https://github.com/Evil/Engine/releases/download/v1.2.3/Engine.zip",
            "https://github.com/Studio/Engine/releases/download/v1.2.4/Engine.zip",
            "https://github.com/Studio/Engine/releases/download/v1.2.3/../Engine.zip",
            "https://github.com/Studio/Engine/releases/download/v1.2.3/%45ngine.zip",
            "https://github.com/Studio/Engine/releases/download/v1.2.3/Engine.zip?x=1",
            "https://github.com/Studio/Engine/releases/download/v1.2.3/Engine.zip#x",
            "https://github.com@evil.test/Studio/Engine/releases/download/v1.2.3/Engine.zip",
        ):
            with self.subTest(address=address):
                self.catalog["cores"][0]["archive_url"] = address
                self.refresh()
                self.commands.clear()
                with self.assertRaises(ValueError):
                    self.run_import()
                self.assertEqual(len(self.commands), 2)
                self.assertFalse(self.output.exists())

    def test_source_tag_mismatch_stops_before_archive_fetch(self):
        self.provenance["source_sha"] = "b" * 40
        self.refresh()
        with self.assertRaisesRegex(ValueError, "source commit differ"):
            self.run_import()
        self.assertEqual(len(self.commands), 2)

    def test_failed_source_ci_stops_before_archive_fetch(self):
        self.distribution.check_source.side_effect = ValueError("CI failed")
        with self.assertRaisesRegex(ValueError, "CI failed"):
            self.run_import()
        self.assertEqual(len(self.commands), 2)

    def test_release_digest_must_match_catalog(self):
        self.catalog["cores"][0]["sha256"] = "0" * 64
        self.refresh()
        with self.assertRaisesRegex(ValueError, "metadata differ"):
            self.run_import()
        self.assertEqual(len(self.commands), 2)

    def test_download_digest_checked_against_real_bytes(self):
        self.payloads["Engine.zip"] = b"X" * len(self.data)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_bad_native_bundle_never_becomes_prepared_output(self):
        self.distribution.validate_bundle.side_effect = ValueError("ELF invalid")
        with self.assertRaisesRegex(ValueError, "ELF invalid"):
            self.run_import()
        self.assertFalse(self.output.exists())

    def test_oversized_metadata_or_archive_rejected_before_download(self):
        for asset_name in ("source.json", "Engine.zip"):
            with self.subTest(asset=asset_name):
                self.refresh()
                asset = next(a for a in self.release["assets"] if a["name"] == asset_name)
                asset["size"] = importer.MAX_ARCHIVE_SIZE + 1
                with self.assertRaisesRegex(ValueError, "metadata"):
                    self.run_import()
                self.assertFalse(self.output.exists())

    def test_unsafe_tags_and_official_import_are_rejected(self):
        for options in ({"tag": "v1.2.3;echo"}, {"upstream_tag": "../v1.2.3"},
                        {"name": "corvuscore"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_import(**options)
        self.assertEqual(self.commands, [])

    def test_nonempty_or_symlink_output_preserves_existing_data(self):
        self.output.mkdir()
        (self.output / "keep").write_text("untouched")
        with self.assertRaisesRegex(ValueError, "absent or empty"):
            self.run_import()
        self.assertEqual((self.output / "keep").read_text(), "untouched")
        self.assertEqual(self.commands, [])

    def test_public_metadata_requires_exact_origin_digest_and_unique_asset(self):
        for mutation in ("draft", "duplicate", "origin", "digest"):
            with self.subTest(mutation=mutation):
                self.refresh()
                self.release["draft"] = mutation == "draft"
                if mutation == "duplicate":
                    self.release["assets"].append(dict(self.release["assets"][0]))
                elif mutation == "origin":
                    self.release["assets"][0]["browser_download_url"] = "https://evil.test/catalog.json"
                elif mutation == "digest":
                    self.release["assets"][0]["digest"] = None
                with self.assertRaises(ValueError):
                    self.run_import()

    def test_annotated_tag_resolves_only_bounded_valid_commits(self):
        replies = [{"object": {"type": "tag", "sha": "b" * 40}},
                   {"object": {"type": "commit", "sha": self.sha}}]
        with patch.object(importer, "gh_json", side_effect=replies) as api:
            self.assertEqual(importer.source_commit("Studio/Engine", "v1.2.3"), self.sha)
            self.assertIn("/git/tags/", api.call_args.args[0])
        for item in ({"type": "tree", "sha": self.sha}, {"type": "commit", "sha": "bad"},
                     {"type": "tag", "sha": "b" * 40}):
            with self.subTest(item=item), patch.object(importer, "gh_json", return_value={"object": item}) as api:
                with self.assertRaises(ValueError):
                    importer.source_commit("Studio/Engine", "v1.2.3")
                self.assertLessEqual(api.call_count, 6)


if __name__ == "__main__":
    unittest.main()
