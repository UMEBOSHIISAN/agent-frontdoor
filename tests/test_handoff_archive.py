from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

try:
    verifier = importlib.import_module("verify_handoff_archive")
except ModuleNotFoundError:
    verifier = None


SOURCE_ROOT = "agent-frontdoor-0.1.0"
PACK_ROOT = "agent-frontdoor-friend-pack-0.1.0"
PUBLIC_REVISION = "1" * 40


@dataclass(frozen=True)
class FixtureRecord:
    path: str
    mode: int
    size: int
    sha256: str


@dataclass(frozen=True)
class TarEntry:
    name: str
    data: bytes = b""
    mode: int = 0o644
    kind: str = "file"
    linkname: str = ""


def _api():
    assert verifier is not None, "missing standalone verifier module"
    return verifier


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def tar_bytes(entries: list[TarEntry]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for entry in entries:
            info = tarfile.TarInfo(entry.name)
            info.mode = entry.mode
            if entry.kind == "file":
                info.size = len(entry.data)
                archive.addfile(info, io.BytesIO(entry.data))
            elif entry.kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            elif entry.kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = entry.linkname
                archive.addfile(info)
            elif entry.kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = entry.linkname
                archive.addfile(info)
            elif entry.kind == "fifo":
                info.type = tarfile.FIFOTYPE
                archive.addfile(info)
            elif entry.kind == "device":
                info.type = tarfile.CHRTYPE
                archive.addfile(info)
            else:  # pragma: no cover - fixture construction guard
                raise AssertionError(f"unknown entry kind: {entry.kind}")
    return stream.getvalue()


def source_entries() -> list[TarEntry]:
    return [
        TarEntry(f"{SOURCE_ROOT}/CHANGELOG.md", b"# Changelog\n"),
        TarEntry(
            f"{SOURCE_ROOT}/LICENSE",
            b"Copyright (c) 2026 Example Project\n",
        ),
        TarEntry(f"{SOURCE_ROOT}/README.md", b"# Agent Frontdoor\n"),
        TarEntry(
            f"{SOURCE_ROOT}/pyproject.toml",
            b"[project]\nname = 'agent-frontdoor'\nversion = '0.1.0'\n",
        ),
        TarEntry(
            f"{SOURCE_ROOT}/src/frontdoor/__init__.py",
            b"__version__ = '0.1.0'\n",
        ),
        TarEntry(
            f"{SOURCE_ROOT}/src/frontdoor/schema/intake.v0.json",
            b"{}\n",
        ),
        TarEntry(
            f"{SOURCE_ROOT}/tests/test_cli.py",
            b"def test_placeholder():\n    assert True\n",
        ),
        TarEntry(
            f"{SOURCE_ROOT}/tools/verify_handoff_archive.py",
            b"# standalone verifier\n",
            mode=0o755,
        ),
    ]


def records_for(entries: list[TarEntry]) -> list[FixtureRecord]:
    prefix = f"{SOURCE_ROOT}/"
    records = []
    for entry in entries:
        if entry.kind != "file" or not entry.name.startswith(prefix):
            continue
        records.append(
            FixtureRecord(
                path=entry.name[len(prefix) :],
                mode=entry.mode,
                size=len(entry.data),
                sha256=sha256(entry.data),
            )
        )
    return sorted(records, key=lambda item: item.path)


def expected_records(records: list[FixtureRecord]):
    api = _api()
    return tuple(
        api.MemberRecord(
            path=item.path,
            mode=item.mode,
            size=item.size,
            sha256=item.sha256,
        )
        for item in records
    )


def verify_source(
    data: bytes,
    records: list[FixtureRecord],
    *,
    expected_hash: str | None = None,
    expected_count: int | None = None,
):
    api = _api()
    return api.verify_source_archive_bytes(
        data,
        expected_sha256=expected_hash or sha256(data),
        expected_regular_file_count=(
            len(records) if expected_count is None else expected_count
        ),
        expected_members=expected_records(records),
    )


def source_manifest(records: list[FixtureRecord]) -> dict[str, object]:
    return {
        "schema_version": "source-archive-manifest.v1",
        "package_version": "0.1.0",
        "public_revision": PUBLIC_REVISION,
        "archive_root": SOURCE_ROOT,
        "regular_file_count": len(records),
        "members": [item.__dict__ for item in records],
    }


def _outer_record(path: str, data: bytes, mode: int = 0o644) -> dict[str, object]:
    return {
        "path": path,
        "mode": mode,
        "size": len(data),
        "sha256": sha256(data),
    }


def make_friend_pack(
    tmp_path: Path,
    *,
    source_data: bytes | None = None,
    source_records: list[FixtureRecord] | None = None,
    detached_bytes: bytes | None = None,
    inpack_verifier_bytes: bytes | None = None,
    malformed_manifest: bool = False,
    bad_manifest_checksum: bool = False,
    bad_privacy_control_hash: bool = False,
    missing_payload: str | None = None,
    extra_payload: bool = False,
) -> SimpleNamespace:
    entries = source_entries()
    records = source_records or records_for(entries)
    nested = source_data or tar_bytes(entries)
    verifier_bytes = inpack_verifier_bytes or b"#!/usr/bin/env python3\n"
    detached = detached_bytes if detached_bytes is not None else verifier_bytes
    privacy_control = (
        (b"/" + b"Users" + b"/synthetic/private\n")
        + (b"user" + b"name=synthetic-user\n")
        + (b"10" + b".0.0.9\n")
        + (b"api_" + b"key=sk-" + b"syntheticvalue\n")
        + (b"OPENAI_" + b"API_KEY=syntheticvalue\n")
        + (b"tasks/" + b"worker_registry/synthetic\n")
    )
    source_manifest_bytes = json_bytes(source_manifest(records))
    payload: dict[str, tuple[bytes, int]] = {
        "FRIEND_LAB.md": (b"# Friend Lab\n", 0o644),
        "source/agent-frontdoor-0.1.0.tar.gz": (nested, 0o644),
        "source/source-manifest.json": (source_manifest_bytes, 0o644),
        "verifier/verify_handoff_archive.py": (verifier_bytes, 0o755),
        "lab/controls/privacy_control.txt": (privacy_control, 0o644),
    }
    manifest_members = [
        _outer_record(path, data, mode)
        for path, (data, mode) in sorted(payload.items())
    ]
    manifest: dict[str, object] = {
        "schema_version": "friend-pack-manifest.v1",
        "package_version": "0.1.0",
        "public_revision": PUBLIC_REVISION,
        "source_archive": {
            "path": "source/agent-frontdoor-0.1.0.tar.gz",
            "sha256": sha256(nested),
            "regular_file_count": len(records),
            "manifest_path": "source/source-manifest.json",
        },
        "verifier": {
            "path": "verifier/verify_handoff_archive.py",
            "sha256": sha256(verifier_bytes),
        },
        "privacy_control": {
            "path": "lab/controls/privacy_control.txt",
            "sha256": (
                "0" * 64
                if bad_privacy_control_hash
                else sha256(privacy_control)
            ),
        },
        "self_exclusions": ["manifest.json", "manifest.sha256"],
        "members": manifest_members,
    }
    manifest_bytes = b"{" if malformed_manifest else json_bytes(manifest)
    checksum = sha256(manifest_bytes)
    checksum_bytes = (
        ("f" * 64 if bad_manifest_checksum else checksum) + "\n"
    ).encode("ascii")

    emitted = dict(payload)
    if missing_payload is not None:
        emitted.pop(missing_payload)
    if extra_payload:
        emitted["unexpected.txt"] = (b"unexpected\n", 0o644)
    emitted["manifest.json"] = (manifest_bytes, 0o644)
    emitted["manifest.sha256"] = (checksum_bytes, 0o644)
    outer_entries = [
        TarEntry(f"{PACK_ROOT}/{path}", data, mode)
        for path, (data, mode) in sorted(emitted.items())
    ]
    pack_data = tar_bytes(outer_entries)
    pack_path = tmp_path / "friend-pack.tar.gz"
    pack_path.write_bytes(pack_data)
    detached_path = tmp_path / "verify_handoff_archive.py"
    detached_path.write_bytes(detached)
    return SimpleNamespace(
        pack_path=pack_path,
        pack_bytes=pack_data,
        detached_path=detached_path,
        pack_sha256=sha256(pack_data),
        source_sha256=sha256(nested),
        verifier_sha256=sha256(verifier_bytes),
        verifier_bytes=verifier_bytes,
    )


def verify_pack(fixture: SimpleNamespace, **overrides):
    api = _api()
    return api.verify_friend_pack(
        fixture.pack_path,
        detached_verifier_path=fixture.detached_path,
        expected_pack_sha256=overrides.get(
            "expected_pack_sha256", fixture.pack_sha256
        ),
        expected_source_sha256=overrides.get(
            "expected_source_sha256", fixture.source_sha256
        ),
        expected_verifier_sha256=overrides.get(
            "expected_verifier_sha256", fixture.verifier_sha256
        ),
    )


def test_source_archive_accepts_exact_safe_members() -> None:
    entries = source_entries()
    records = records_for(entries)
    data = tar_bytes(entries)

    result = verify_source(data, records)

    assert result.ok is True
    assert result.artifact_kind == "source"
    assert result.sha256 == sha256(data)
    assert result.regular_file_count == len(records)
    assert result.root_name == SOURCE_ROOT
    assert result.errors == ()


@pytest.mark.parametrize(
    "entry",
    [
        TarEntry("../escape", b"x"),
        TarEntry(f"{SOURCE_ROOT}/../escape", b"x"),
        TarEntry("/absolute.txt", b"x"),
    ],
)
def test_source_archive_rejects_unsafe_path(entry: TarEntry) -> None:
    entries = source_entries() + [entry]
    result = verify_source(tar_bytes(entries), records_for(entries))

    assert result.ok is False
    assert any("unsafe archive member" in item for item in result.errors)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "device"])
