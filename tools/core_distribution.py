#!/usr/bin/env python3
# CorvusRepository - CorvusSoftware
# Copyright (c) 2026 CorvusSoftware
# SPDX-License-Identifier: MIT
"""Publish qualified native cores independently of the Android application."""

import argparse
import base64
import hashlib
import json
import re
import stat
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

from tools.build_corvuscore import elf_layout
from tools.validate_catalog import (MAX_ARCHIVE_SIZE, MAX_CATALOG_SIZE,
                                    release_asset, validate, validate_directory)

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "CorvusSoftware/CorvusRepository"
TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
SHA = re.compile(r"[a-f0-9]{40}")
PROVIDER = re.compile(r"[a-z][a-z0-9_-]{0,39}")
FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}")
SYSTEM_LIBRARIES = {"libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so"}


def gh(*args):
    return subprocess.check_output(["gh", *map(str, args)], text=True).strip()


def api(endpoint, **fields):
    args = ["api", endpoint]
    method = fields.pop("_method", None)
    if method:
        args += ["--method", method]
    for key, value in fields.items():
        args += ["-f", key + "=" + value]
    return json.loads(gh(*args))


def read_json(path, limit=MAX_CATALOG_SIZE):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("invalid or oversized JSON file: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def provider(name):
    if not isinstance(name, str) or not PROVIDER.fullmatch(name):
        raise ValueError("invalid provider identifier")
    record = read_json(ROOT / "providers" / (name + ".json"))
    fields = {"format", "id", "name", "repository", "license", "ci_workflow",
              "manifest_asset", "provenance_asset"}
    if (not isinstance(record, dict) or set(record) != fields
            or type(record["format"]) is not int or record["format"] != 1
            or record["id"] != name):
        raise ValueError("invalid approved provider declaration")
    for key in fields - {"format"}:
        if not isinstance(record[key], str) or not 1 <= len(record[key]) <= 128:
            raise ValueError("invalid provider field: " + key)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", record["repository"]):
        raise ValueError("invalid approved repository")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", record["license"]):
        raise ValueError("expected an SPDX license identifier")
    for key in ("ci_workflow", "manifest_asset", "provenance_asset"):
        if not FILENAME.fullmatch(record[key]):
            raise ValueError("unsafe provider asset/workflow filename")
    if not record["ci_workflow"].endswith((".yml", ".yaml")):
        raise ValueError("expected a CI workflow filename")
    if record["manifest_asset"] == record["provenance_asset"]:
        raise ValueError("manifest and provenance must be distinct")
    return record


def check_source(record, source):
    required = {"format", "provider", "repository", "source_sha", "version", "ci_run_id"}
    optional = {"corvusapi_sha", "repository_sha", "distribution_run_id", "api_version", "toolchain", "upstream_tag"}
    if (not isinstance(source, dict) or not required <= source.keys()
            or source.keys() - required - optional
            or type(source["format"]) is not int or source["format"] != 1
            or source["provider"] != record["id"] or source["repository"] != record["repository"]
            or not isinstance(source["source_sha"], str) or not SHA.fullmatch(source["source_sha"])
            or not isinstance(source["version"], str) or not TAG.fullmatch("v" + source["version"])
            or type(source["ci_run_id"]) is not int or source["ci_run_id"] <= 0):
        raise ValueError("invalid source provenance")
    for key in ("corvusapi_sha", "repository_sha"):
        if key in source and (not isinstance(source[key], str) or not SHA.fullmatch(source[key])):
            raise ValueError("invalid provenance revision")
    if "distribution_run_id" in source and (type(source["distribution_run_id"]) is not int or source["distribution_run_id"] <= 0):
        raise ValueError("invalid distribution run")
    if "api_version" in source and (type(source["api_version"]) is not int or source["api_version"] != 0):
        raise ValueError("invalid API provenance")
    if "toolchain" in source:
        expected = {"ndk": "27.2.12479018", "cmake": "3.22.1", "platform": 26,
                    "stl": "c++_static", "build_type": "Release"}
        if source["toolchain"] != expected:
            raise ValueError("unknown toolchain provenance")
    repository = record["repository"]
    run = api(f"repos/{repository}/actions/runs/{source['ci_run_id']}")
    default = api(f"repos/{repository}")["default_branch"]
    if (run.get("head_sha") != source["source_sha"] or run.get("head_branch") != default
            or run.get("event") != "push" or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or run.get("path", "").split("@", 1)[0] != ".github/workflows/" + record["ci_workflow"]
            or run.get("head_repository", {}).get("full_name") != repository):
        raise ValueError("source does not have successful exact-revision default-branch CI")
    if record["id"] == "corvuscore":
        from tools.build_corvuscore import project_version
        commit = source["source_sha"]
        cmake = api(f"repos/{repository}/contents/CMakeLists.txt?ref={commit}")
        if project_version(base64.b64decode(cmake["content"]).decode()) != source["version"]:
            raise ValueError("official version differs from the qualified source")
        pin = api(f"repos/{repository}/contents/third_party/CorvusAPI?ref={commit}")
        if source.get("corvusapi_sha") != pin["sha"]:
            raise ValueError("official API pin differs from the qualified source")
    if "upstream_tag" in source:
        from tools.import_provider import source_commit
        tag = source["upstream_tag"]
        if not isinstance(tag, str) or not TAG.fullmatch(tag) or source_commit(repository, tag) != source["source_sha"]:
            raise ValueError("upstream release tag differs from the qualified source")


def module_symbols(data):
    """Read defined dynamic functions and dependencies without loading native code."""
    offset = struct.unpack_from("<Q", data, 40)[0]
    stride, count = struct.unpack_from("<HH", data, 58)
    if stride < 64 or not 0 < count <= 4096 or offset + stride * count > len(data):
        raise ValueError("invalid ELF section table")
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, offset + i * stride) for i in range(count)]

    def content(section):
        start, size = section[4:6]
        if start + size > len(data):
            raise ValueError("invalid ELF section bounds")
        return data[start:start + size]

    def string(strings, index):
        end = strings.find(b"\0", index)
        if index >= len(strings) or end < 0:
            raise ValueError("invalid ELF string")
        return strings[index:end].decode("ascii")

    exports, dependencies = set(), set()
    for section in sections:
        if section[1] not in (6, 11):
            continue
        link = section[6]
        if link >= count or sections[link][1] != 3:
            raise ValueError("invalid ELF linked string table")
        strings, table = content(sections[link]), content(section)
        entry_size = 24 if section[1] == 11 else 16
        if section[9] != entry_size or len(table) % entry_size:
            raise ValueError("invalid ELF dynamic table")
        for pos in range(0, len(table), entry_size):
            if section[1] == 11:
                name, info, visibility, index, _, _ = struct.unpack_from("<IBBHQQ", table, pos)
                if index and info >> 4 in (1, 2) and info & 15 == 2 and visibility & 3 in (0, 3):
                    exports.add(string(strings, name))
            else:
                kind, value = struct.unpack_from("<qQ", table, pos)
                if kind == 1:
                    dependencies.add(string(strings, value))
    if "corvus_get_api" not in exports or not dependencies <= SYSTEM_LIBRARIES:
        raise ValueError("missing CorvusAPI entrypoint or unshipped runtime dependency")
    return exports


