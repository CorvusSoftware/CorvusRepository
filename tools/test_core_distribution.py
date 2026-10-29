# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Regression checks for native validation and immutable publication ordering."""
import base64
import hashlib
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import core_distribution as dist


def module(machine=62, symbol=b'corvus_get_api', dependency=b'libc.so', alignment=16384):
    data = bytearray(640)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 3, machine)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<Q', data, 40, 384)
    struct.pack_into('<HH', data, 54, 56, 1)
    struct.pack_into('<HH', data, 58, 64, 4)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 0, 0, 0, len(data), len(data), alignment)
    strings = b'\0' + symbol + b'\0' + dependency + b'\0'
    data[128:128+len(strings)] = strings
    struct.pack_into('<IBBHQQ', data, 216, 1, 0x12, 0, 1, 256, 1)
    struct.pack_into('<qQ', data, 256, 1, len(symbol)+2)
    struct.pack_into('<IIQQQQIIQQ', data, 448, 0, 3, 0, 0, 128, len(strings), 0, 0, 1, 0)
    struct.pack_into('<IIQQQQIIQQ', data, 512, 0, 11, 0, 0, 192, 48, 1, 0, 8, 24)
    struct.pack_into('<IIQQQQIIQQ', data, 576, 0, 6, 0, 0, 256, 16, 1, 0, 8, 16)
    return bytes(data)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.entry = {'id': 'example.gb', 'name': 'ExampleGB', 'description': 'Game Boy',
                      'version': '1.0.0', 'abi': 'x86_64', 'api_version': 0,
                      'library_name': 'libexample.so', 'archive_url':
                      'https://github.com/CorvusSoftware/CorvusRepository/releases/download/v1.0.0/Example.zip'}
        self.path = self.directory / 'Example.zip'
        self.archive(module())
        self.source = {'format': 1, 'provider': 'example', 'repository': 'Example/Engine',
                       'source_sha': 'a'*40, 'version': '1.0.0', 'ci_run_id': 123}
        self.record = {'id': 'example', 'repository': 'Example/Engine', 'ci_workflow': 'ci.yml'}
        self.run = {'head_sha': 'a'*40, 'head_branch': 'main', 'event': 'push',
                    'status': 'completed', 'conclusion': 'success',
                    'path': '.github/workflows/ci.yml', 'head_repository': {'full_name': 'Example/Engine'}}

    def archive(self, data, name='libexample.so', mode=0o100444, extra=False):
        item = zipfile.ZipInfo(name)
        item.external_attr = mode << 16
        with zipfile.ZipFile(self.path, 'w') as archive:
            archive.writestr(item, data)
            if extra:
                archive.writestr('extra.so', data)
        self.entry['size'] = self.path.stat().st_size
        self.entry['sha256'] = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_valid_module_and_archive(self):
        dist.validate_archive(self.path, self.entry)
        self.assertEqual(dist.module_symbols(module()), {'corvus_get_api'})

    def test_wrong_abi_page_size_export_or_dependency(self):
        for data in (module(machine=183), module(alignment=4096), module(symbol=b'not_corvus_api'),
                     module(dependency=b'libc++_shared.so')):
            with self.subTest(data=data[16:20]):
                self.archive(data)
                with self.assertRaises(ValueError):
                    dist.validate_archive(self.path, self.entry)

    def test_zip_traversal_symlink_and_multiple_members(self):
        for name, mode, extra in (('../libexample.so', 0o100444, False),
                                  ('libexample.so', 0o120777, False),
                                  ('libexample.so', 0o100444, True)):
            self.archive(module(), name, mode, extra)
            with self.assertRaises(ValueError):
                dist.validate_archive(self.path, self.entry)

    def test_changed_checksum_size_and_local_symlink(self):
        original = self.entry.copy()
        self.entry['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            dist.validate_archive(self.path, self.entry)
        self.entry = original
        linked = self.directory / 'link.zip'
        linked.symlink_to(self.path)
        with self.assertRaises(ValueError):
            dist.validate_archive(linked, self.entry)
        self.entry['size'] += 1
        with self.assertRaises(ValueError):
            dist.validate_archive(self.path, self.entry)

    def test_malformed_elf_tables_rejected(self):
        for position in (32, 40):
            data = bytearray(module())
            struct.pack_into('<Q', data, position, 2**63)
            self.archive(data)
            with self.assertRaises(ValueError):
                dist.validate_archive(self.path, self.entry)

    def test_exact_source_ci_and_provenance(self):
        with patch.object(dist, 'api', side_effect=[self.run, {'default_branch': 'main'}]):
            dist.check_source(self.record, self.source)
        for key, value in [('head_sha', 'b'*40), ('event', 'pull_request'),
                           ('head_branch', 'branch'), ('conclusion', 'failure'),
                           ('status', 'in_progress'), ('path', '.github/workflows/other.yml'),
                           ('head_repository', {'full_name': 'Other/Engine'})]:
            run = dict(self.run, **{key: value})
            with self.subTest(key=key), patch.object(dist, 'api', side_effect=[run, {'default_branch': 'main'}]):
                with self.assertRaises(ValueError):
                    dist.check_source(self.record, self.source)
        for changes in ({'ci_run_id': True}, {'source_sha': 'a'*39}, {'repository': 'Other/Engine'},
                        {'unexpected': 'secret'}, {'toolchain': {'ndk': 'other'}}):
            with self.subTest(changes=changes), patch.object(dist, 'api') as api:
                with self.assertRaises(ValueError):
                    dist.check_source(self.record, dict(self.source, **changes))
                api.assert_not_called()

    def test_bundle_rejects_foreign_tag_and_duplicate_asset_before_publication(self):
        payload = {'format': 3, 'cores': [self.entry]}
        self.source['upstream_tag'] = 'v1.0.0'
        with patch.object(dist, 'provider', return_value=self.record), patch.object(dist, 'check_source'):
            dist.validate_bundle('example', 'v1.0.0', payload, self.source, self.directory)
            with self.assertRaises(ValueError):
                dist.validate_bundle('example', 'v1.0.1', payload, self.source, self.directory)
            self.entry['version'] = '1.0.1'
            with self.assertRaises(ValueError):
                dist.validate_bundle('example', 'v1.0.0', payload, self.source, self.directory)

    def test_immutable_release_asset_checks(self):
        item = {'name': self.path.name, 'size': self.path.stat().st_size,
                'digest': 'sha256:'+self.entry['sha256'], 'browser_download_url': self.entry['archive_url']}
        release = {'tag_name': 'v1.0.0', 'draft': False, 'assets': [item]}
        expected = {self.path.name: self.path}
        self.assertEqual(set(dist.asset_records(release, expected, 'v1.0.0')), {'Example.zip'})
        for changes in ({'digest': 'sha256:'+'0'*64}, {'name': 'unknown.zip'}, {'size': 1}):
            with self.assertRaises(ValueError):
                dist.asset_records(dict(release, assets=[dict(item, **changes)]), expected, 'v1.0.0')
        with self.assertRaises(ValueError):
            dist.asset_records(dict(release, draft=True), expected, 'v1.0.0')
        draft = dict(release, draft=True, assets=[dict(item, browser_download_url=
            'https://github.com/'+dist.REPOSITORY+'/releases/download/untagged-abc123/Example.zip')])
        self.assertEqual(set(dist.asset_records(draft, expected, 'v1.0.0', allow_draft=True)), {'Example.zip'})
        with self.assertRaises(ValueError):
            dist.asset_records(dict(draft, draft=False), expected, 'v1.0.0', allow_draft=True)
        for address in ('https://github.com/Other/Repository/releases/download/untagged-abc123/Example.zip',
                        'https://github.com/'+dist.REPOSITORY+'/releases/download/untagged-abc123/Other.zip'):
            with self.assertRaises(ValueError):
                dist.asset_records(dict(draft, assets=[dict(item, browser_download_url=address)]),
                                   expected, 'v1.0.0', allow_draft=True)

    def test_no_promotion_when_public_bytes_differ(self):
        release = {'id': 123, 'tag_name': 'v1.0.0', 'draft': False, 'assets': []}
        def fake_api(endpoint, **fields):
            return [release] if endpoint.endswith('per_page=100') else release
        def fake_gh(*args):
            if args[:2] == ('release', 'download'):
                directory = Path(args[args.index('--dir')+1])
                filename = args[args.index('--pattern')+1]
                (directory / filename).write_bytes(b'corrupt')
            return ''
        with patch.object(dist, 'validate_bundle', return_value=[self.entry]), \
             patch.object(dist, 'qualified_repository', return_value='a'*40), \
             patch.object(dist, 'api', side_effect=fake_api), \
             patch.object(dist, 'asset_records', side_effect=lambda r,e,t,**kw: dict(e)), \
             patch.object(dist, 'gh', side_effect=fake_gh), \
             patch.object(dist, 'promote_catalog') as promote:
            with self.assertRaisesRegex(ValueError, 'public bytes'):
                dist.publish('example', 'v1.0.0', self.directory, {'cores':[self.entry]}, self.source)
            promote.assert_not_called()

    def test_put_uses_http_method_not_json_method_field(self):
        with patch.object(dist, 'gh', return_value='{}') as gh:
            dist.api('repos/example/file', _method='PUT', content='YQ==')
        self.assertEqual(gh.call_args.args, ('api','repos/example/file','--method','PUT','-f','content=YQ=='))

    def test_new_draft_uses_supported_cli_api_url_and_promotes_after_downloads(self):
        release = {'id': 123, 'tag_name': 'v1.0.0', 'draft': True, 'assets': []}
        expected = {}
        events = []
        def fake_api(endpoint, **fields):
            return [] if endpoint.endswith('per_page=100') else release
        def fake_records(r, files, tag, **kwargs):
            expected.update(files)
            return {} if not events else dict(files)
        def fake_gh(*args):
            if args[:2] == ('release', 'view'):
                self.assertEqual(args[-1], 'apiUrl')
                return json.dumps({'apiUrl': 'https://api.github.com/repos/'+dist.REPOSITORY+'/releases/123'})
            if args[:2] == ('release', 'upload'):
                events.append('upload')
            if args[:2] == ('release', 'edit'):
                release['draft'] = False
            if args[:2] == ('release', 'download'):
                filename = args[args.index('--pattern')+1]
                target = Path(args[args.index('--dir')+1]) / filename
                target.write_bytes(expected[filename].read_bytes())
                events.append('download')
            return ''
        def fake_promote(*args):
            self.assertEqual(events.count('download'), 3)
            self.assertFalse(release['draft'])
            return {'catalog': 'prepared'}
        with patch.object(dist, 'validate_bundle', return_value=[self.entry]), \
             patch.object(dist, 'qualified_repository', return_value='a'*40), \
             patch.object(dist, 'api', side_effect=fake_api), \
             patch.object(dist, 'asset_records', side_effect=fake_records), \
             patch.object(dist, 'gh', side_effect=fake_gh), \
             patch.object(dist, 'promote_catalog', side_effect=fake_promote):
            dist.publish('example','v1.0.0',self.directory,{'cores':[self.entry]},self.source)

    def test_registry_rejects_unapproved_and_path_traversal(self):
        dist.provider('corvuscore')
        for name in ('../other', 'unknown', 'Example', 'corvuscore.json'):
            with self.assertRaises((OSError, ValueError)):
                dist.provider(name)


if __name__ == '__main__':
    unittest.main()