def test_source_archive_rejects_non_regular_member(kind: str) -> None:
    entries = source_entries() + [
        TarEntry(
            f"{SOURCE_ROOT}/unsafe-node",
            kind=kind,
            linkname=f"{SOURCE_ROOT}/README.md",
        )
    ]
    result = verify_source(tar_bytes(entries), records_for(entries))

    assert result.ok is False
    assert any("forbidden member type" in item for item in result.errors)


def test_source_archive_rejects_truncated_tar() -> None:
    entries = source_entries()
    data = tar_bytes(entries)
    truncated = data[: max(1, len(data) // 3)]

    result = verify_source(truncated, records_for(entries), expected_hash=sha256(truncated))

    assert result.ok is False
    assert any("archive unreadable" in item for item in result.errors)


def test_source_archive_rejects_multiple_roots() -> None:
    entries = source_entries() + [TarEntry("second-root/file.txt", b"x")]
    result = verify_source(tar_bytes(entries), records_for(entries))

    assert result.ok is False
    assert any("single archive root required" in item for item in result.errors)


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        ".venv/bin/python",
        "__pycache__/cached.pyc",
        ".env",
        "logs/private.log",
    ],
)
def test_source_archive_rejects_forbidden_directory(path: str) -> None:
    entries = source_entries() + [TarEntry(f"{SOURCE_ROOT}/{path}", b"x")]
    result = verify_source(tar_bytes(entries), records_for(entries))

    assert result.ok is False
    assert any("forbidden archive path" in item for item in result.errors)