def validate_archive(path, entry):
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or path.stat().st_size != entry["size"]
            or not 0 < path.stat().st_size <= MAX_ARCHIVE_SIZE):
        raise ValueError("invalid archive size or local file")
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError("archive checksum mismatch")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != 1:
            raise ValueError("archive must contain exactly one native module")
        item = members[0]
        mode = item.external_attr >> 16
        if (item.filename != entry["library_name"] or item.flag_bits & 1
                or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                or not 0 < item.file_size <= 64 * 1024 * 1024
                or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
            raise ValueError("unsafe archive member")
        data = archive.read(item)
    elf_layout(data, entry["abi"])
    exports = module_symbols(data)
    if entry["id"].startswith("corvus.") and not {
        "corvus_get_options_api", "corvus_get_subsystem_api", "corvus_get_achievements_api"
    } <= exports:
        raise ValueError("official core lacks required optional interfaces")


def validate_bundle(name, tag, catalog, provenance, directory):
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise ValueError("expected an immutable vX.Y.Z distribution tag")
    record = provider(name)
    entries = validate(catalog, name + ".json")
    if not entries:
        raise ValueError("cannot publish an empty native distribution")
    check_source(record, provenance)
    if name != "corvuscore" and "upstream_tag" not in provenance:
        raise ValueError("community distribution must retain its upstream tag")
    filenames = set()
    for entry in entries:
        repo, version, filename = release_asset(entry["archive_url"])
        if repo != REPOSITORY or version != tag or entry["version"] != provenance["version"] or filename in filenames:
            raise ValueError("distribution origin, version or asset collision")
        filenames.add(filename)
        validate_archive(Path(directory) / filename, entry)
    return entries


def qualified_repository():
    if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"], text=True):
        raise ValueError("distribution tooling checkout must be clean")
    revision = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    payload = api(f"repos/{REPOSITORY}/actions/workflows/validate.yml/runs?head_sha={revision}&event=push&status=completed&per_page=100")
    if not any(run.get("head_sha") == revision and run.get("head_branch") == "main"
               and run.get("event") == "push" and run.get("status") == "completed"
               and run.get("conclusion") == "success"
               and run.get("head_repository", {}).get("full_name") == REPOSITORY
               and run.get("path", "").split("@", 1)[0] == ".github/workflows/validate.yml"
               for run in payload.get("workflow_runs", [])):
        raise ValueError("distribution tooling requires successful exact-revision main CI")
    return revision


def asset_records(release, expected, tag, allow_draft=False):
    if (release.get("tag_name") != tag or (release.get("draft") is not False and not allow_draft)
            or not isinstance(release.get("assets"), list)):
        raise ValueError("invalid release identity")
    found = {}
    for item in release["assets"]:
        name = item.get("name")
        if name not in expected or name in found:
            raise ValueError("existing release has unexpected or duplicate assets")
        path = expected[name]
        address = item.get("browser_download_url")
        published_address = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
        # GitHub gives unpublished assets a temporary untagged-* path until
        # the draft is published. The final public URL remains strict.
        draft_address = (allow_draft and release.get("draft") is True
                         and isinstance(address, str) and re.fullmatch(
                             re.escape(f"https://github.com/{REPOSITORY}/releases/download/")
                             + r"untagged-[a-f0-9]+/" + re.escape(name), address))
        if (item.get("size") != path.stat().st_size
                or item.get("digest") != "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                or (address != published_address and not draft_address)):
            raise ValueError("immutable release asset differs: " + name)
        found[name] = item
    return found


def promote_catalog(name, tag, catalog):
    """Prepare a review branch against live main. Never write the public branch."""
    base = api(f"repos/{REPOSITORY}/git/ref/heads/main")["object"]["sha"]
    current = api(f"repos/{REPOSITORY}/contents/catalog?ref={base}")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for item in current:
            if item["name"].endswith(".json"):
                blob = api(f"repos/{REPOSITORY}/contents/catalog/{item['name']}?ref={base}")
                (directory / item["name"]).write_bytes(base64.b64decode(blob["content"]))
        (directory / (name + ".json")).write_text(json.dumps(catalog, indent=2) + "\n")
        validate_directory(directory)
    body = json.dumps(catalog, indent=2) + "\n"
    # Re-running an already-promoted lot needs no new branch or pull request.
    live = next((item for item in current if item["name"] == name + ".json"), None)
    if live:
        blob = api(f"repos/{REPOSITORY}/contents/catalog/{name}.json?ref={base}")
        if json.loads(base64.b64decode(blob["content"])) == catalog:
            return {"catalog": "already promoted"}
    branch = f"catalog/{name}-{tag}"
    refs = api(f"repos/{REPOSITORY}/git/matching-refs/heads/{branch}")
    exact = next((item for item in refs if item["ref"] == "refs/heads/" + branch), None)
    if exact:
        blob = api(f"repos/{REPOSITORY}/contents/catalog/{name}.json?ref={branch}")
        if base64.b64decode(blob["content"]).decode() != body:
            raise ValueError("existing catalog branch differs; refusing to overwrite")
    else:
        api(f"repos/{REPOSITORY}/git/refs", ref="refs/heads/" + branch, sha=base)
        fields = {"message": f"Publish verified {name} distribution {tag}", "branch": branch,
                  "content": base64.b64encode(body.encode()).decode()}
        if live:
            fields["sha"] = live["sha"]
        api(f"repos/{REPOSITORY}/contents/catalog/{name}.json", **fields, _method="PUT")
    # GITHUB_TOKEN-created pushes do not trigger CI automatically.
    gh("workflow", "run", "validate.yml", "--repo", REPOSITORY, "--ref", branch)
    prs = api(f"repos/{REPOSITORY}/pulls?head=CorvusSoftware:{branch}&base=main&state=open")
    if prs:
        link = prs[0]["html_url"]
    else:
        try:
            link = gh("pr", "create", "--repo", REPOSITORY, "--base", "main", "--head", branch,
                      "--title", f"Publish verified {name} cores ({tag})", "--body",
                      f"Publish the verified native distribution from https://github.com/{REPOSITORY}/releases/tag/{tag}.\n\nThe archives, source CI, architecture, checksums and public bytes were checked before catalog promotion.")
        except subprocess.CalledProcessError:
            link = f"https://github.com/{REPOSITORY}/compare/main...{branch}?expand=1"
            print("Pull request creation unavailable; review the prepared branch: " + link)
    return {"branch": branch, "review_url": link}


def publish(name, tag, directory, catalog, provenance):
    entries = validate_bundle(name, tag, catalog, provenance, directory)
    revision = qualified_repository()
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        expected = {release_asset(e["archive_url"])[2]: Path(directory) / release_asset(e["archive_url"])[2] for e in entries}
        source = staging / "source.json"
        source.write_text(json.dumps(provenance, indent=2) + "\n")
        expected[source.name] = source
        sums = staging / "SHA256SUMS"
        sums.write_text("".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + filename + "\n"
                                for filename, path in sorted(expected.items())))
        expected[sums.name] = sums
        releases = api(f"repos/{REPOSITORY}/releases?per_page=100")
        existing = next((r for r in releases if r["tag_name"] == tag), None)
        if existing is None:
            gh("release", "create", tag, "--repo", REPOSITORY, "--target", revision, "--draft",
               "--title", f"Native core distribution {tag}", "--notes",
               f"Independent {name} distribution. Source: {provenance['repository']}@{provenance['source_sha']}. Core version: {provenance['version']}. See source.json and SHA256SUMS.")
            detail = json.loads(gh("release", "view", tag, "--repo", REPOSITORY, "--json", "apiUrl"))
            expected_api = f"https://api.github.com/repos/{REPOSITORY}/releases/"
            if not isinstance(detail.get("apiUrl"), str) or not re.fullmatch(re.escape(expected_api) + r"[0-9]+", detail["apiUrl"]):
                raise ValueError("unexpected draft release API address")
            existing = api(detail["apiUrl"])
        found = asset_records(existing, expected, tag, allow_draft=True)
        missing = [path for filename, path in expected.items() if filename not in found]
        if missing:
            if not existing["draft"]:
                raise ValueError("public release is incomplete; refusing to alter it")
            gh("release", "upload", tag, "--repo", REPOSITORY, *missing)
        release = api(f"repos/{REPOSITORY}/releases/{existing['id']}")
        if set(asset_records(release, expected, tag, allow_draft=True)) != set(expected):
            raise ValueError("release upload is incomplete")
        if release["draft"]:
            gh("release", "edit", tag, "--repo", REPOSITORY, "--draft=false", "--latest=false")
        release = api(f"repos/{REPOSITORY}/releases/tags/{tag}")
        if set(asset_records(release, expected, tag)) != set(expected):
            raise ValueError("public release does not match the qualified bundle")
        public = staging / "public"
        public.mkdir()
        for filename, path in expected.items():
            gh("release", "download", tag, "--repo", REPOSITORY, "--pattern", filename, "--dir", public)
            if (public / filename).read_bytes() != path.read_bytes():
                raise ValueError("public bytes differ from the qualified bundle")
    result = {"release_url": f"https://github.com/{REPOSITORY}/releases/tag/{tag}"}
    result.update(promote_catalog(name, tag, catalog))
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    publish_parser = commands.add_parser("publish")
    for option in ("provider", "tag", "input-dir", "catalog", "provenance"):
        publish_parser.add_argument("--" + option, required=True)
    import_parser = commands.add_parser("import")
    for option in ("provider", "upstream-tag", "tag", "output-dir"):
        import_parser.add_argument("--" + option, required=True)
    import_parser.add_argument("--dry-run", action="store_true")
    commands.add_parser("validate-providers")
    args = parser.parse_args()
    if args.command == "validate-providers":
        for path in sorted((ROOT / "providers").glob("*.json")):
            provider(path.stem)
        print("PASS approved provider declarations")
    elif args.command == "publish":
        publish(args.provider, args.tag, Path(args.input_dir), read_json(args.catalog), read_json(args.provenance))
    else:
        from tools.import_provider import import_bundle
        output = Path(args.output_dir)
        import_bundle(args.provider, args.upstream_tag, args.tag, output)
        if not args.dry_run:
            publish(args.provider, args.tag, output, read_json(output / "catalog.json"), read_json(output / "source.json"))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, UnicodeError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        raise SystemExit("Core distribution failed: " + str(error))
