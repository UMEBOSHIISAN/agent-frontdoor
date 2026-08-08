#!/usr/bin/env python3
"""Human-attended, fail-closed Agent Frontdoor friend-lab acceptance."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Literal, Mapping, Protocol, Sequence
import zipfile

try:
    from tools.verify_handoff_archive import (
        PRIVACY_CATEGORIES,
        scan_forbidden_text,
        verify_friend_pack,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"tools", "tools.verify_handoff_archive"}:
        raise
    verifier_directory = Path(__file__).resolve().parents[1] / "verifier"
    sys.path.insert(0, str(verifier_directory))
    from verify_handoff_archive import (  # type: ignore[no-redef]
        PRIVACY_CATEGORIES,
        scan_forbidden_text,
        verify_friend_pack,
    )


PACKAGE_VERSION = "0.2.0"
PACK_ROOT_NAME = f"agent-frontdoor-friend-pack-{PACKAGE_VERSION}"
SOURCE_ROOT_NAME = f"agent-frontdoor-{PACKAGE_VERSION}"
RECEIPT_NAME = "friend-acceptance-receipt.json"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,95}\Z")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_REQUIRED_WHEEL_DISTRIBUTIONS = frozenset(
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
_OPTIONAL_ADAPTER_TEST_IGNORES = (
    "--ignore=tests/test_hook_adapter.py",
    "--ignore=tests/test_hook_fixtures.py",
    "--ignore=tests/test_hook_state.py",
)
_GAP_ORDER = (
    "REMOTE_EXECUTION",
    "NETWORK_DISCONNECT_UNCONFIRMED",
    "DIGEST_MISMATCH",
    "CONTROL_FAILURE",
    "PHASE_FAILURE",
    "PYTHON_FLOOR_UNVERIFIED",
    "INCOMPLETE_EVIDENCE",
    "NATIVE_COMPATIBILITY_GAP",
)
_ALLOWED_RUN_ROOT_ENTRIES = frozenset(
    {
        "audit-ledger.jsonl",
        "environment",
        "evidence",
        "friend-acceptance-receipt.json",
        "source",
        "source-venv",
        "wheel-venv",
    }
)


class AcceptanceError(RuntimeError):
    """An acceptance invariant was not satisfied."""


@dataclass(frozen=True)
class CommandResult:
    command_class: str
    exit_status: int
    stdout_sha256: str
    stderr_sha256: str
    timed_out: bool


@dataclass(frozen=True)
class AcceptanceRequest:
    pack_path: Path
    detached_verifier_path: Path
    pack_root: Path
    run_root: Path
    expected_pack_sha256: str
    expected_source_sha256: str
    expected_verifier_sha256: str
    execution_mode: Literal["local", "remote"]
    verifier_role: Literal[
        "receiver-human", "receiver-agent", "independent-reviewer"
    ]
    network_disconnected_confirmed: bool


class CommandRunner(Protocol):
    def run(
        self,
        command_class: str,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: float,
        output_budget_bytes: int,
    ) -> CommandResult: ...


class BoundedCommandRunner:
    """Run one process group once while draining two bounded output streams."""

    def __init__(self, run_root: Path, *, terminate_grace_seconds: float = 0.5):
        self._evidence = run_root / "evidence"
        self._evidence.mkdir(parents=True, exist_ok=True)
        self._grace = terminate_grace_seconds
        self._sequence = 0
        self._stdout_by_class: dict[str, bytes] = {}

    def stdout_bytes(self, command_class: str) -> bytes:
        return self._stdout_by_class.get(command_class, b"")

    @staticmethod
    def _safe_exit_status(returncode: int | None) -> int:
        if returncode is None or returncode < 0 or returncode > 255:
            return -1
        return returncode

    def _stop_group(self, process: subprocess.Popen[bytes]) -> None:
        process_group = process.pid
        try:
            os.killpg(process_group, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return

        deadline = time.monotonic() + self._grace
        while time.monotonic() < deadline:
            try:
                os.killpg(process_group, 0)
            except (ProcessLookupError, PermissionError):
                break
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        else:
            try:
                os.killpg(process_group, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

        try:
            process.wait(timeout=max(self._grace, 0.1))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def run(
        self,
        command_class: str,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: float,
        output_budget_bytes: int,
    ) -> CommandResult:
        if not _SAFE_LABEL.fullmatch(command_class):
            raise AcceptanceError("command class invalid")
        if timeout_seconds <= 0 or output_budget_bytes <= 0:
            raise AcceptanceError("command bounds must be positive")
        self._sequence += 1
        prefix = f"{self._sequence:03d}-{command_class}"
        stdout_path = self._evidence / f"{prefix}.stdout"
        stderr_path = self._evidence / f"{prefix}.stderr"
        deadline = time.monotonic() + timeout_seconds
        timed_out = False
        output_capped = False
        group_stopped = False
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        streams: dict[int, tuple[str, object]] = {}
        selector = selectors.DefaultSelector()
        try:
            process = subprocess.Popen(
                tuple(argv),
                cwd=cwd,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            error = f"process start failed: {type(exc).__name__}\n".encode("ascii")
            stdout_path.write_bytes(b"")
            stderr_path.write_bytes(error)
            self._stdout_by_class[command_class] = b""
            return CommandResult(
                command_class=command_class,
                exit_status=127,
                stdout_sha256=_EMPTY_SHA256,
                stderr_sha256=hashlib.sha256(error).hexdigest(),
                timed_out=False,
            )
        assert process.stdout is not None
        assert process.stderr is not None
        for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
            streams[stream.fileno()] = (label, stream)
        try:
            while streams:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    if not group_stopped:
                        self._stop_group(process)
                        group_stopped = True
                events = selector.select(max(0.0, min(remaining, 0.1)))
                for key, _mask in events:
                    stream = key.fileobj
                    label, _registered = streams[stream.fileno()]
                    try:
                        chunk = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        streams.pop(stream.fileno(), None)
                        continue
                    room = output_budget_bytes - len(buffers[label])
                    if len(chunk) > room:
                        buffers[label].extend(chunk[: max(0, room)])
                        output_capped = True
                        if not group_stopped:
                            self._stop_group(process)
                            group_stopped = True
                    else:
                        buffers[label].extend(chunk)
                if process.poll() is not None and not events:
                    for _fd, (_label, stream) in tuple(streams.items()):
                        try:
                            chunk = os.read(stream.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if chunk:
                            room = output_budget_bytes - len(buffers[_label])
                            buffers[_label].extend(chunk[: max(0, room)])
                            output_capped = output_capped or len(chunk) > room
                        else:
                            selector.unregister(stream)
                            streams.pop(stream.fileno(), None)
                if timed_out or output_capped:
                    if not group_stopped:
                        self._stop_group(process)
                        group_stopped = True
            process.wait()
        finally:
            selector.close()
            process.stdout.close()
            process.stderr.close()
        stdout = bytes(buffers["stdout"])
        stderr = bytes(buffers["stderr"])
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        self._stdout_by_class[command_class] = stdout
        return CommandResult(
            command_class=command_class,
            exit_status=(
                -1
                if timed_out or output_capped
                else self._safe_exit_status(process.returncode)
            ),
            stdout_sha256=hashlib.sha256(stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(stderr).hexdigest(),
            timed_out=timed_out,
        )


@dataclass(frozen=True)
class _PackContext:
    manifest: dict[str, object]
    source_manifest: dict[str, object]
    wheel_manifest: dict[str, object]
    source_path: Path
    source_sha256: str
    source_manifest_sha256: str
    verifier_sha256: str
    public_revision: str
    platform: dict[str, str]
    agent_wheel: str
    agent_package_payloads: dict[str, bytes]
    setuptools_version: str
    wheel_version: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise AcceptanceError(f"required regular file missing: {path.name}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AcceptanceError(f"required file unreadable: {path.name}") from exc


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(_read_regular(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AcceptanceError(f"JSON invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise AcceptanceError(f"JSON object required: {path.name}")
    return value


def _safe_relative(value: object) -> str:
    if not isinstance(value, str):
        raise AcceptanceError("manifest path invalid")
    path = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise AcceptanceError("manifest path invalid")
    return value


def _actual_pack_files(pack_root: Path) -> dict[str, Path]:
    if (
        pack_root.name != PACK_ROOT_NAME
        or pack_root.is_symlink()
        or not pack_root.is_dir()
    ):
        raise AcceptanceError("pack root invalid")
    actual: dict[str, Path] = {}
    for path in pack_root.rglob("*"):
        if path.is_symlink():
            raise AcceptanceError("pack root contains symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise AcceptanceError("pack root contains non-regular file")
        relative = path.relative_to(pack_root).as_posix()
        actual[relative] = path
    return actual


def _safe_zip_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and not name.startswith("/")
        and "\\" not in name
        and path.parts
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _agent_wheel_payloads(path: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    wheel_stem = path.name.removesuffix(".whl")
    wheel_parts = wheel_stem.split("-")
    if len(wheel_parts) < 2:
        raise AcceptanceError("agent wheel filename invalid")
    expected_dist = f"{wheel_parts[0]}-{wheel_parts[1]}.dist-info"
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or not all(
                _safe_zip_name(name) for name in names
            ):
                raise AcceptanceError("agent wheel contents invalid")
            for item in infos:
                name = item.filename
                if item.is_dir():
                    continue
                relative = PurePosixPath(name)
                parts = relative.parts
                if not parts or (parts[0] != "frontdoor" and not (
                    (len(parts) == 2
                    and parts[0] == expected_dist
                    and parts[1] in {"METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt"})
                    or (len(parts) == 3 and parts[0] == expected_dist and parts[1] == "licenses" and parts[2] == "LICENSE")
                )):
                    raise AcceptanceError("agent wheel contains unexpected member")
                if relative.suffix.lower() in {".so", ".dylib", ".dll", ".pyd"}:
                    raise AcceptanceError("agent wheel native member forbidden")
                data = archive.read(item)
                if scan_forbidden_text(relative, data):
                    raise AcceptanceError("agent wheel privacy validation failed")
                if parts[-1] == "METADATA":
                    message = BytesParser(policy=policy.default).parsebytes(data)
                    requires = sorted(str(value).strip() for value in message.get_all("Requires-Dist", []))
                    if requires not in (["jsonschema>=4"], ["jsonschema>=4", 'pytest; extra == "test"']):
                        raise AcceptanceError("agent wheel dependency metadata mismatch")
                if parts[-1] == "RECORD":
                    for line in data.decode("utf-8").splitlines():
                        member = line.split(",", 1)[0]
                        if not _safe_zip_name(member):
                            raise AcceptanceError("agent wheel RECORD path invalid")
                if parts[-1] == "entry_points.txt" and data != b"[console_scripts]\nagent-frontdoor = frontdoor.cli:main\n":
                    raise AcceptanceError("agent wheel entry point mismatch")
                if name.startswith("frontdoor/"):
                    payloads[name] = data
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        if isinstance(exc, AcceptanceError):
            raise
        raise AcceptanceError("agent wheel unreadable") from exc
    if not payloads:
        raise AcceptanceError("agent wheel package empty")
    return payloads


def _source_package_payloads(source_path: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    prefix = f"{SOURCE_ROOT_NAME}/src/frontdoor/"
    try:
        with tarfile.open(
            fileobj=io.BytesIO(_read_regular(source_path)), mode="r:gz"
        ) as archive:
            for member in archive.getmembers():
                if not member.isfile() or not member.name.startswith(prefix):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise AcceptanceError("source package member unreadable")
                relative = member.name[len(prefix) :]
                payloads[f"frontdoor/{relative}"] = extracted.read()
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        if isinstance(exc, AcceptanceError):
            raise
        raise AcceptanceError("source package unreadable") from exc
    if not payloads:
        raise AcceptanceError("source package empty")
    return payloads


def _validate_wheelhouse(
    pack_root: Path,
    wheel_manifest: dict[str, object],
) -> tuple[dict[str, object], str, dict[str, bytes], str, str]:
    target = wheel_manifest.get("target")
    wheels = wheel_manifest.get("wheels")
    backend = wheel_manifest.get("build_backend")
    if not isinstance(target, dict) or not isinstance(wheels, list) or not isinstance(
        backend, dict
    ):
        raise AcceptanceError("wheelhouse manifest invalid")
    target_fields = {
        "os_version",
        "architecture",
        "python_minor",
        "abi_tag",
        "platform_tags",
        "pip_version",
    }
    if set(target) != target_fields or any(
        not isinstance(target.get(field), str)
        for field in target_fields - {"platform_tags"}
    ):
        raise AcceptanceError("wheelhouse target invalid")
    platform_tags = target.get("platform_tags")
    if (
        not isinstance(platform_tags, list)
        or not platform_tags
        or any(not isinstance(item, str) for item in platform_tags)
    ):
        raise AcceptanceError("wheelhouse target invalid")
    if (
        re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,63}",
            str(target["os_version"]),
        )
        is None
        or _SAFE_LABEL.fullmatch(str(target["architecture"])) is None
        or re.fullmatch(r"3\.[0-9]{1,2}", str(target["python_minor"])) is None
        or _SAFE_LABEL.fullmatch(str(target["abi_tag"])) is None
        or _SAFE_LABEL.fullmatch(str(target["pip_version"])) is None
        or len(platform_tags) != len(set(platform_tags))
        or any(_SAFE_LABEL.fullmatch(item) is None for item in platform_tags)
    ):
        raise AcceptanceError("wheelhouse target invalid")
    required_record_fields = {
        "name",
        "version",
        "filename",
        "size",
        "sha256",
        "python_tags",
        "abi_tags",
        "platform_tags",
        "license_fields",
        "requires_dist",
    }
    by_name: dict[str, dict[str, object]] = {}
    filenames: set[str] = set()
    for item in wheels:
        if not isinstance(item, dict) or set(item) != required_record_fields:
            raise AcceptanceError("wheel record invalid")
        name = item.get("name")
        filename = item.get("filename")
        digest = item.get("sha256")
        size = item.get("size")
        if (
            not isinstance(name, str)
            or name in by_name
            or not isinstance(filename, str)
            or PurePosixPath(filename).name != filename
            or not filename.endswith(".whl")
            or filename in filenames
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or not isinstance(digest, str)
            or not _HEX64.fullmatch(digest)
        ):
            raise AcceptanceError("wheel record invalid")
        data = _read_regular(pack_root / "wheelhouse" / filename)
        if len(data) != size or _sha256(data) != digest:
            raise AcceptanceError("wheel record hash mismatch")
        for field in (
            "python_tags",
            "abi_tags",
            "platform_tags",
            "license_fields",
            "requires_dist",
        ):
            values = item.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) for value in values
            ):
                raise AcceptanceError("wheel record invalid")
        by_name[name] = item
        filenames.add(filename)
    missing = _REQUIRED_WHEEL_DISTRIBUTIONS - set(by_name)
    if missing:
        raise AcceptanceError("wheelhouse closure incomplete")
    directory_files = {
        path.name
        for path in (pack_root / "wheelhouse").iterdir()
        if path.is_file() and not path.is_symlink()
    }
    if directory_files != filenames | {"wheelhouse-manifest.json"}:
        raise AcceptanceError("wheelhouse file set mismatch")
    agent = by_name["agent-frontdoor"]
    rpds = by_name["rpds-py"]
    setuptools = by_name["setuptools"]
    wheel = by_name["wheel"]
    expected_python = "cp" + str(target["python_minor"]).replace(".", "")
    if (
        agent.get("version") != PACKAGE_VERSION
        or expected_python not in rpds["python_tags"]
        or target["abi_tag"] not in rpds["abi_tags"]
        or not set(platform_tags).intersection(rpds["platform_tags"])
    ):
        raise AcceptanceError("wheelhouse target compatibility mismatch")
    expected_backend = {
        "name": "setuptools",
        "version": setuptools["version"],
        "filename": setuptools["filename"],
        "sha256": setuptools["sha256"],
    }
    if backend != expected_backend:
        raise AcceptanceError("build backend lock mismatch")
    agent_filename = str(agent["filename"])
    agent_payloads = _agent_wheel_payloads(
        pack_root / "wheelhouse" / agent_filename
    )
    return (
        target,
        agent_filename,
        agent_payloads,
        str(setuptools["version"]),
        str(wheel["version"]),
    )


def _validate_pack_root(pack_root: Path) -> _PackContext:
    actual = _actual_pack_files(pack_root)
    manifest_data = _read_regular(pack_root / "manifest.json")
    checksum = _read_regular(pack_root / "manifest.sha256").decode(
        "ascii", errors="replace"
    ).strip()
    if checksum != _sha256(manifest_data):
        raise AcceptanceError("pack manifest checksum mismatch")
    try:
        manifest = json.loads(manifest_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AcceptanceError("pack manifest invalid") from exc
    if not isinstance(manifest, dict):
        raise AcceptanceError("pack manifest invalid")
    records = manifest.get("members")
    if not isinstance(records, list):
        raise AcceptanceError("pack manifest members invalid")
    expected_paths = {"manifest.json", "manifest.sha256"}
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "path",
            "mode",
            "size",
            "sha256",
        }:
            raise AcceptanceError("pack member record invalid")
        relative = _safe_relative(record.get("path"))
        if relative in expected_paths:
            raise AcceptanceError("pack member record duplicated")
        expected_paths.add(relative)
        path = actual.get(relative)
        if path is None:
            raise AcceptanceError("pack member missing")
        data = _read_regular(path)
        if (
            record.get("mode") != (path.stat().st_mode & 0o777)
            or record.get("size") != len(data)
            or record.get("sha256") != _sha256(data)
        ):
            raise AcceptanceError("pack member metadata mismatch")
    if set(actual) != expected_paths:
        raise AcceptanceError("pack root file set mismatch")

    source_section = manifest.get("source_archive")
    verifier_section = manifest.get("verifier")
    if not isinstance(source_section, dict) or not isinstance(
        verifier_section, dict
    ):
        raise AcceptanceError("pack trust fields invalid")
    source_relative = _safe_relative(source_section.get("path"))
    source_manifest_relative = _safe_relative(
        source_section.get("manifest_path")
    )
    verifier_relative = _safe_relative(verifier_section.get("path"))
    source_path = pack_root / source_relative
    source_data = _read_regular(source_path)
    verifier_data = _read_regular(pack_root / verifier_relative)
    if source_section.get("sha256") != _sha256(source_data):
        raise AcceptanceError("source archive manifest mismatch")
    if verifier_section.get("sha256") != _sha256(verifier_data):
        raise AcceptanceError("verifier manifest mismatch")
    source_manifest_path = pack_root / source_manifest_relative
    source_manifest = _load_json(source_manifest_path)
    wheel_manifest = _load_json(
        pack_root / "wheelhouse/wheelhouse-manifest.json"
    )
    public_revision = manifest.get("public_revision")
    if (
        not isinstance(public_revision, str)
        or not re.fullmatch(r"[0-9a-f]{40}", public_revision)
        or source_manifest.get("public_revision") != public_revision
    ):
        raise AcceptanceError("public revision mismatch")
    target, agent_wheel, agent_payloads, setuptools_version, wheel_version = (
        _validate_wheelhouse(pack_root, wheel_manifest)
    )
    if agent_payloads != _source_package_payloads(source_path):
        raise AcceptanceError("agent wheel source binding mismatch")
    return _PackContext(
        manifest=manifest,
        source_manifest=source_manifest,
        wheel_manifest=wheel_manifest,
        source_path=source_path,
        source_sha256=_sha256(source_data),
        source_manifest_sha256=_sha256(_read_regular(source_manifest_path)),
        verifier_sha256=_sha256(verifier_data),
        public_revision=public_revision,
        platform={
            "os_version": str(target["os_version"]),
            "architecture": str(target["architecture"]),
            "python_version": str(target["python_minor"]),
            "pip_version": str(target["pip_version"]),
        },
        agent_wheel=agent_wheel,
        agent_package_payloads=agent_payloads,
        setuptools_version=setuptools_version,
        wheel_version=wheel_version,
    )


def _extract_source(source_path: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise AcceptanceError("source destination already exists")
    destination.mkdir()
    data = _read_regular(source_path)
    seen: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if (
                    not path.parts
                    or path.parts[0] != SOURCE_ROOT_NAME
                    or len(path.parts) < 2
                    or member.name.startswith("/")
                    or "\\" in member.name
                    or any(part in {"", ".", ".."} for part in path.parts)
                    or not (member.isfile() or member.isdir())
                ):
                    raise AcceptanceError("unsafe source archive member")
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                if relative in seen:
                    raise AcceptanceError("duplicate source archive member")
                seen.add(relative)
                target = destination.joinpath(*PurePosixPath(relative).parts)
                target.resolve(strict=False).relative_to(destination.resolve())
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=False)
                    target.chmod(member.mode & 0o777)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise AcceptanceError("source archive member unreadable")
                target.write_bytes(extracted.read())
                target.chmod(member.mode & 0o777)
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        if isinstance(exc, AcceptanceError):
            raise
        raise AcceptanceError("source archive extraction failed") from exc


def _create_isolated_environment(
    run_root: Path, pack_root: Path, ledger: Path
) -> dict[str, str]:
    environment_root = run_root / "environment"
    paths = {
        "HOME": environment_root / "home",
        "XDG_CACHE_HOME": environment_root / "xdg-cache",
        "XDG_CONFIG_HOME": environment_root / "xdg-config",
        "XDG_DATA_HOME": environment_root / "xdg-data",
        "XDG_STATE_HOME": environment_root / "xdg-state",
        "TMPDIR": environment_root / "tmp",
        "PIP_CACHE_DIR": environment_root / "pip-cache",
        "PYTHONPYCACHEPREFIX": environment_root / "pycache",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=False)
    pip_config = environment_root / "pip.conf"
    pip_config.write_bytes(b"")
    env = {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "PYTHONHASHSEED": "0",
        "PYTHONUTF8": "1",
    }
    env.update({name: str(path) for name, path in paths.items()})
    env.update(
        {
            "PIP_CONFIG_FILE": str(pip_config),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONPATH": str(pack_root / "lab"),
            "FRIEND_LAB_ROOT": str(run_root.resolve()),
            "FRIEND_LAB_LEDGER": str(ledger.resolve()),
            "FRIEND_LAB_PHASE": "preflight",
            "FRIEND_LAB_CONTROL_OUTSIDE": str(
                run_root.parent / ".friend-lab-outside-write-control"
            ),
        }
    )
    return env


def _phase_environment(env: Mapping[str, str], phase: str) -> dict[str, str]:
    if not _SAFE_LABEL.fullmatch(phase):
        raise AcceptanceError("phase label invalid")
    value = dict(env)
    value["FRIEND_LAB_PHASE"] = phase
    return value


def _ledger_events(ledger: Path) -> tuple[dict[str, str], ...]:
    if ledger.is_symlink() or not ledger.is_file():
        raise AcceptanceError("audit ledger invalid")
    events: list[dict[str, str]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AcceptanceError("audit ledger entry invalid") from exc
        if (
            not isinstance(value, dict)
            or set(value) != {"phase", "operation_class"}
            or value.get("operation_class") not in {"socket", "outside-write"}
            or not isinstance(value.get("phase"), str)
            or not _SAFE_LABEL.fullmatch(str(value["phase"]))
        ):
            raise AcceptanceError("audit ledger entry invalid")
        events.append(
            {
                "phase": str(value["phase"]),
                "operation_class": str(value["operation_class"]),
            }
        )
    return tuple(events)


def _privacy_control_ok(pack_root: Path, context: _PackContext) -> bool:
    section = context.manifest.get("privacy_control")
    if not isinstance(section, dict):
        return False
    try:
        relative = _safe_relative(section.get("path"))
        data = _read_regular(pack_root / relative)
    except AcceptanceError:
        return False
    return (
        section.get("sha256") == _sha256(data)
        and set(scan_forbidden_text(PurePosixPath(relative), data))
        == set(PRIVACY_CATEGORIES)
    )


def _scan_tree(root: Path) -> tuple[str, ...]:
    hits: set[str] = set()
    if root.is_symlink() or not root.is_dir():
        return ("tree-invalid",)
    for path in root.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            hits.add("tree-invalid")
            continue
        if not path.is_file():
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        try:
            data = path.read_bytes()
        except OSError:
            hits.add("tree-unreadable")
            continue
        hits.update(scan_forbidden_text(relative, data))
    return tuple(sorted(hits))


def _installed_agent_payloads(venv: Path) -> dict[str, bytes]:
    candidates = tuple(
        path
        for path in (venv / "lib").glob("python*/site-packages/frontdoor")
        if path.is_dir() and not path.is_symlink()
    )
    if len(candidates) != 1:
        raise AcceptanceError("installed agent package missing or ambiguous")
    package_root = candidates[0]
    payloads: dict[str, bytes] = {}
    for path in package_root.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise AcceptanceError("installed agent package contains unsafe member")
        if not path.is_file():
            continue
        relative = PurePosixPath(path.relative_to(package_root).as_posix())
        if relative.suffix.lower() in {".so", ".dylib", ".dll", ".pyd"}:
            raise AcceptanceError("installed agent package contains native member")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise AcceptanceError("installed agent package unreadable") from exc
        if scan_forbidden_text(relative, data):
            raise AcceptanceError("installed agent package privacy validation failed")
        payloads[f"frontdoor/{relative.as_posix()}"] = data
    if not payloads:
        raise AcceptanceError("installed agent package empty")
    return payloads


def _static_source_ok(source_root: Path) -> bool:
    package_root = source_root / "src/frontdoor"
    if package_root.is_symlink() or not package_root.is_dir():
        return False
    forbidden = re.compile(
        rb"(?m)^\s*(?:from\s+(?:socket|subprocess|ctypes)\s+import|"
        rb"import\s+(?:socket|subprocess|ctypes)(?:\s|$))|"
        rb"\bos\.(?:system|popen)\s*\(|\b(?:eval|exec)\s*\("
    )
    native_suffixes = {".so", ".dylib", ".dll", ".pyd"}
    for path in package_root.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            return False
        if not path.is_file():
            continue
        if path.suffix.lower() in native_suffixes:
            return False
        try:
            data = path.read_bytes()
        except OSError:
            return False
        if path.suffix == ".py" and forbidden.search(data):
            return False
    return True


def _run_root_file_set_ok(run_root: Path) -> bool:
    try:
        entries = tuple(run_root.iterdir())
    except OSError:
        return False
    if any(path.is_symlink() for path in entries):
        return False
    return {path.name for path in entries}.issubset(_ALLOWED_RUN_ROOT_ENTRIES)


class _AcceptanceState:
    def __init__(self, request: AcceptanceRequest) -> None:
        self.request = request
        self.steps: list[dict[str, object]] = []
        self.deterministic: list[dict[str, object]] = []
        self.gaps: set[str] = set()
        self.failed = False
        self.collected_test_count = 0
        self.uninstall_result = "NOT_RUN"
        self.controls: dict[str, object] = {
            "network_disconnect": (
                "REMOTE_UNAVAILABLE"
                if request.execution_mode == "remote"
                else (
                    "CONFIRMED"
                    if request.network_disconnected_confirmed
                    else "NOT_CONFIRMED"
                )
            ),
            "socket_guard": "NOT_RUN",
            "write_guard": "NOT_RUN",
            "privacy_scan": "NOT_RUN",
            "secret_scan": "NOT_RUN",
            "post_control_socket_events": 0,
            "post_control_write_events": 0,
        }
        if request.execution_mode == "remote":
            self.gaps.add("REMOTE_EXECUTION")
        elif not request.network_disconnected_confirmed:
            self.gaps.add("NETWORK_DISCONNECT_UNCONFIRMED")

    def add_internal(self, phase: str, passed: bool) -> None:
        self.steps.append(
            {
                "phase": phase,
                "command_class": phase,
                "exit_status": 0 if passed else 1,
                "result": "PASS" if passed else "FAIL",
                "stdout_sha256": _EMPTY_SHA256,
                "stderr_sha256": _EMPTY_SHA256,
            }
        )
        if not passed:
            self.failed = True

    def add_command(
        self,
        phase: str,
        result: CommandResult,
        *,
        expect_zero: bool,
    ) -> bool:
        valid = (
            result.command_class == phase
            and isinstance(result.exit_status, int)
            and -1 <= result.exit_status <= 255
            and _HEX64.fullmatch(result.stdout_sha256) is not None
            and _HEX64.fullmatch(result.stderr_sha256) is not None
            and not result.timed_out
        )
        passed = valid and (
            result.exit_status == 0 if expect_zero else result.exit_status > 0
        )
        self.steps.append(
            {
                "phase": phase,
                "command_class": phase,
                "exit_status": (
                    result.exit_status
                    if isinstance(result.exit_status, int)
                    and -1 <= result.exit_status <= 255
                    else -1
                ),
                "result": "PASS" if passed else "FAIL",
                "stdout_sha256": (
                    result.stdout_sha256
                    if _HEX64.fullmatch(result.stdout_sha256)
                    else _EMPTY_SHA256
                ),
                "stderr_sha256": (
                    result.stderr_sha256
                    if _HEX64.fullmatch(result.stderr_sha256)
                    else _EMPTY_SHA256
                ),
            }
        )
        if not passed:
            self.failed = True
            self.gaps.add("PHASE_FAILURE")
        return passed

    def compare_pair(
        self, base: str, first: CommandResult, second: CommandResult
    ) -> bool:
        passed = (
            first.exit_status == second.exit_status
            and first.stdout_sha256 == second.stdout_sha256
            and first.stderr_sha256 == second.stderr_sha256
            and not first.timed_out
            and not second.timed_out
        )
        if passed and first.exit_status >= 0:
            self.deterministic.append(
                {
                    "command_class": base,
                    "exit_status": first.exit_status,
                    "stdout_sha256": first.stdout_sha256,
                    "stderr_sha256": first.stderr_sha256,
                }
            )
        else:
            self.failed = True
            self.gaps.add("PHASE_FAILURE")
        return passed


def _run_phase(
    state: _AcceptanceState,
    runner: CommandRunner,
    command_class: str,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    expect_zero: bool = True,
    timeout_seconds: float = 120.0,
    output_budget_bytes: int = 2_000_000,
) -> CommandResult | None:
    result = runner.run(
        command_class,
        argv,
        cwd=cwd,
        env=_phase_environment(env, command_class),
        timeout_seconds=timeout_seconds,
        output_budget_bytes=output_budget_bytes,
    )
    if not state.add_command(command_class, result, expect_zero=expect_zero):
        return None
    return result


def _run_deterministic_pair(
    state: _AcceptanceState,
    runner: CommandRunner,
    base: str,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    expect_zero: bool,
    timeout_seconds: float = 120.0,
) -> bool:
    first = _run_phase(
        state,
        runner,
        base,
        argv,
        cwd=cwd,
        env=env,
        expect_zero=expect_zero,
        timeout_seconds=timeout_seconds,
    )
    if first is None:
        return False
    repeated_class = base + "-repeat"
    second = _run_phase(
        state,
        runner,
        repeated_class,
        argv,
        cwd=cwd,
        env=env,
        expect_zero=expect_zero,
        timeout_seconds=timeout_seconds,
    )
    if second is None:
        return False
    return state.compare_pair(base, first, second)


def _fallback_context(request: AcceptanceRequest) -> _PackContext:
    zero = "0" * 64
    return _PackContext(
        manifest={},
        source_manifest={},
        wheel_manifest={},
        source_path=request.pack_root / "missing-source.tar.gz",
        source_sha256=zero,
        source_manifest_sha256=zero,
        verifier_sha256=(
            _sha256(_read_regular(request.detached_verifier_path))
            if request.detached_verifier_path.is_file()
            and not request.detached_verifier_path.is_symlink()
            else zero
        ),
        public_revision="0" * 40,
        platform={
            "os_version": "UNKNOWN",
            "architecture": "UNKNOWN",
            "python_version": "UNKNOWN",
            "pip_version": "UNKNOWN",
        },
        agent_wheel="missing.whl",
        agent_package_payloads={},
        setuptools_version="UNKNOWN",
        wheel_version="UNKNOWN",
    )


def _receipt(
    state: _AcceptanceState,
    context: _PackContext,
    *,
    pack_sha256: str,
    verifier_sha256: str,
    digest_equality: dict[str, bool],
) -> dict[str, object]:
    if state.failed:
        classification = "NOT_READY"
    elif state.gaps:
        classification = "PRIVATE_HANDOFF_READY_WITH_GAPS"
    else:
        classification = "PRIVATE_HANDOFF_READY"
    return {
        "schema_version": "friend-acceptance-receipt.v1",
        "package_version": PACKAGE_VERSION,
        "public_revision": context.public_revision,
        "pack_sha256": pack_sha256,
        "source_archive_sha256": context.source_sha256,
        "source_manifest_sha256": context.source_manifest_sha256,
        "verifier_sha256": verifier_sha256,
        "platform": context.platform,
        "digest_equality": digest_equality,
        "controls": state.controls,
        "steps": state.steps,
        "collected_test_count": state.collected_test_count,
        "deterministic_output_hashes": state.deterministic,
        "uninstall_result": state.uninstall_result,
        "final_classification": classification,
        "verifier_role": state.request.verifier_role,
        "gaps": [item for item in _GAP_ORDER if item in state.gaps],
    }


def _validate_receipt(receipt: dict[str, object], schema_path: Path) -> None:
    schema = _load_json(schema_path)
    receipt_fields = {
        "schema_version",
        "package_version",
        "public_revision",
        "pack_sha256",
        "source_archive_sha256",
        "source_manifest_sha256",
        "verifier_sha256",
        "platform",
        "digest_equality",
        "controls",
        "steps",
        "collected_test_count",
        "deterministic_output_hashes",
        "uninstall_result",
        "final_classification",
        "verifier_role",
        "gaps",
    }
    required = schema.get("required")
    properties = schema.get("properties")
    if (
        schema.get("additionalProperties") is not False
        or not isinstance(required, list)
        or set(required) != receipt_fields
        or not isinstance(properties, dict)
        or set(properties) != receipt_fields
        or set(receipt) != receipt_fields
    ):
        raise AcceptanceError("receipt schema validation failed")

    safe_label = lambda value: (
        isinstance(value, str) and _SAFE_LABEL.fullmatch(value) is not None
    )
    sha256 = lambda value: (
        isinstance(value, str) and _HEX64.fullmatch(value) is not None
    )
    integer = lambda value: isinstance(value, int) and not isinstance(value, bool)
    pass_states = {"PASS", "FAIL", "NOT_RUN"}

    platform = receipt.get("platform")
    platform_ok = bool(
        isinstance(platform, dict)
        and set(platform)
        == {"os_version", "architecture", "python_version", "pip_version"}
        and isinstance(platform.get("os_version"), str)
        and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,63}",
            str(platform.get("os_version")),
        )
        and all(
            safe_label(platform.get(name))
            for name in ("architecture", "python_version", "pip_version")
        )
    )
    equality = receipt.get("digest_equality")
    equality_ok = bool(
        isinstance(equality, dict)
        and set(equality) == {"pack", "source", "verifier"}
        and all(type(equality.get(name)) is bool for name in equality)
    )
    controls = receipt.get("controls")
    controls_ok = bool(
        isinstance(controls, dict)
        and set(controls)
        == {
            "network_disconnect",
            "socket_guard",
            "write_guard",
            "privacy_scan",
            "secret_scan",
            "post_control_socket_events",
            "post_control_write_events",
        }
        and controls.get("network_disconnect")
        in {"CONFIRMED", "NOT_CONFIRMED", "REMOTE_UNAVAILABLE"}
        and all(
            controls.get(name) in pass_states
            for name in ("socket_guard", "write_guard", "privacy_scan", "secret_scan")
        )
        and all(
            integer(controls.get(name)) and int(controls[name]) >= 0
            for name in ("post_control_socket_events", "post_control_write_events")
        )
    )

    steps = receipt.get("steps")
    steps_ok = isinstance(steps, list) and bool(steps)
    if steps_ok:
        for step in steps:
            if not (
                isinstance(step, dict)
                and set(step)
                == {
                    "phase",
                    "command_class",
                    "exit_status",
                    "result",
                    "stdout_sha256",
                    "stderr_sha256",
                }
                and safe_label(step.get("phase"))
                and safe_label(step.get("command_class"))
                and integer(step.get("exit_status"))
                and -1 <= int(step["exit_status"]) <= 255
                and step.get("result") in pass_states
                and sha256(step.get("stdout_sha256"))
                and sha256(step.get("stderr_sha256"))
            ):
                steps_ok = False
                break

    deterministic = receipt.get("deterministic_output_hashes")
    deterministic_ok = isinstance(deterministic, list)
    if deterministic_ok:
        for item in deterministic:
            if not (
                isinstance(item, dict)
                and set(item)
                == {
                    "command_class",
                    "exit_status",
                    "stdout_sha256",
                    "stderr_sha256",
                }
                and safe_label(item.get("command_class"))
                and integer(item.get("exit_status"))
                and 0 <= int(item["exit_status"]) <= 255
                and sha256(item.get("stdout_sha256"))
                and sha256(item.get("stderr_sha256"))
            ):
                deterministic_ok = False
                break

    gaps = receipt.get("gaps")
    gaps_ok = bool(
        isinstance(gaps, list)
        and all(isinstance(item, str) for item in gaps)
        and len(gaps) == len(set(gaps))
        and all(item in _GAP_ORDER for item in gaps)
    )
    if not all(
        (
            receipt.get("schema_version") == "friend-acceptance-receipt.v1",
            receipt.get("package_version") == PACKAGE_VERSION,
            isinstance(receipt.get("public_revision"), str)
            and re.fullmatch(r"[0-9a-f]{40}", str(receipt["public_revision"]))
            is not None,
            all(
                sha256(receipt.get(name))
                for name in (
                    "pack_sha256",
                    "source_archive_sha256",
                    "source_manifest_sha256",
                    "verifier_sha256",
                )
            ),
            platform_ok,
            equality_ok,
            controls_ok,
            steps_ok,
            integer(receipt.get("collected_test_count"))
            and int(receipt["collected_test_count"]) >= 0,
            deterministic_ok,
            receipt.get("uninstall_result") in pass_states,
            receipt.get("final_classification")
            in {
                "PRIVATE_HANDOFF_READY",
                "PRIVATE_HANDOFF_READY_WITH_GAPS",
                "NOT_READY",
            },
            receipt.get("verifier_role")
            in {"receiver-human", "receiver-agent", "independent-reviewer"},
            gaps_ok,
        )
    ):
        raise AcceptanceError("receipt schema validation failed")


def _atomic_write_receipt(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise OSError("receipt destination already exists")
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".receipt-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _finish(
    state: _AcceptanceState,
    context: _PackContext,
    *,
    pack_sha256: str,
    verifier_sha256: str,
    digest_equality: dict[str, bool],
) -> dict[str, object]:
    if not state.steps:
        state.add_internal("incomplete-evidence", False)
        state.gaps.add("INCOMPLETE_EVIDENCE")
    receipt = _receipt(
        state,
        context,
        pack_sha256=pack_sha256,
        verifier_sha256=verifier_sha256,
        digest_equality=digest_equality,
    )
    try:
        _validate_receipt(
            receipt,
            state.request.pack_root
            / "schemas/friend_acceptance_receipt.v1.json",
        )
        receipt_data = (
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        if scan_forbidden_text(PurePosixPath(RECEIPT_NAME), receipt_data):
            raise AcceptanceError("receipt privacy validation failed")
        _atomic_write_receipt(state.request.run_root / RECEIPT_NAME, receipt_data)
    except (AcceptanceError, OSError, ValueError):
        state.failed = True
        state.gaps.add("INCOMPLETE_EVIDENCE")
        receipt = _receipt(
            state,
            context,
            pack_sha256=pack_sha256,
            verifier_sha256=verifier_sha256,
            digest_equality=digest_equality,
        )
    return receipt


def _test_count(runner: CommandRunner) -> int:
    value = getattr(runner, "collected_test_count", None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    reader = getattr(runner, "stdout_bytes", None)
    if callable(reader):
        for command_class, pattern in (
            ("test-collect", rb"(?m)(\d+) tests? collected(?:\s|$)"),
            ("tests", rb"(?m)(\d+) passed(?:\s|$)"),
        ):
            data = reader(command_class)
            if isinstance(data, bytes):
                matches = re.findall(pattern, data)
                if matches:
                    return int(matches[-1])
    return 0


def _observed_digest(path: Path) -> str:
    try:
        return _sha256(_read_regular(path))
    except AcceptanceError:
        return "0" * 64


def run_acceptance(
    request: AcceptanceRequest,
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, object]:
    """Execute the approved acceptance state machine once, without fallback."""

    if request.execution_mode not in {"local", "remote"}:
        raise AcceptanceError("execution mode invalid")
    if request.verifier_role not in {
        "receiver-human",
        "receiver-agent",
        "independent-reviewer",
    }:
        raise AcceptanceError("verifier role invalid")
    if request.run_root.exists() or request.run_root.is_symlink():
        raise AcceptanceError("run root must be a new nonsymlink leaf")
    request.run_root.mkdir(parents=True, mode=0o700)
    state = _AcceptanceState(request)
    context = _fallback_context(request)
    pack_sha = _observed_digest(request.pack_path)
    detached_sha = _observed_digest(request.detached_verifier_path)
    digest_equality = {
        "pack": bool(
            _HEX64.fullmatch(request.expected_pack_sha256)
            and pack_sha == request.expected_pack_sha256
        ),
        "source": False,
        "verifier": bool(
            _HEX64.fullmatch(request.expected_verifier_sha256)
            and detached_sha == request.expected_verifier_sha256
        ),
    }

    try:
        context = _validate_pack_root(request.pack_root)
        digest_equality["source"] = bool(
            _HEX64.fullmatch(request.expected_source_sha256)
            and context.source_sha256 == request.expected_source_sha256
        )
        verification = verify_friend_pack(
            request.pack_path,
            detached_verifier_path=request.detached_verifier_path,
            expected_pack_sha256=request.expected_pack_sha256,
            expected_source_sha256=request.expected_source_sha256,
            expected_verifier_sha256=request.expected_verifier_sha256,
        )
        verified = bool(verification.ok) and all(digest_equality.values())
    except (AcceptanceError, OSError, ValueError):
        verified = False
    state.add_internal("verify-pack", verified)
    if not verified:
        state.gaps.add("DIGEST_MISMATCH")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    privacy_control_ok = _privacy_control_ok(request.pack_root, context)
    state.add_internal("privacy-control", privacy_control_ok)
    if not privacy_control_ok:
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    evidence = request.run_root / "evidence"
    evidence.mkdir()
    ledger = request.run_root / "audit-ledger.jsonl"
    ledger.write_bytes(b"")
    ledger.chmod(0o600)
    try:
        env = _create_isolated_environment(
            request.run_root, request.pack_root, ledger
        )
    except (AcceptanceError, OSError):
        state.add_internal("environment-isolation", False)
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )
    runner = command_runner or BoundedCommandRunner(request.run_root)

    write_result = _run_phase(
        state,
        runner,
        "write-control",
        (
            sys.executable,
            str(request.pack_root / "lab/controls/write_outside_probe.py"),
        ),
        cwd=request.run_root,
        env=env,
        expect_zero=False,
        timeout_seconds=15.0,
        output_budget_bytes=100_000,
    )
    try:
        write_events = _ledger_events(ledger)
    except AcceptanceError:
        write_events = ()
    write_control_ok = bool(
        write_result is not None
        and [item["operation_class"] for item in write_events]
        == ["outside-write"]
    )
    state.controls["write_guard"] = "PASS" if write_control_ok else "FAIL"
    if not write_control_ok:
        state.failed = True
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    socket_result = _run_phase(
        state,
        runner,
        "socket-control",
        (sys.executable, str(request.pack_root / "lab/controls/socket_probe.py")),
        cwd=request.run_root,
        env=env,
        expect_zero=False,
        timeout_seconds=15.0,
        output_budget_bytes=100_000,
    )
    try:
        baseline = _ledger_events(ledger)
    except AcceptanceError:
        baseline = ()
    socket_control_ok = bool(
        socket_result is not None
        and [item["operation_class"] for item in baseline]
        == ["outside-write", "socket"]
    )
    state.controls["socket_guard"] = "PASS" if socket_control_ok else "FAIL"
    if not socket_control_ok:
        state.failed = True
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    reachability_argv = (
        sys.executable,
        "-S",
        "-c",
        (
            "import socket; "
            "socket.create_connection(('example.com', 443), 2).close()"
        ),
    )
    if request.execution_mode == "local" and (
        request.network_disconnected_confirmed
    ):
        reachability = _run_phase(
            state,
            runner,
            "reachability-probe",
            reachability_argv,
            cwd=request.run_root,
            env=env,
            expect_zero=False,
            timeout_seconds=5.0,
            output_budget_bytes=20_000,
        )
    else:
        observed = runner.run(
            "reachability-probe",
            reachability_argv,
            cwd=request.run_root,
            env=_phase_environment(env, "reachability-probe"),
            timeout_seconds=5.0,
            output_budget_bytes=20_000,
        )
        reachability = (
            observed
            if state.add_command(
                "reachability-probe",
                observed,
                expect_zero=observed.exit_status == 0,
            )
            else None
        )
    if reachability is None:
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    source_root = request.run_root / "source"
    try:
        _extract_source(context.source_path, source_root)
        state.add_internal("source-materialize", True)
    except (AcceptanceError, OSError, ValueError):
        state.add_internal("source-materialize", False)
        state.gaps.add("PHASE_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    source_venv = request.run_root / "source-venv"
    wheel_venv = request.run_root / "wheel-venv"
    source_python = source_venv / "bin/python"
    wheel_python = wheel_venv / "bin/python"
    wheelhouse = request.pack_root / "wheelhouse"
    positive_fixture = source_root / "fixtures/positive/01_install_only.json"

    positive_phases: tuple[
        tuple[str, tuple[str, ...], Path, float], ...
    ] = (
        (
            "source-venv",
            (sys.executable, "-m", "venv", str(source_venv)),
            request.run_root,
            120.0,
        ),
        (
            "wheel-venv",
            (sys.executable, "-m", "venv", str(wheel_venv)),
            request.run_root,
            120.0,
        ),
        (
            "source-backend-install",
            (
                str(source_python),
                "-m",
                "pip",
                "install",
                "-q",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                f"setuptools=={context.setuptools_version}",
                f"wheel=={context.wheel_version}",
            ),
            request.run_root,
            180.0,
        ),
        (
            "source-install",
            (
                str(source_python),
                "-m",
                "pip",
                "install",
                "-q",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                "--no-build-isolation",
                f"{source_root}[test]",
            ),
            request.run_root,
            180.0,
        ),
        (
            "wheel-install",
            (
                str(wheel_python),
                "-m",
                "pip",
                "install",
                "-q",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                str(wheelhouse / context.agent_wheel),
                "pytest",
            ),
            request.run_root,
            180.0,
        ),
    )
    for command_class, argv, cwd, timeout in positive_phases:
        if _run_phase(
            state,
            runner,
            command_class,
            argv,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout,
        ) is None:
            return _finish(
                state,
                context,
                pack_sha256=pack_sha,
                verifier_sha256=detached_sha,
                digest_equality=digest_equality,
            )

    try:
        installed_packages_ok = all(
            _installed_agent_payloads(venv) == context.agent_package_payloads
            for venv in (source_venv, wheel_venv)
        )
    except AcceptanceError:
        installed_packages_ok = False
    state.add_internal("installed-package-boundary", installed_packages_ok)
    if not installed_packages_ok:
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    collect_argv = (
        str(source_python),
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "-c",
        os.devnull,
        *_OPTIONAL_ADAPTER_TEST_IGNORES,
        "tests",
    )
    if _run_phase(
        state,
        runner,
        "test-collect",
        collect_argv,
        cwd=source_root,
        env=env,
        timeout_seconds=120.0,
    ) is None:
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )
    state.collected_test_count = _test_count(runner)
    if state.collected_test_count <= 0:
        state.add_internal("test-count", False)
        state.gaps.add("INCOMPLETE_EVIDENCE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    pytest_argv = (
        str(source_python),
        "-m",
        "pytest",
        "-qq",
        "-p",
        "no:cacheprovider",
        "-c",
        os.devnull,
        *_OPTIONAL_ADAPTER_TEST_IGNORES,
        "tests",
    )
    if not _run_deterministic_pair(
        state,
        runner,
        "tests",
        pytest_argv,
        cwd=source_root,
        env=env,
        expect_zero=True,
        timeout_seconds=300.0,
    ):
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )
    wheel_pytest_argv = (str(wheel_python), *pytest_argv[1:])
    if not _run_deterministic_pair(
        state,
        runner,
        "wheel-tests",
        wheel_pytest_argv,
        cwd=source_root,
        env=env,
        expect_zero=True,
        timeout_seconds=300.0,
    ):
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )
    source_cli = source_venv / "bin/agent-frontdoor"
    wheel_cli = wheel_venv / "bin/agent-frontdoor"
    samples = (
        (
            "sample-validate",
            (str(source_cli), "validate", str(positive_fixture)),
        ),
        (
            "sample-card",
            (str(source_cli), "card", str(positive_fixture)),
        ),
        (
            "wheel-sample-validate",
            (str(wheel_cli), "validate", str(positive_fixture)),
        ),
        (
            "wheel-sample-card",
            (str(wheel_cli), "card", str(positive_fixture)),
        ),
    )
    for command_class, argv in samples:
        if not _run_deterministic_pair(
            state,
            runner,
            command_class,
            argv,
            cwd=source_root,
            env=env,
            expect_zero=True,
        ):
            return _finish(
                state,
                context,
                pack_sha256=pack_sha,
                verifier_sha256=detached_sha,
                digest_equality=digest_equality,
            )

    negative_fixtures = (
        ("negative-deploy", "fixtures/negative/neg_05_deploy_tag_none.json"),
        (
            "negative-scheduler",
            "fixtures/negative/neg_13_scheduler_tag_none.json",
        ),
        (
            "negative-cleanup",
            "fixtures/negative/neg_19_destructive_cleanup_tag_none.json",
        ),
        (
            "negative-authority",
            "fixtures/negative/neg_25_authority_tag_none.json",
        ),
        (
            "negative-missing-manifest",
            "fixtures/negative/neg_01_install_missing_manifest.json",
        ),
    )
    for command_class, relative in negative_fixtures:
        if not _run_deterministic_pair(
            state,
            runner,
            command_class,
            (str(source_cli), "validate", str(source_root / relative)),
            cwd=source_root,
            env=env,
            expect_zero=False,
        ):
            return _finish(
                state,
                context,
                pack_sha256=pack_sha,
                verifier_sha256=detached_sha,
                digest_equality=digest_equality,
            )

    source_privacy_hits = _scan_tree(source_root)
    evidence_privacy_hits = _scan_tree(request.run_root / "evidence")
    privacy_ok = not source_privacy_hits and not evidence_privacy_hits
    state.controls["privacy_scan"] = "PASS" if privacy_ok else "FAIL"
    secret_categories = {"credential-like", "environment-assignment"}
    secret_ok = not secret_categories.intersection(
        set(source_privacy_hits) | set(evidence_privacy_hits)
    )
    state.controls["secret_scan"] = "PASS" if secret_ok else "FAIL"
    if not privacy_ok or not secret_ok:
        state.failed = True
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )
    noop = (sys.executable, "-c", "raise SystemExit(0)")
    if _run_phase(
        state,
        runner,
        "privacy-scan",
        noop,
        cwd=request.run_root,
        env=env,
        timeout_seconds=15.0,
        output_budget_bytes=20_000,
    ) is None:
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    static_ok = _static_source_ok(source_root)
    if not static_ok:
        state.failed = True
        state.gaps.add("CONTROL_FAILURE")
        state.add_internal("static-source", False)
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )
    if _run_phase(
        state,
        runner,
        "static-scan",
        noop,
        cwd=request.run_root,
        env=env,
        timeout_seconds=15.0,
        output_budget_bytes=20_000,
    ) is None:
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    try:
        final_events = _ledger_events(ledger)
    except AcceptanceError:
        final_events = ()
    added_events = (
        final_events[len(baseline) :]
        if final_events[: len(baseline)] == baseline
        else final_events
    )
    socket_events = sum(
        item["operation_class"] == "socket" for item in added_events
    )
    write_events_count = sum(
        item["operation_class"] == "outside-write" for item in added_events
    )
    state.controls["post_control_socket_events"] = socket_events
    state.controls["post_control_write_events"] = write_events_count
    if socket_events or write_events_count or not _run_root_file_set_ok(
        request.run_root
    ):
        state.failed = True
        state.gaps.add("CONTROL_FAILURE")
        return _finish(
            state,
            context,
            pack_sha256=pack_sha,
            verifier_sha256=detached_sha,
            digest_equality=digest_equality,
        )

    uninstall_phases = (
        (
            "source-uninstall",
            (
                str(source_python),
                "-m",
                "pip",
                "uninstall",
                "-q",
                "-y",
                "agent-frontdoor",
            ),
        ),
        (
            "source-cli-absent",
            (
                str(source_python),
                "-c",
                (
                    "import importlib.util; "
                    "raise SystemExit(importlib.util.find_spec('frontdoor') is not None)"
                ),
            ),
        ),
        (
            "wheel-uninstall",
            (
                str(wheel_python),
                "-m",
                "pip",
                "uninstall",
                "-q",
                "-y",
                "agent-frontdoor",
            ),
        ),
        (
            "wheel-cli-absent",
            (
                str(wheel_python),
                "-c",
                (
                    "import importlib.util; "
                    "raise SystemExit(importlib.util.find_spec('frontdoor') is not None)"
                ),
            ),
        ),
    )
    for command_class, argv in uninstall_phases:
        if _run_phase(
            state,
            runner,
            command_class,
            argv,
            cwd=request.run_root,
            env=env,
            timeout_seconds=120.0,
        ) is None:
            state.uninstall_result = "FAIL"
            return _finish(
                state,
                context,
                pack_sha256=pack_sha,
                verifier_sha256=detached_sha,
                digest_equality=digest_equality,
            )
    state.uninstall_result = "PASS"
    try:
        after_uninstall_events = _ledger_events(ledger)
    except AcceptanceError:
        after_uninstall_events = ()
    if after_uninstall_events != baseline or not _run_root_file_set_ok(
        request.run_root
    ):
        state.failed = True
        state.gaps.add("CONTROL_FAILURE")
    return _finish(
        state,
        context,
        pack_sha256=pack_sha,
        verifier_sha256=detached_sha,
        digest_equality=digest_equality,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one human-attended Agent Frontdoor friend-lab acceptance"
    )
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--detached-verifier", type=Path, required=True)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--expected-pack-sha256", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-verifier-sha256", required=True)
    parser.add_argument("--execution-mode", choices=("local", "remote"), required=True)
    parser.add_argument(
        "--verifier-role",
        choices=("receiver-human", "receiver-agent", "independent-reviewer"),
        required=True,
    )
    parser.add_argument(
        "--network-disconnected-confirmed",
        action="store_true",
        help="record the human's independent physical-disconnect confirmation",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    request = AcceptanceRequest(
        pack_path=args.pack,
        detached_verifier_path=args.detached_verifier,
        pack_root=args.pack_root,
        run_root=args.run_root,
        expected_pack_sha256=args.expected_pack_sha256,
        expected_source_sha256=args.expected_source_sha256,
        expected_verifier_sha256=args.expected_verifier_sha256,
        execution_mode=args.execution_mode,
        verifier_role=args.verifier_role,
        network_disconnected_confirmed=args.network_disconnected_confirmed,
    )
    try:
        receipt = run_acceptance(request)
    except AcceptanceError as exc:
        print(f"NOT_READY {exc}", file=sys.stderr)
        return 2
    print(receipt["final_classification"])
    return 0 if receipt["final_classification"] != "NOT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
