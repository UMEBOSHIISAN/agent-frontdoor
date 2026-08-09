#!/usr/bin/env python3
"""Standalone, extraction-free verifier for Agent Frontdoor handoff archives."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Sequence
import tarfile


PRIVACY_CATEGORIES: tuple[str, ...] = (
    "absolute-user-path",
    "user-or-host-identifier",
    "ip-address",
    "credential-like",
    "environment-assignment",
    "private-operational-record",
)

_SOURCE_ROOT = "agent-frontdoor-0.2.0"
_PACK_ROOT = "agent-frontdoor-friend-pack-0.2.0"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED_SOURCE_MEMBERS = frozenset(
    {
        "CHANGELOG.md",
        "LICENSE",
        "README.md",
        "pyproject.toml",
        "src/frontdoor/__init__.py",
        "src/frontdoor/schema/intake.v0.json",
        "tests/test_cli.py",
        "tools/verify_handoff_archive.py",
    }
)
_FORBIDDEN_COMPONENTS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        ".env",
        ".claude",
        ".codex",
        "memory",
        "logs",
    }
)
_DOCUMENTATION_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "example.test",
        "example.invalid",
    }
)
_SENSITIVE_ENV_RE = re.compile(
    r"(?im)^\s*([A-Z][A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|"
    r"PASSWORD|SECRET|CREDENTIALS?))\s*=\s*([^\s#]+)"
)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(password|token|secret|api[_-]?key)\b\s*[:=]\s*([^\s#]+)"
)
_IDENTIFIER_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(username|hostname|account)\b\s*[:=]\s*([^\s#]+)"
)
_USER_HOST_RE = re.compile(
    r"(?<![\w.+-])([A-Za-z0-9._-]+)@([A-Za-z0-9.-]+)(?![\w.-])"
)
_IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_IPV6_RE = re.compile(
    r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])"
)
_TOKEN_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|"
    r"github_pat_[A-Za-z0-9_]{8,}|xox[baprs]-[A-Za-z0-9-]{8,}|"
    r"AKIA[A-Z0-9]{12,})(?![A-Za-z0-9])"
)


@dataclass(frozen=True)
class MemberRecord:
    path: str
    mode: int
    size: int
    sha256: str


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    artifact_kind: str
    sha256: str | None
    regular_file_count: int
    root_name: str | None
    errors: tuple[str, ...]
    members: tuple[MemberRecord, ...] = ()


@dataclass(frozen=True)
class _ArchiveInspection:
    root_name: str | None
    members: tuple[MemberRecord, ...]
    payloads: dict[str, bytes]
    errors: tuple[str, ...]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _member_record(name: str, mode: int, data: bytes) -> MemberRecord:
    return MemberRecord(
        path=name,
        mode=mode,
        size=len(data),
        sha256=_sha256_bytes(data),
    )


def _stable_errors(errors: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(errors)))


def _result(
    artifact_kind: str,
    *,
    sha256: str | None,
    regular_file_count: int = 0,
    root_name: str | None = None,
    errors: Sequence[str] = (),
    members: tuple[MemberRecord, ...] = (),
) -> VerificationResult:
    stable = _stable_errors(errors)
    return VerificationResult(
        ok=not stable,
        artifact_kind=artifact_kind,
        sha256=sha256,
        regular_file_count=regular_file_count,
        root_name=root_name,
        errors=stable,
        members=members,
    )


def _is_metavariable(value: str) -> bool:
    stripped = value.strip().strip("'\"")
    return stripped.startswith("<") and stripped.endswith(">")


def _masked_documentation_values(text: str) -> str:
    return re.sub(r"<[^>\r\n]+>", "", text)


def _contains_ip_literal(text: str) -> bool:
    for pattern in (_IPV4_RE, _IPV6_RE):
        for match in pattern.finditer(text):
            candidate = match.group(0)
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            return True
    return False


def _is_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def scan_forbidden_text(
    path: PurePosixPath, data: bytes
) -> tuple[str, ...]:
    """Return closed privacy categories found in one UTF-8 text member."""

    if _is_binary(data):
        return ()
    text = data.decode("utf-8")
    masked = _masked_documentation_values(text)
    hits: set[str] = set()

    posix_home = "/" + "Users" + "/"
    unix_home = "/" + "home" + "/"
    windows_home = "\\" + "Users" + "\\"
    if (
        re.search(re.escape(posix_home) + r"[^/\s<>]+", masked)
        or re.search(re.escape(unix_home) + r"[^/\s<>]+", masked)
        or re.search(
            r"[A-Za-z]:" + re.escape(windows_home) + r"[^\\\s<>]+",
            masked,
        )
    ):
        hits.add("absolute-user-path")

    if path.name != "LICENSE":
        for match in _IDENTIFIER_ASSIGNMENT_RE.finditer(masked):
            if not _is_metavariable(match.group(2)):
                hits.add("user-or-host-identifier")
                break
        if "user-or-host-identifier" not in hits:
            for match in _USER_HOST_RE.finditer(masked):
                host = match.group(2).lower()
                if host not in _DOCUMENTATION_DOMAINS and not host.endswith(
                    tuple("." + item for item in _DOCUMENTATION_DOMAINS)
                ):
                    hits.add("user-or-host-identifier")
                    break

    if _contains_ip_literal(masked):
        hits.add("ip-address")

    private_key_header = "-----BEGIN " + "PRIVATE KEY-----"
    private_key_suffix = "-----BEGIN " + "RSA PRIVATE KEY-----"
    if (
        private_key_header in masked
        or private_key_suffix in masked
        or re.search(r"(?i)\bBearer\s+[^\s<>]+", masked)
        or _TOKEN_PREFIX_RE.search(masked)
    ):
        hits.add("credential-like")
    for match in _CREDENTIAL_ASSIGNMENT_RE.finditer(masked):
        if not _is_metavariable(match.group(2)):
            hits.add("credential-like")
            break

    for match in _SENSITIVE_ENV_RE.finditer(masked):
        if not _is_metavariable(match.group(2)):
            hits.add("environment-assignment")
            break

    operational_markers = (
        "memory" + "/",
        "tasks" + "/worker_registry/",
        "." + "claude/",
        "." + "codex/",
        "runtime" + "/ledger",
        "runtime" + "/logs",
    )
    if any(marker in masked for marker in operational_markers):
        hits.add("private-operational-record")

    return tuple(item for item in PRIVACY_CATEGORIES if item in hits)


def scan_forbidden_path(path: PurePosixPath) -> tuple[str, ...]:
    """Return closed privacy categories found in one archive-relative path."""

    value = path.as_posix()
    hits: set[str] = set()
    windows_posix_home = "/" + "Users" + "/"
    if (
        value.startswith("/" + "Users" + "/")
        or value.startswith("/" + "home" + "/")
        or re.match(r"[A-Za-z]:" + re.escape(windows_posix_home), value)
    ):
        hits.add("absolute-user-path")
    markers = (
        "memory" + "/",
        "tasks" + "/worker_registry/",
        "." + "claude/",
        "." + "codex/",
        "runtime" + "/ledger",
        "runtime" + "/logs",
    )
    if any(marker in value for marker in markers):
        hits.add("private-operational-record")
    return tuple(item for item in PRIVACY_CATEGORIES if item in hits)


def _unsafe_member_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        return True
    parts = PurePosixPath(name).parts
    return not parts or any(part in {"", ".", ".."} for part in parts)


def _forbidden_relative_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part in _FORBIDDEN_COMPONENTS for part in parts)


def _inspect_archive(
    data: bytes,
    *,
    artifact_label: str,
    required_root: str,
    privacy_control: tuple[str, str] | None = None,
    scan_text: bool = True,
) -> _ArchiveInspection:
    errors: list[str] = []
    payloads: dict[str, bytes] = {}
    records: list[MemberRecord] = []
    root_name: str | None = None

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = archive.getmembers()
            roots: set[str] = set()
            seen_names: set[str] = set()
            structurally_safe: list[tarfile.TarInfo] = []

            for member in members:
                name = member.name
                if name in seen_names:
                    errors.append(f"duplicate archive member: {name}")
                    continue
                seen_names.add(name)
                if _unsafe_member_name(name):
                    errors.append(f"unsafe archive member: {name}")
                    continue
                parts = PurePosixPath(name).parts
                roots.add(parts[0])
                if not (member.isfile() or member.isdir()):
                    errors.append(f"forbidden member type: {name}")
                    continue
                structurally_safe.append(member)

            if len(roots) != 1:
                errors.append("single archive root required")
            else:
                root_name = next(iter(roots))
                if root_name != required_root:
                    errors.append(
                        f"{artifact_label} root mismatch: {root_name}"
                    )

            if errors:
                return _ArchiveInspection(
                    root_name=root_name,
                    members=(),
                    payloads={},
                    errors=_stable_errors(errors),
                )

            prefix = required_root + "/"
            for member in structurally_safe:
                if member.name == required_root and member.isdir():
                    continue
                if not member.name.startswith(prefix):
                    errors.append(f"unsafe archive member: {member.name}")
                    continue
                relative = member.name[len(prefix) :].rstrip("/")
                if not relative or _forbidden_relative_path(relative):
                    errors.append(f"forbidden archive path: {relative}")
                    continue
                path_hits = scan_forbidden_path(PurePosixPath(relative))
                errors.extend(
                    f"privacy {category} in path: {relative}"
                    for category in path_hits
                )
                if member.isdir():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    errors.append(f"archive member unreadable: {relative}")
                    continue
                member_data = extracted.read()
                payloads[relative] = member_data
                records.append(
                    _member_record(
                        relative,
                        member.mode & 0o777,
                        member_data,
                    )
                )

            control_path = control_sha = None
            if privacy_control is not None:
                control_path, control_sha = privacy_control
            if scan_text:
                for relative, member_data in payloads.items():
                    if (
                        control_path is not None
                        and relative == control_path
                        and _sha256_bytes(member_data) == control_sha
                    ):
                        continue
                    for category in scan_forbidden_text(
                        PurePosixPath(relative), member_data
                    ):
                        errors.append(
                            f"privacy {category} in member: {relative}"
                        )
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        message = str(exc).strip()
        suffix = f": {message}" if message else ""
        errors.append(f"archive unreadable{suffix}")

    return _ArchiveInspection(
        root_name=root_name,
        members=tuple(sorted(records, key=lambda item: item.path)),
        payloads=payloads,
        errors=_stable_errors(errors),
    )


def _compare_member_records(
    actual: tuple[MemberRecord, ...],
    expected: tuple[MemberRecord, ...],
    *,
    missing_label: str,
    unexpected_label: str,
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_paths: set[str] = set()
    for record in expected:
        if record.path in expected_paths:
            errors.append(f"duplicate expected member path: {record.path}")
        expected_paths.add(record.path)
    actual_by_path = {item.path: item for item in actual}
    expected_by_path = {item.path: item for item in expected}

    for path in sorted(expected_by_path.keys() - actual_by_path.keys()):
        errors.append(f"{missing_label}: {path}")
    for path in sorted(actual_by_path.keys() - expected_by_path.keys()):
        errors.append(f"{unexpected_label}: {path}")
    for path in sorted(actual_by_path.keys() & expected_by_path.keys()):
        if actual_by_path[path] != expected_by_path[path]:
            errors.append(f"member metadata mismatch: {path}")
    return _stable_errors(errors)


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _open_snapshot_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(descriptor)
        raise OSError("snapshot component is not a directory")
    if opened.st_mode & 0o077:
        os.close(descriptor)
        raise OSError("snapshot directory is not private")
    return descriptor


def _write_snapshot_member(
    root_fd: int,
    record: MemberRecord,
    data: bytes,
) -> None:
    parts = PurePosixPath(record.path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise OSError("snapshot member path invalid")
    parent_fd = os.dup(root_fd)
    descriptor = -1
    try:
        for component in parts[:-1]:
            child_fd = _open_snapshot_directory(parent_fd, component)
            os.close(parent_fd)
            parent_fd = child_fd
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(
            parts[-1], flags, record.mode, dir_fd=parent_fd
        )
        os.fchmod(descriptor, record.mode)
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("snapshot member write incomplete")
            remaining = remaining[written:]
        os.fsync(descriptor)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_mode & 0o777 != record.mode
            or observed.st_size != record.size
        ):
            raise OSError("snapshot member metadata mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        if digest.hexdigest() != record.sha256:
            raise OSError("snapshot member digest mismatch")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _materialize_verified_snapshot(
    inspection: _ArchiveInspection,
    destination: Path,
) -> tuple[str, ...]:
    if (
        inspection.errors
        or inspection.root_name != _PACK_ROOT
        or destination.name != _PACK_ROOT
    ):
        return ("snapshot destination invalid",)
    parent_fd = root_fd = -1
    try:
        parent = destination.parent
        parent_before = parent.lstat()
        if (
            not stat.S_ISDIR(parent_before.st_mode)
            or parent_before.st_mode & 0o077
        ):
            raise OSError("snapshot parent is not private")
        parent_fd = os.open(parent, _directory_flags())
        parent_opened = os.fstat(parent_fd)
        if (
            not stat.S_ISDIR(parent_opened.st_mode)
            or (parent_before.st_dev, parent_before.st_ino)
            != (parent_opened.st_dev, parent_opened.st_ino)
            or parent_opened.st_mode & 0o077
        ):
            raise OSError("snapshot parent changed")
        os.mkdir(destination.name, mode=0o700, dir_fd=parent_fd)
        root_fd = os.open(
            destination.name, _directory_flags(), dir_fd=parent_fd
        )
        os.fchmod(root_fd, 0o700)
        by_path = {record.path: record for record in inspection.members}
        if set(by_path) != set(inspection.payloads):
            raise OSError("snapshot member set mismatch")
        for relative in sorted(by_path):
            record = by_path[relative]
            data = inspection.payloads[relative]
            if (
                len(data) != record.size
                or _sha256_bytes(data) != record.sha256
            ):
                raise OSError("snapshot payload mismatch")
            _write_snapshot_member(root_fd, record, data)
        parent_after = destination.parent.lstat()
        if (parent_after.st_dev, parent_after.st_ino) != (
            parent_opened.st_dev,
            parent_opened.st_ino,
        ):
            raise OSError("snapshot parent changed")
    except (OSError, ValueError):
        return ("snapshot materialization failed",)
    finally:
        if root_fd >= 0:
            os.close(root_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
    return ()


def verify_source_archive_bytes(
    data: bytes,
    *,
    expected_sha256: str,
    expected_regular_file_count: int,
    expected_members: tuple[MemberRecord, ...],
) -> VerificationResult:
    """Verify a public source archive without extracting it."""

    actual_sha = _sha256_bytes(data)
    errors: list[str] = []
    if actual_sha != expected_sha256:
        errors.append("sha256 mismatch")

    inspection = _inspect_archive(
        data,
        artifact_label="source archive",
        required_root=_SOURCE_ROOT,
    )
    errors.extend(inspection.errors)
    actual_count = len(inspection.members)
    if actual_count != expected_regular_file_count:
        errors.append("regular file count mismatch")
    errors.extend(
        _compare_member_records(
            inspection.members,
            expected_members,
            missing_label="missing member",
            unexpected_label="unexpected member",
        )
    )
    actual_paths = {item.path for item in inspection.members}
    for required in sorted(_REQUIRED_SOURCE_MEMBERS - actual_paths):
        errors.append(f"required source member missing: {required}")

    return _result(
        "source",
        sha256=actual_sha,
        regular_file_count=actual_count,
        root_name=inspection.root_name,
        errors=errors,
        members=inspection.members,
    )


def _records_from_json(
    value: object, *, label: str
) -> tuple[tuple[MemberRecord, ...], tuple[str, ...]]:
    if not isinstance(value, list):
        return (), (f"{label} members must be an array",)
    records: list[MemberRecord] = []
    errors: list[str] = []
    required_keys = {"path", "mode", "size", "sha256"}
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != required_keys:
            errors.append(f"{label} member {index} invalid")
            continue
        path = item.get("path")
        mode = item.get("mode")
        size = item.get("size")
        digest = item.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or _unsafe_member_name(path)
            or not isinstance(mode, int)
            or isinstance(mode, bool)
            or mode < 0
            or mode > 0o777
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not _HEX64.fullmatch(digest)
        ):
            errors.append(f"{label} member {index} invalid")
            continue
        records.append(
            MemberRecord(path=path, mode=mode, size=size, sha256=digest)
        )
    if [item.path for item in records] != sorted(
        item.path for item in records
    ):
        errors.append(f"{label} members not sorted")
    paths = [item.path for item in records]
    if len(paths) != len(set(paths)):
        errors.append(f"{label} member paths not unique")
    return tuple(records), _stable_errors(errors)


def _load_source_manifest_bytes(
    data: bytes,
) -> tuple[tuple[MemberRecord, ...], int | None, str | None, tuple[str, ...]]:
    errors: list[str] = []
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return (), None, None, (f"source manifest invalid: {exc}",)
    required = {
        "schema_version",
        "package_version",
        "public_revision",
        "archive_root",
        "regular_file_count",
        "members",
    }
    if not isinstance(value, dict) or set(value) != required:
        return (), None, None, ("source manifest invalid: fields",)
    if value.get("schema_version") != "source-archive-manifest.v1":
        errors.append("source manifest invalid: schema_version")
    if value.get("package_version") != "0.2.0":
        errors.append("source manifest invalid: package_version")
    revision = value.get("public_revision")
    if not isinstance(revision, str) or not re.fullmatch(
        r"[0-9a-f]{40}", revision
    ):
        errors.append("source manifest invalid: public_revision")
    root = value.get("archive_root")
    if root != _SOURCE_ROOT:
        errors.append("source manifest invalid: archive_root")
    count = value.get("regular_file_count")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
    ):
        errors.append("source manifest invalid: regular_file_count")
        count = None
    records, record_errors = _records_from_json(
        value.get("members"), label="source manifest"
    )
    errors.extend(record_errors)
    if count is not None and count != len(records):
        errors.append("source manifest invalid: member count")
    return records, count, root if isinstance(root, str) else None, _stable_errors(errors)


def _field_path_and_sha(
    manifest: dict[str, object],
    field: str,
    *,
    extra_keys: frozenset[str] = frozenset(),
) -> tuple[str | None, str | None, tuple[str, ...]]:
    value = manifest.get(field)
    expected_keys = {"path", "sha256"} | set(extra_keys)
    if not isinstance(value, dict) or set(value) != expected_keys:
        return None, None, (f"manifest invalid: {field}",)
    path = value.get("path")
    digest = value.get("sha256")
    if (
        not isinstance(path, str)
        or _unsafe_member_name(path)
        or not isinstance(digest, str)
        or not _HEX64.fullmatch(digest)
    ):
        return None, None, (f"manifest invalid: {field}",)
    return path, digest, ()


def _load_pack_manifest_bytes(
    data: bytes,
) -> tuple[dict[str, object] | None, tuple[MemberRecord, ...], tuple[str, ...]]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, (), (f"manifest invalid: {exc}",)
    required = {
        "schema_version",
        "package_version",
        "public_revision",
        "source_archive",
        "verifier",
        "privacy_control",
        "self_exclusions",
        "members",
    }
    if not isinstance(value, dict) or set(value) != required:
        return None, (), ("manifest invalid: fields",)
    errors: list[str] = []
    if value.get("schema_version") != "friend-pack-manifest.v1":
        errors.append("manifest invalid: schema_version")
    if value.get("package_version") != "0.2.0":
        errors.append("manifest invalid: package_version")
    revision = value.get("public_revision")
    if not isinstance(revision, str) or not re.fullmatch(
        r"[0-9a-f]{40}", revision
    ):
        errors.append("manifest invalid: public_revision")
    if value.get("self_exclusions") != ["manifest.json", "manifest.sha256"]:
        errors.append("manifest invalid: self_exclusions")
    records, record_errors = _records_from_json(
        value.get("members"), label="outer manifest"
    )
    errors.extend(record_errors)
    return value, records, _stable_errors(errors)


def verify_friend_pack(
    pack_path: Path,
    *,
    detached_verifier_path: Path,
    expected_pack_sha256: str,
    expected_source_sha256: str,
    expected_verifier_sha256: str,
    materialize_to: Path | None = None,
) -> VerificationResult:
    """Verify detached trust, outer pack membership, and nested source bytes."""

    errors: list[str] = []
    try:
        pack_data = pack_path.read_bytes()
    except OSError as exc:
        return _result(
            "friend-pack", sha256=None, errors=(f"pack unreadable: {exc}",)
        )
    actual_pack_sha = _sha256_bytes(pack_data)
    try:
        detached_data = detached_verifier_path.read_bytes()
    except OSError as exc:
        return _result(
            "friend-pack",
            sha256=actual_pack_sha,
            errors=(f"detached verifier unreadable: {exc}",),
        )
    if actual_pack_sha != expected_pack_sha256:
        errors.append("pack sha256 mismatch")
    if _sha256_bytes(detached_data) != expected_verifier_sha256:
        errors.append("detached verifier sha256 mismatch")
    if errors:
        return _result(
            "friend-pack", sha256=actual_pack_sha, errors=errors
        )

    initial = _inspect_archive(
        pack_data,
        artifact_label="friend pack",
        required_root=_PACK_ROOT,
        scan_text=False,
    )
    errors.extend(initial.errors)
    if initial.errors:
        return _result(
            "friend-pack",
            sha256=actual_pack_sha,
            regular_file_count=len(initial.members),
            root_name=initial.root_name,
            errors=errors,
        )

    manifest_data = initial.payloads.get("manifest.json")
    checksum_data = initial.payloads.get("manifest.sha256")
    if manifest_data is None:
        errors.append("missing outer member: manifest.json")
    if checksum_data is None:
        errors.append("missing outer member: manifest.sha256")
    if manifest_data is None or checksum_data is None:
        return _result(
            "friend-pack",
            sha256=actual_pack_sha,
            regular_file_count=len(initial.members),
            root_name=initial.root_name,
            errors=errors,
        )

    checksum_text = checksum_data.decode("ascii", errors="replace").strip()
    if not _HEX64.fullmatch(checksum_text) or checksum_text != _sha256_bytes(
        manifest_data
    ):
        errors.append("manifest checksum mismatch")

    manifest, expected_outer, manifest_errors = _load_pack_manifest_bytes(
        manifest_data
    )
    errors.extend(manifest_errors)
    if manifest is None:
        return _result(
            "friend-pack",
            sha256=actual_pack_sha,
            regular_file_count=len(initial.members),
            root_name=initial.root_name,
            errors=errors,
        )

    actual_outer = tuple(
        item
        for item in initial.members
        if item.path not in {"manifest.json", "manifest.sha256"}
    )
    errors.extend(
        _compare_member_records(
            actual_outer,
            expected_outer,
            missing_label="missing outer member",
            unexpected_label="unexpected outer member",
        )
    )

    source_path, manifest_source_sha, source_field_errors = _field_path_and_sha(
        manifest,
        "source_archive",
        extra_keys=frozenset({"regular_file_count", "manifest_path"}),
    )
    verifier_path, manifest_verifier_sha, verifier_field_errors = (
        _field_path_and_sha(manifest, "verifier")
    )
    control_path, manifest_control_sha, control_field_errors = (
        _field_path_and_sha(manifest, "privacy_control")
    )
    errors.extend(source_field_errors)
    errors.extend(verifier_field_errors)
    errors.extend(control_field_errors)

    source_section = manifest.get("source_archive")
    source_manifest_path: str | None = None
    source_count: int | None = None
    if isinstance(source_section, dict):
        candidate_path = source_section.get("manifest_path")
        candidate_count = source_section.get("regular_file_count")
        if isinstance(candidate_path, str) and not _unsafe_member_name(
            candidate_path
        ):
            source_manifest_path = candidate_path
        else:
            errors.append("manifest invalid: source_archive manifest_path")
        if (
            isinstance(candidate_count, int)
            and not isinstance(candidate_count, bool)
            and candidate_count >= 0
        ):
            source_count = candidate_count
        else:
            errors.append("manifest invalid: source_archive regular_file_count")

    nested_data = initial.payloads.get(source_path or "")
    inpack_verifier = initial.payloads.get(verifier_path or "")
    privacy_control_data = initial.payloads.get(control_path or "")
    source_manifest_data = initial.payloads.get(source_manifest_path or "")

    if source_path is not None and nested_data is None:
        errors.append(f"missing outer member: {source_path}")
    if verifier_path is not None and inpack_verifier is None:
        errors.append(f"missing outer member: {verifier_path}")
    if control_path is not None and privacy_control_data is None:
        errors.append(f"missing outer member: {control_path}")
    if source_manifest_path is not None and source_manifest_data is None:
        errors.append(f"missing outer member: {source_manifest_path}")

    if nested_data is not None:
        nested_sha = _sha256_bytes(nested_data)
        if nested_sha != expected_source_sha256:
            errors.append("source archive sha256 mismatch")
        if manifest_source_sha is not None and nested_sha != manifest_source_sha:
            errors.append("source archive manifest sha256 mismatch")
    if inpack_verifier is not None:
        inpack_sha = _sha256_bytes(inpack_verifier)
        if inpack_sha != expected_verifier_sha256:
            errors.append("in-pack verifier sha256 mismatch")
        if manifest_verifier_sha is not None and inpack_sha != manifest_verifier_sha:
            errors.append("verifier manifest sha256 mismatch")
    if privacy_control_data is not None and manifest_control_sha is not None:
        if _sha256_bytes(privacy_control_data) != manifest_control_sha:
            errors.append("privacy control sha256 mismatch")

    trusted_control: tuple[str, str] | None = None
    if (
        control_path is not None
        and privacy_control_data is not None
        and manifest_control_sha is not None
        and _sha256_bytes(privacy_control_data) == manifest_control_sha
    ):
        trusted_control = (control_path, manifest_control_sha)
    for relative, member_data in initial.payloads.items():
        if (
            trusted_control is not None
            and relative == trusted_control[0]
            and _sha256_bytes(member_data) == trusted_control[1]
        ):
            continue
        for category in scan_forbidden_text(
            PurePosixPath(relative), member_data
        ):
            errors.append(f"privacy {category} in member: {relative}")

    if nested_data is not None and source_manifest_data is not None:
        source_records, manifest_count, _root, source_manifest_errors = (
            _load_source_manifest_bytes(source_manifest_data)
        )
        errors.extend(source_manifest_errors)
        effective_count = source_count
        if manifest_count is not None:
            if source_count is not None and source_count != manifest_count:
                errors.append("source manifest count mismatch")
            effective_count = manifest_count
        if not source_manifest_errors and effective_count is not None:
            nested_result = verify_source_archive_bytes(
                nested_data,
                expected_sha256=expected_source_sha256,
                expected_regular_file_count=effective_count,
                expected_members=source_records,
            )
            errors.extend(nested_result.errors)

    if not _stable_errors(errors) and materialize_to is not None:
        errors.extend(
            _materialize_verified_snapshot(initial, materialize_to)
        )

    return _result(
        "friend-pack",
        sha256=actual_pack_sha,
        regular_file_count=len(initial.members),
        root_name=initial.root_name,
        errors=errors,
        members=initial.members,
    )


def _source_result_from_paths(args: argparse.Namespace) -> VerificationResult:
    try:
        data = args.archive.read_bytes()
    except OSError as exc:
        return _result("source", sha256=None, errors=(f"archive unreadable: {exc}",))
    try:
        manifest_data = args.manifest.read_bytes()
    except OSError as exc:
        return _result(
            "source",
            sha256=_sha256_bytes(data),
            errors=(f"source manifest unreadable: {exc}",),
        )
    records, manifest_count, _root, errors = _load_source_manifest_bytes(
        manifest_data
    )
    if errors:
        return _result(
            "source", sha256=_sha256_bytes(data), errors=errors
        )
    return verify_source_archive_bytes(
        data,
        expected_sha256=args.expected_sha256,
        expected_regular_file_count=args.expected_files,
        expected_members=records,
    )


def _print_result(result: VerificationResult) -> int:
    if result.ok:
        print(
            f"PASS {result.artifact_kind} sha256={result.sha256} "
            f"files={result.regular_file_count} root={result.root_name}"
        )
        return 0
    print(f"FAIL {result.artifact_kind}")
    for error in result.errors:
        print(f"- {error}")
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Agent Frontdoor handoff archives without extraction."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("source")
    source.add_argument("archive", type=Path)
    source.add_argument("--expected-sha256", required=True)
    source.add_argument("--expected-files", required=True, type=int)
    source.add_argument("--manifest", required=True, type=Path)

    friend_pack = commands.add_parser("friend-pack")
    friend_pack.add_argument("pack", type=Path)
    friend_pack.add_argument("--detached-verifier", required=True, type=Path)
    friend_pack.add_argument("--expected-pack-sha256", required=True)
    friend_pack.add_argument("--expected-source-sha256", required=True)
    friend_pack.add_argument("--expected-verifier-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "source":
        return _print_result(_source_result_from_paths(args))
    return _print_result(
        verify_friend_pack(
            args.pack,
            detached_verifier_path=args.detached_verifier,
            expected_pack_sha256=args.expected_pack_sha256,
            expected_source_sha256=args.expected_source_sha256,
            expected_verifier_sha256=args.expected_verifier_sha256,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