@pytest.mark.parametrize(
    ("data", "category"),
    [
        (b"path=/" + b"Users" + b"/private/example\n", "absolute-user-path"),
        (b"user" + b"name=private-person\n", "user-or-host-identifier"),
        (b"address=10" + b".9.8.7\n", "ip-address"),
        (b"api_" + b"key=sk-" + b"secretvalue123\n", "credential-like"),
        (b"OPENAI_" + b"API_KEY=nonempty\n", "environment-assignment"),
        (b"tasks/" + b"worker_registry/private.md\n", "private-operational-record"),
    ],
)
def test_source_archive_rejects_each_privacy_category(
    data: bytes, category: str
) -> None:
    entries = source_entries() + [
        TarEntry(f"{SOURCE_ROOT}/docs/leak.txt", data)
    ]
    result = verify_source(tar_bytes(entries), records_for(entries))

    assert result.ok is False
    assert any(category in item for item in result.errors)


def test_license_skips_only_reviewed_user_identifier_line() -> None:
    api = _api()
    copyright_line = b"Copyright (c) 2026 Example Person\n"
    errors = api.scan_forbidden_text(PurePosixPath("LICENSE"), copyright_line)

    assert "user-or-host-identifier" not in errors


def test_standalone_verifier_does_not_flag_its_own_public_rules() -> None:
    api = _api()
    path = ROOT / "tools" / "verify_handoff_archive.py"

    assert api.scan_forbidden_text(
        PurePosixPath("tools/verify_handoff_archive.py"),
        path.read_bytes(),
    ) == ()


