#!/usr/bin/env python3
"""Build deterministic, receiver-bound Agent Frontdoor friend packs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
from typing import Iterable, Mapping
import zipfile

from tools.verify_handoff_archive import (
    MemberRecord,
    scan_forbidden_text,
    verify_friend_pack,
    verify_source_archive_bytes,
)


PACKAGE_VERSION = "0.1.0"
SOURCE_ROOT = f"agent-frontdoor-{PACKAGE_VERSION}"
PACK_ROOT = f"agent-frontdoor-friend-pack-{PACKAGE_VERSION}"
PACK_FILENAME = f"{PACK_ROOT}.tar.gz"
DETACHED_VERIFIER_FILENAME = "verify_handoff_archive.py"
LOCK_FILENAME = "wheelhouse-manifest.json"

_TARGET_FIELDS = {
    "os_version",
    "architecture",
    "python_minor",
    "abi_tag",
    "platform_tags",
    "pip_version",
}
_REQUIRED_DISTRIBUTIONS = frozenset(
    {
        "agent-frontdoor",
        "attrs",
        "iniconfig",
        "jsonschema",
        "jsonschema-specifications",
        "packaging",
        "pluggy",
        "pygments",
        "pytest",
        "referencing",
        "rpds-py",
        "setuptools",
        "wheel",
    }
)
_PUBLIC_PACK_FILES = {
    "FRIEND_LAB.md": "docs/FRIEND_LAB.md",
    "verifier/verify_handoff_archive.py": "tools/verify_handoff_archive.py",
    "schemas/friend_acceptance_receipt.v1.json": (
        "schemas/friend_acceptance_receipt.v1.json"
    ),
    "schemas/friend_pack_manifest.v1.json": (
        "schemas/friend_pack_manifest.v1.json"
    ),
    "schemas/source_archive_manifest.v1.json": (
        "schemas/source_archive_manifest.v1.json"
    ),
    "schemas/wheelhouse_manifest.v1.json": (
        "schemas/wheelhouse_manifest.v1.json"
    ),
    "lab/acceptance_runner.py": "tools/friend_lab/acceptance_runner.py",
    "lab/sitecustomize.py": "tools/friend_lab/sitecustomize.py",
    "lab/controls/write_outside_probe.py": (
        "tools/friend_lab/controls/write_outside_probe.py"
    ),
    "lab/controls/socket_probe.py": (
        "tools/friend_lab/controls/socket_probe.py"
    ),
}
_EXECUTABLE_MEMBERS = frozenset(
    {
        "verifier/verify_handoff_archive.py",
        "lab/acceptance_runner.py",
        "lab/controls/write_outside_probe.py",
        "lab/controls/socket_probe.py",
    }
)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_TAG = re.compile(r"[A-Za-z0-9_.-]+\Z")
_SAFE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")
_PYTHON_MINOR = re.compile(r"3\.[0-9]{1,2}\Z")


class BuildError(RuntimeError):
    """A closed build invariant was not satisfied."""


@dataclass(frozen=True)
class TargetTuple:
    os_version: str
    architecture: str
    python_minor: str
    abi_tag: str
    platform_tags: tuple[str, ...]
    pip_version: str


@dataclass(frozen=True)
class BuiltArtifacts:
    pack_path: Path
    detached_verifier_path: Path
    pack_sha256: str
    source_sha256: str
    verifier_sha256: str
    public_revision: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _run_git(public_repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=public_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BuildError(f"git command failed: {arguments[0]}") from exc
    return result.stdout.strip()


def _public_revision(public_repo: Path) -> str:
    revision = _run_git(public_repo, "rev-parse", "--verify", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise BuildError("public revision is not a full commit id")
    return revision


def _require_clean_public_repo(public_repo: Path) -> str:
    if not public_repo.is_dir() or public_repo.is_symlink():
        raise BuildError("public repo must be a nonsymlink directory")
    if _run_git(public_repo, "status", "--porcelain", "--untracked-files=all"):
        raise BuildError("public tree is dirty")
    pyproject = _read_regular(public_repo / "pyproject.toml")
    match = re.search(
        rb"(?m)^version\s*=\s*\"([^\"]+)\"\s*$", pyproject
    )
    if match is None or match.group(1).decode("ascii", errors="replace") != (
        PACKAGE_VERSION
    ):
        raise BuildError(f"package version must be {PACKAGE_VERSION}")
    return _public_revision(public_repo)


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise BuildError(f"required regular file missing: {path.name}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BuildError(f"required file unreadable: {path.name}") from exc


def _run_git_archive(
    public_repo: Path, destination: Path, revision: str
) -> bytes:
    if destination.exists() or destination.is_symlink():
        raise BuildError("archive destination already exists")
    try:
        subprocess.run(
            (
                "git",
                "archive",
                "--format=tar.gz",
                f"--prefix={SOURCE_ROOT}/",
                f"--output={destination}",
                revision,
            ),
            cwd=public_repo,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BuildError("git archive failed") from exc
    return _read_regular(destination)


def _archive_records(data: bytes, expected_root: str) -> tuple[MemberRecord, ...]:
    records: list[MemberRecord] = []
    roots: set[str] = set()
    seen: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for item in archive.getmembers():
                path = PurePosixPath(item.name)
                if (
                    not path.parts
                    or item.name.startswith("/")
                    or "\\" in item.name
                    or any(part in {"", ".", ".."} for part in path.parts)
                ):
                    raise BuildError("unsafe source archive member")
                roots.add(path.parts[0])
                if item.name in seen:
                    raise BuildError("duplicate source archive member")
                seen.add(item.name)
                if item.isdir():
                    continue
                if not item.isfile():
                    raise BuildError("forbidden source archive member type")
                if path.parts[0] != expected_root or len(path.parts) < 2:
                    raise BuildError("source archive root mismatch")
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                extracted = archive.extractfile(item)
                if extracted is None:
                    raise BuildError("source archive member unreadable")
                payload = extracted.read()
                records.append(
                    MemberRecord(
                        path=relative,
                        mode=item.mode & 0o777,
                        size=len(payload),
                        sha256=_sha256(payload),
                    )
                )
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        raise BuildError("source archive unreadable") from exc
    if roots != {expected_root}:
        raise BuildError("source archive root mismatch")
    return tuple(sorted(records, key=lambda item: item.path))


def build_source_archive(
    public_repo: Path, destination: Path
) -> tuple[bytes, tuple[MemberRecord, ...]]:
    """Build the same Git source archive twice and retain verified bytes."""

    public_repo = public_repo.resolve()
    revision = _require_clean_public_repo(public_repo)
    if destination.exists() or destination.is_symlink():
        raise BuildError("source destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".friend-source-", dir=destination.parent
    ) as temporary:
        temporary_root = Path(temporary)
        first = _run_git_archive(
            public_repo, temporary_root / "first.tar.gz", revision
        )
        second = _run_git_archive(
            public_repo, temporary_root / "second.tar.gz", revision
        )
    if first != second:
        raise BuildError("source archives differ")
    if len(first) < 10 or first[:3] != b"\x1f\x8b\x08":
        raise BuildError("source archive is not gzip")
    if first[4:8] != b"\x00\x00\x00\x00":
        raise BuildError("source gzip MTIME must be zero")
    records = _archive_records(first, SOURCE_ROOT)
    result = verify_source_archive_bytes(
        first,
        expected_sha256=_sha256(first),
        expected_regular_file_count=len(records),
        expected_members=records,
    )
    if not result.ok:
        raise BuildError("source verification failed: " + "; ".join(result.errors))
    destination.write_bytes(first)
    return first, records


def _normalize_distribution(name: str) -> str:
    normalized = re.sub(r"[-_.]+", "-", name).lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", normalized):
        raise BuildError("invalid wheel distribution name")
    return normalized


def _split_wheel_filename(path: Path) -> tuple[str, str, list[str], list[str], list[str]]:
    if path.suffix != ".whl":
        raise BuildError("only wheel files are allowed")
    parts = path.name[:-4].split("-")
    if len(parts) not in {5, 6}:
        raise BuildError(f"invalid wheel filename: {path.name}")
    distribution, version = parts[0], parts[1]
    python_tag, abi_tag, platform_tag = parts[-3:]
    if not _SAFE_VERSION.fullmatch(version):
        raise BuildError(f"invalid wheel version: {path.name}")
    tag_groups = [python_tag.split("."), abi_tag.split("."), platform_tag.split(".")]
    if any(
        not values or any(not _SAFE_TAG.fullmatch(value) for value in values)
        for values in tag_groups
    ):
        raise BuildError(f"invalid wheel tag: {path.name}")
    return (
        _normalize_distribution(distribution),
        version,
        sorted(set(tag_groups[0])),
        sorted(set(tag_groups[1])),
        sorted(set(tag_groups[2])),
    )


def _safe_zip_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and not name.startswith("/")
        and "\\" not in name
        and path.parts
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _parse_wheel(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise BuildError(f"wheel must be a regular file: {path.name}")
    name, version, python_tags, abi_tags, platform_tags = _split_wheel_filename(
        path
    )
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or not all(
                _safe_zip_name(item) for item in names
            ):
                raise BuildError(f"unsafe wheel contents: {path.name}")
            dist_root = f"{name.replace('-', '_')}-{version}.dist-info/"
            metadata_names = [item for item in names if item == dist_root + "METADATA"]
            wheel_names = [item for item in names if item == dist_root + "WHEEL"]
            record_names = [item for item in names if item == dist_root + "RECORD"]
            if not (
                len(metadata_names) == len(wheel_names) == len(record_names) == 1
            ):
                raise BuildError(f"wheel metadata incomplete: {path.name}")
            roots = {
                PurePosixPath(item).parts[0]
                for item in (*metadata_names, *wheel_names, *record_names)
            }
            if len(roots) != 1:
                raise BuildError(f"wheel dist-info mismatch: {path.name}")
            message = BytesParser(policy=policy.default).parsebytes(
                archive.read(metadata_names[0])
            )
            wheel_message = BytesParser(policy=policy.default).parsebytes(
                archive.read(wheel_names[0])
            )
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        if isinstance(exc, BuildError):
            raise
        raise BuildError(f"wheel unreadable: {path.name}") from exc
    metadata_name = message.get("Name")
    metadata_version = message.get("Version")
    if (
        metadata_name is None
        or _normalize_distribution(str(metadata_name)) != name
        or metadata_version != version
    ):
        raise BuildError(f"wheel filename/metadata mismatch: {path.name}")
    wheel_header_tags = sorted(set(str(item) for item in wheel_message.get_all("Tag", [])))
    expected_tag_products = {
        f"{python_tag}-{abi_tag}-{platform_tag}"
        for python_tag in python_tags
        for abi_tag in abi_tags
        for platform_tag in platform_tags
    }
    if set(wheel_header_tags) != expected_tag_products:
        raise BuildError(f"wheel filename/header tag mismatch: {path.name}")
    license_fields: list[str] = []
    for field in ("License", "License-Expression", "License-File"):
        license_fields.extend(
            f"{field}: {value}" for value in message.get_all(field, [])
        )
    requires_dist = sorted(set(str(item) for item in message.get_all("Requires-Dist", [])))
    data = path.read_bytes()
    return {
        "name": name,
        "version": version,
        "filename": path.name,
        "size": len(data),
        "sha256": _sha256(data),
        "python_tags": python_tags,
        "abi_tags": abi_tags,
        "platform_tags": platform_tags,
        "license_fields": sorted(set(license_fields)),
        "requires_dist": requires_dist,
    }


def _agent_wheel_payloads(path: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise BuildError("agent wheel contains duplicate members")
            for item in infos:
                name = item.filename
                if not _safe_zip_name(name):
                    raise BuildError("agent wheel contains unsafe member")
                if item.is_dir():
                    continue
                relative = PurePosixPath(name)
                parts = relative.parts
                if not parts or (parts[0] != "frontdoor" and not (
                    len(parts) == 2
                    and parts[0].startswith("agent_frontdoor-")
                    and parts[0].endswith(".dist-info")
                    and parts[1] in {"METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt"}
                )):
                    raise BuildError("agent wheel contains unexpected member")
                if relative.suffix.lower() in {".so", ".dylib", ".dll", ".pyd"}:
                    raise BuildError("agent wheel contains native member")
                data = archive.read(item)
                if scan_forbidden_text(relative, data):
                    raise BuildError("agent wheel privacy validation failed")
                if parts[-1] == "METADATA":
                    message = BytesParser(policy=policy.default).parsebytes(data)
                    requires = sorted(str(value).strip() for value in message.get_all("Requires-Dist", []))
                    if requires != ["jsonschema>=4"]:
                        raise BuildError("agent wheel dependency metadata mismatch")
                if parts[-1] == "RECORD":
                    for line in data.decode("utf-8").splitlines():
                        member = line.split(",", 1)[0]
                        if not _safe_zip_name(member):
                            raise BuildError("agent wheel RECORD path invalid")
                if parts[-1] == "entry_points.txt" and data != b"[console_scripts]\nagent-frontdoor = frontdoor.cli:main\n":
                    raise BuildError("agent wheel entry point mismatch")
                if name.startswith("frontdoor/"):
                    payloads[name] = data
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        if isinstance(exc, BuildError):
            raise
        raise BuildError("agent wheel package unreadable") from exc
    if not payloads:
        raise BuildError("agent wheel package is empty")
    return payloads


def _source_package_payloads(source_data: bytes) -> dict[str, bytes]:
    prefix = f"{SOURCE_ROOT}/src/frontdoor/"
    payloads: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(source_data), mode="r:gz") as archive:
            for item in archive.getmembers():
                if not item.isfile() or not item.name.startswith(prefix):
                    continue
                extracted = archive.extractfile(item)
                if extracted is None:
                    raise BuildError("source package member unreadable")
                relative = item.name[len(prefix) :]
                payloads[f"frontdoor/{relative}"] = extracted.read()
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        if isinstance(exc, BuildError):
            raise
        raise BuildError("source package unreadable") from exc
    if not payloads:
        raise BuildError("source package is empty")
    return payloads


def _validate_agent_wheel_source_binding(
    wheelhouse: Path,
    wheel_manifest: dict[str, object],
    source_data: bytes,
) -> None:
    wheels = wheel_manifest.get("wheels")
    if not isinstance(wheels, list):
        raise BuildError("wheelhouse manifest invalid")
    agent_records = [
        item for item in wheels
        if isinstance(item, dict) and item.get("name") == "agent-frontdoor"
    ]
    if len(agent_records) != 1:
        raise BuildError("agent wheel record invalid")
    filename = agent_records[0].get("filename")
    if not isinstance(filename, str) or PurePosixPath(filename).name != filename:
        raise BuildError("agent wheel record invalid")
    wheel_payloads = _agent_wheel_payloads(wheelhouse / filename)
    if wheel_payloads != _source_package_payloads(source_data):
        raise BuildError("agent wheel source binding mismatch")


def _target_dict(target: TargetTuple) -> dict[str, object]:
    _validate_target(target)
    value = asdict(target)
    value["platform_tags"] = list(target.platform_tags)
    return value


def _validate_target(target: TargetTuple) -> None:
    if (
        not isinstance(target.os_version, str)
        or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,63}", target.os_version
        )
        or not _SAFE_TAG.fullmatch(target.architecture)
        or not _PYTHON_MINOR.fullmatch(target.python_minor)
        or not _SAFE_TAG.fullmatch(target.abi_tag)
        or not target.platform_tags
        or len(target.platform_tags) != len(set(target.platform_tags))
        or any(not _SAFE_TAG.fullmatch(tag) for tag in target.platform_tags)
        or not _SAFE_VERSION.fullmatch(target.pip_version)
    ):
        raise BuildError("target tuple invalid")


def _validate_backend_lock(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "name",
        "version",
        "filename",
        "sha256",
    }:
        raise BuildError("build backend lock invalid")
    if (
        value.get("name") != "setuptools"
        or not isinstance(value.get("version"), str)
        or not _SAFE_VERSION.fullmatch(str(value["version"]))
        or not isinstance(value.get("filename"), str)
        or not re.fullmatch(r"setuptools-[^/\s]+\.whl", str(value["filename"]))
        or not isinstance(value.get("sha256"), str)
        or not _HEX64.fullmatch(str(value["sha256"]))
    ):
        raise BuildError("build backend lock invalid")


def _load_lock(path: Path) -> dict[str, object]:
    try:
        value = json.loads(_read_regular(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BuildError("wheelhouse lock invalid") from exc
    if not isinstance(value, dict):
        raise BuildError("wheelhouse lock invalid")
    _validate_backend_lock(value.get("build_backend"))
    wheels = value.get("wheels")
    if not isinstance(wheels, list) or not wheels:
        raise BuildError("wheelhouse lock invalid")
    return value


def freeze_wheelhouse(
    wheelhouse: Path, target: TargetTuple
) -> dict[str, object]:
    """Freeze wheels or verify them against an existing exact lock manifest."""

    _validate_target(target)
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise BuildError("wheelhouse must be a nonsymlink directory")
    entries = sorted(wheelhouse.iterdir(), key=lambda item: item.name)
    for entry in entries:
        if entry.name == LOCK_FILENAME:
            if entry.is_symlink() or not entry.is_file():
                raise BuildError("wheelhouse lock must be a regular file")
            continue
        if entry.suffix != ".whl":
            raise BuildError("only wheel files are allowed")
        if entry.is_symlink() or not entry.is_file():
            raise BuildError("wheel must be a regular file")
    wheel_paths = [entry for entry in entries if entry.suffix == ".whl"]
    records = [_parse_wheel(path) for path in wheel_paths]
    records.sort(key=lambda item: (str(item["name"]), str(item["filename"])))
    names = [str(item["name"]) for item in records]
    if len(names) != len(set(names)):
        raise BuildError("duplicate wheel distribution")
    missing = sorted(_REQUIRED_DISTRIBUTIONS - set(names))
    if missing:
        raise BuildError("missing required distributions: " + ", ".join(missing))
    by_name = {str(item["name"]): item for item in records}
    if by_name["agent-frontdoor"]["version"] != PACKAGE_VERSION:
        raise BuildError(f"agent-frontdoor version must be {PACKAGE_VERSION}")
    rpds = by_name["rpds-py"]
    expected_python_tag = "cp" + target.python_minor.replace(".", "")
    if (
        expected_python_tag not in rpds["python_tags"]
        or target.abi_tag not in rpds["abi_tags"]
        or not set(target.platform_tags).intersection(rpds["platform_tags"])
    ):
        raise BuildError("rpds-py target mismatch")
    setuptools = by_name["setuptools"]
    backend = {
        "name": "setuptools",
        "version": setuptools["version"],
        "filename": setuptools["filename"],
        "sha256": setuptools["sha256"],
    }
    manifest: dict[str, object] = {
        "schema_version": "wheelhouse-manifest.v1",
        "package_version": PACKAGE_VERSION,
        "target": _target_dict(target),
        "wheels": records,
        "build_backend": backend,
    }
    lock_path = wheelhouse / LOCK_FILENAME
    if lock_path.exists() or lock_path.is_symlink():
        locked = _load_lock(lock_path)
        locked_wheels = locked.get("wheels")
        locked_filenames = {
            str(item.get("filename"))
            for item in locked_wheels
            if isinstance(item, dict)
        }
        actual_filenames = {path.name for path in wheel_paths}
        if locked_filenames != actual_filenames:
            raise BuildError("wheelhouse lock file set mismatch")
        if locked != manifest:
            raise BuildError("wheelhouse lock mismatch")
    return manifest


def _load_target(path: Path) -> TargetTuple:
    try:
        value = json.loads(_read_regular(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BuildError("target JSON invalid") from exc
    if not isinstance(value, dict) or set(value) != _TARGET_FIELDS:
        raise BuildError("target JSON invalid")
    platform_tags = value.get("platform_tags")
    if not isinstance(platform_tags, list) or any(
        not isinstance(item, str) for item in platform_tags
    ):
        raise BuildError("target JSON invalid")
    scalar_fields = _TARGET_FIELDS - {"platform_tags"}
    if any(not isinstance(value.get(field), str) for field in scalar_fields):
        raise BuildError("target JSON invalid")
    target = TargetTuple(
        os_version=value["os_version"],
        architecture=value["architecture"],
        python_minor=value["python_minor"],
        abi_tag=value["abi_tag"],
        platform_tags=tuple(platform_tags),
        pip_version=value["pip_version"],
    )
    _validate_target(target)
    return target


def _member_mode(path: str) -> int:
    return 0o755 if path in _EXECUTABLE_MEMBERS else 0o644


def _records_for_payloads(
    payloads: Mapping[str, bytes],
) -> tuple[MemberRecord, ...]:
    return tuple(
        MemberRecord(
            path=path,
            mode=_member_mode(path),
            size=len(payloads[path]),
            sha256=_sha256(payloads[path]),
        )
        for path in sorted(payloads)
    )


def _records_json(records: Iterable[MemberRecord]) -> list[dict[str, object]]:
    return [
        {
            "path": item.path,
            "mode": item.mode,
            "size": item.size,
            "sha256": item.sha256,
        }
        for item in records
    ]


def _privacy_control() -> bytes:
    return (
        "absolute-user-path=/Users/synthetic-receiver/private.txt\n"
        "account=synthetic-private-host\n"
        "ip-address=192.0.2.44\n"
        "password=synthetic-secret-token\n"
        "SYNTHETIC_API_KEY=synthetic-environment-value\n"
        "private-operational-record=memory/active_next.md\n"
    ).encode("utf-8")


def _build_outer_archive(payloads: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, mtime=0, compresslevel=9
    ) as compressed:
        with tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT
        ) as archive:
            for relative in sorted(payloads):
                path = f"{PACK_ROOT}/{relative}"
                data = payloads[relative]
                info = tarfile.TarInfo(path)
                info.size = len(data)
                info.mode = _member_mode(relative)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _public_pack_payloads(public_repo: Path) -> dict[str, bytes]:
    return {
        destination: _read_regular(public_repo / source)
        for destination, source in _PUBLIC_PACK_FILES.items()
    }


def _verify_built_pack(
    pack_data: bytes,
    verifier_data: bytes,
    *,
    source_sha256: str,
    directory: Path,
    label: str,
) -> None:
    pack_path = directory / f"{label}.tar.gz"
    verifier_path = directory / f"{label}-verifier.py"
    pack_path.write_bytes(pack_data)
    verifier_path.write_bytes(verifier_data)
    result = verify_friend_pack(
        pack_path,
        detached_verifier_path=verifier_path,
        expected_pack_sha256=_sha256(pack_data),
        expected_source_sha256=source_sha256,
        expected_verifier_sha256=_sha256(verifier_data),
    )
    if not result.ok:
        raise BuildError("friend pack verification failed: " + "; ".join(result.errors))


def build_friend_pack(
    public_repo: Path,
    wheelhouse: Path,
    target_json: Path,
    output_dir: Path,
) -> BuiltArtifacts:
    """Build two identical packs, self-verify both, and emit two transfer files."""

    public_repo = public_repo.resolve()
    revision = _require_clean_public_repo(public_repo)
    if output_dir.is_symlink():
        raise BuildError("output directory must not be a symlink")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise BuildError("output path must be a directory")
        if any(output_dir.iterdir()):
            raise BuildError("output directory is not empty")
    else:
        output_dir.mkdir(parents=True)

    target = _load_target(target_json)
    wheel_manifest = freeze_wheelhouse(wheelhouse, target)
    with tempfile.TemporaryDirectory(
        prefix=".friend-pack-", dir=output_dir.parent
    ) as temporary:
        temporary_root = Path(temporary)
        source_data, source_records = build_source_archive(
            public_repo, temporary_root / "source.tar.gz"
        )
        _validate_agent_wheel_source_binding(
            wheelhouse, wheel_manifest, source_data
        )
        if _public_revision(public_repo) != revision:
            raise BuildError("public revision changed during build")
        source_sha = _sha256(source_data)
        source_manifest = {
            "schema_version": "source-archive-manifest.v1",
            "package_version": PACKAGE_VERSION,
            "public_revision": revision,
            "archive_root": SOURCE_ROOT,
            "regular_file_count": len(source_records),
            "members": _records_json(source_records),
        }
        payloads = _public_pack_payloads(public_repo)
        verifier_data = payloads["verifier/verify_handoff_archive.py"]
        payloads.update(
            {
                f"source/{SOURCE_ROOT}.tar.gz": source_data,
                f"source/{SOURCE_ROOT}.tar.gz.sha256": (
                    source_sha + "\n"
                ).encode("ascii"),
                "source/source-manifest.json": _canonical_json(source_manifest),
                "wheelhouse/wheelhouse-manifest.json": _canonical_json(
                    wheel_manifest
                ),
                "lab/controls/privacy_control.txt": _privacy_control(),
            }
        )
        for wheel in wheel_manifest["wheels"]:
            filename = str(wheel["filename"])
            payloads[f"wheelhouse/{filename}"] = _read_regular(
                wheelhouse / filename
            )
        records = _records_for_payloads(payloads)
        control_path = "lab/controls/privacy_control.txt"
        manifest = {
            "schema_version": "friend-pack-manifest.v1",
            "package_version": PACKAGE_VERSION,
            "public_revision": revision,
            "source_archive": {
                "path": f"source/{SOURCE_ROOT}.tar.gz",
                "sha256": source_sha,
                "regular_file_count": len(source_records),
                "manifest_path": "source/source-manifest.json",
            },
            "verifier": {
                "path": "verifier/verify_handoff_archive.py",
                "sha256": _sha256(verifier_data),
            },
            "privacy_control": {
                "path": control_path,
                "sha256": _sha256(payloads[control_path]),
            },
            "self_exclusions": ["manifest.json", "manifest.sha256"],
            "members": _records_json(records),
        }
        manifest_data = _canonical_json(manifest)
        payloads["manifest.json"] = manifest_data
        payloads["manifest.sha256"] = (
            _sha256(manifest_data) + "\n"
        ).encode("ascii")
        first = _build_outer_archive(payloads)
        second = _build_outer_archive(payloads)
        if first != second:
            raise BuildError("friend packs differ")
        if len(first) < 10 or first[4:8] != b"\x00\x00\x00\x00":
            raise BuildError("friend pack gzip MTIME must be zero")
        _verify_built_pack(
            first,
            verifier_data,
            source_sha256=source_sha,
            directory=temporary_root,
            label="first",
        )
        _verify_built_pack(
            second,
            verifier_data,
            source_sha256=source_sha,
            directory=temporary_root,
            label="second",
        )

    pack_path = output_dir / PACK_FILENAME
    detached_verifier_path = output_dir / DETACHED_VERIFIER_FILENAME
    pack_path.write_bytes(first)
    detached_verifier_path.write_bytes(verifier_data)
    pack_path.chmod(0o644)
    detached_verifier_path.chmod(0o755)
    if {
        path.name for path in output_dir.iterdir() if path.is_file()
    } != {PACK_FILENAME, DETACHED_VERIFIER_FILENAME} or any(
        path.is_symlink() or not path.is_file() for path in output_dir.iterdir()
    ):
        raise BuildError("transfer output must contain exactly two regular files")
    return BuiltArtifacts(
        pack_path=pack_path,
        detached_verifier_path=detached_verifier_path,
        pack_sha256=_sha256(first),
        source_sha256=source_sha,
        verifier_sha256=_sha256(verifier_data),
        public_revision=revision,
    )