def test_source_archive_rejects_wrong_hash() -> None:
    entries = source_entries()
    result = verify_source(tar_bytes(entries), records_for(entries), expected_hash="0" * 64)

    assert result.ok is False
    assert "sha256 mismatch" in result.errors


def test_source_archive_rejects_wrong_regular_file_count() -> None:
    entries = source_entries()
    records = records_for(entries)
    result = verify_source(tar_bytes(entries), records, expected_count=len(records) + 1)

    assert result.ok is False
    assert "regular file count mismatch" in result.errors


def test_source_archive_rejects_required_file_omission() -> None:
    entries = [
        entry for entry in source_entries() if not entry.name.endswith("/README.md")
    ]
    result = verify_source(tar_bytes(entries), records_for(entries))

    assert result.ok is False
    assert "required source member missing: README.md" in result.errors


def test_source_archive_rejects_duplicate_manifest_path() -> None:
    entries = source_entries()
    records = records_for(entries)
    data = tar_bytes(entries)
    duplicate = FixtureRecord(
        path=records[0].path,
        mode=0o600,
        size=records[0].size,
        sha256=records[0].sha256,
    )
    api = _api()
    result = api.verify_source_archive_bytes(
        data,
        expected_sha256=sha256(data),
        expected_regular_file_count=len(records),
        expected_members=expected_records(records + [duplicate]),
    )

    assert result.ok is False
    assert any("duplicate expected member path" in item for item in result.errors)


def test_source_archive_rejects_mode_mismatch() -> None:
    entries = source_entries()
    records = records_for(entries)
    records[0] = FixtureRecord(
        path=records[0].path,
        mode=0o600,
        size=records[0].size,
        sha256=records[0].sha256,
    )
    result = verify_source(tar_bytes(entries), records)

    assert result.ok is False
    assert any("member metadata mismatch" in item for item in result.errors)


def test_source_archive_rejects_unexpected_member() -> None:
    base = source_entries()
    records = records_for(base)
    data = tar_bytes(base + [TarEntry(f"{SOURCE_ROOT}/private.txt", b"x")])
    result = verify_source(data, records, expected_count=len(records))

    assert result.ok is False
    assert "unexpected member: private.txt" in result.errors


def test_friend_pack_accepts_exact_detached_and_nested_bytes(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path)

    result = verify_pack(fixture)

    assert result.ok is True
    assert result.artifact_kind == "friend-pack"
    assert result.sha256 == fixture.pack_sha256
    assert result.root_name == PACK_ROOT
    assert result.errors == ()


def test_friend_pack_rejects_detached_verifier_digest_mismatch(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path, detached_bytes=b"different\n")
    result = verify_pack(fixture)

    assert result.ok is False
    assert "detached verifier sha256 mismatch" in result.errors


def test_friend_pack_rejects_inpack_verifier_mismatch(tmp_path: Path) -> None:
    expected = b"#!/usr/bin/env python3\n"
    fixture = make_friend_pack(
        tmp_path,
        detached_bytes=expected,
        inpack_verifier_bytes=b"#!/usr/bin/env python3\n# changed\n",
    )
    result = verify_pack(
        fixture,
        expected_verifier_sha256=sha256(expected),
    )

    assert result.ok is False
    assert "in-pack verifier sha256 mismatch" in result.errors


def test_friend_pack_rejects_pack_digest_mismatch(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path)
    result = verify_pack(fixture, expected_pack_sha256="0" * 64)

    assert result.ok is False
    assert "pack sha256 mismatch" in result.errors


def test_friend_pack_rejects_source_digest_mismatch(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path)
    result = verify_pack(fixture, expected_source_sha256="0" * 64)

    assert result.ok is False
    assert "source archive sha256 mismatch" in result.errors


def test_friend_pack_rejects_manifest_checksum_mismatch(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path, bad_manifest_checksum=True)
    result = verify_pack(fixture)

    assert result.ok is False
    assert "manifest checksum mismatch" in result.errors


@pytest.mark.parametrize(
    "missing",
    [
        "FRIEND_LAB.md",
        "source/agent-frontdoor-0.1.0.tar.gz",
        "source/source-manifest.json",
        "verifier/verify_handoff_archive.py",
        "lab/controls/privacy_control.txt",
    ],
)
def test_friend_pack_rejects_missing_outer_member(
    tmp_path: Path, missing: str
) -> None:
    fixture = make_friend_pack(tmp_path, missing_payload=missing)
    result = verify_pack(fixture)

    assert result.ok is False
    assert any("missing outer member" in item for item in result.errors)


def test_friend_pack_rejects_extra_outer_member(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path, extra_payload=True)
    result = verify_pack(fixture)

    assert result.ok is False
    assert "unexpected outer member: unexpected.txt" in result.errors


def test_friend_pack_rejects_malformed_manifest(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path, malformed_manifest=True)
    result = verify_pack(fixture)

    assert result.ok is False
    assert any("manifest invalid" in item for item in result.errors)


def test_friend_pack_rejects_privacy_control_hash_mismatch(tmp_path: Path) -> None:
    fixture = make_friend_pack(tmp_path, bad_privacy_control_hash=True)
    result = verify_pack(fixture)

    assert result.ok is False
    assert "privacy control sha256 mismatch" in result.errors


def test_friend_pack_inspects_nested_source_without_extracting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = source_entries() + [
        TarEntry(f"{SOURCE_ROOT}/../escape", b"unsafe")
    ]
    data = tar_bytes(entries)
    fixture = make_friend_pack(
        tmp_path,
        source_data=data,
        source_records=records_for(source_entries()),
    )

    def forbidden_extract(*_args, **_kwargs):
        raise AssertionError("filesystem extraction is forbidden")

    monkeypatch.setattr(tarfile.TarFile, "extract", forbidden_extract)
    monkeypatch.setattr(tarfile.TarFile, "extractall", forbidden_extract)
    result = verify_pack(fixture)

    assert result.ok is False
    assert any("unsafe archive member" in item for item in result.errors)


def test_source_cli_prints_one_stable_pass_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api = _api()
    entries = source_entries()
    records = records_for(entries)
    data = tar_bytes(entries)
    archive = tmp_path / "source.tar.gz"
    archive.write_bytes(data)
    manifest = tmp_path / "source-manifest.json"
    manifest.write_bytes(json_bytes(source_manifest(records)))

    rc = api.main(
        [
            "source",
            str(archive),
            "--expected-sha256",
            sha256(data),
            "--expected-files",
            str(len(records)),
            "--manifest",
            str(manifest),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert captured.out == (
        f"PASS source sha256={sha256(data)} files={len(records)} "
        f"root={SOURCE_ROOT}\n"
    )


def test_source_cli_prints_sorted_failure_reasons(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api = _api()
    entries = source_entries()
    records = records_for(entries)
    data = tar_bytes(entries)
    archive = tmp_path / "source.tar.gz"
    archive.write_bytes(data)
    manifest = tmp_path / "source-manifest.json"
    manifest.write_bytes(json_bytes(source_manifest(records)))

    rc = api.main(
        [
            "source",
            str(archive),
            "--expected-sha256",
            "0" * 64,
            "--expected-files",
            str(len(records) + 1),
            "--manifest",
            str(manifest),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err == ""
    assert captured.out == (
        "FAIL source\n"
        "- regular file count mismatch\n"
        "- sha256 mismatch\n"
    )


def test_cli_malformed_arguments_use_argparse_exit_two() -> None:
    api = _api()
    with pytest.raises(SystemExit) as raised:
        api.main(["source"])

    assert raised.value.code == 2
