from __future__ import annotations

from dataclasses import replace
import builtins
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
import tarfile
import zipfile

from jsonschema import Draft202012Validator
import pytest

from tools.friend_lab import acceptance_runner as acceptance


HEX_EMPTY = hashlib.sha256(b"").hexdigest()
PUBLIC_REVISION = "a" * 40
PACK_ROOT_NAME = "agent-frontdoor-friend-pack-0.2.0"
SOURCE_ROOT_NAME = "agent-frontdoor-0.2.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _tar_gz(entries: dict[str, tuple[bytes, int]], root: str) -> bytes:
    stream = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for relative in sorted(entries):
                data, mode = entries[relative]
                info = tarfile.TarInfo(f"{root}/{relative}")
                info.size = len(data)
                info.mode = mode
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def _member(path: str, data: bytes, mode: int = 0o644) -> dict[str, object]:
    return {
        "path": path,
        "mode": mode,
        "size": len(data),
        "sha256": _sha256(data),
    }


def _wheel_bytes(
    name: str,
    version: str,
    tag: str,
    package_payloads: dict[str, bytes] | None = None,
) -> bytes:
    stream = io.BytesIO()
    dist_info = f"{name.replace('-', '_')}-{version}.dist-info"
    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        "License: MIT\n"
        + ("Requires-Dist: jsonschema>=4\n" if name == "agent-frontdoor" else "")
    ).encode("utf-8")
    wheel = (
        "Wheel-Version: 1.0\n"
        "Generator: friend-lab-test\n"
        "Root-Is-Purelib: true\n"
        f"Tag: {tag}\n"
    ).encode("utf-8")
    members = dict(package_payloads or {})
    members.update(
        {
            f"{dist_info}/METADATA": metadata,
            f"{dist_info}/WHEEL": wheel,
            f"{dist_info}/RECORD": b"",
        }
    )
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative, data in sorted(members.items()):
            archive.writestr(relative, data)
    return stream.getvalue()


def _replace_wheel_member(
    pack_root: Path, filename: str, member: str, payload: bytes
) -> None:
    wheel_path = pack_root / "wheelhouse" / filename
    with zipfile.ZipFile(wheel_path) as archive:
        members = {
            item.filename: archive.read(item)
            for item in archive.infolist()
            if not item.is_dir()
        }
    members[member] = payload
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative, data in sorted(members.items()):
            archive.writestr(relative, data)
    wheel_data = stream.getvalue()
    wheel_manifest_path = pack_root / "wheelhouse/wheelhouse-manifest.json"
    wheel_manifest = json.loads(wheel_manifest_path.read_text(encoding="utf-8"))
    for record in wheel_manifest["wheels"]:
        if record["filename"] == filename:
            record["size"] = len(wheel_data)
            record["sha256"] = _sha256(wheel_data)
            break
    else:  # pragma: no cover - fixture construction guard
        raise AssertionError(f"missing wheel record: {filename}")
    _replace_pack_payload(
        pack_root, f"wheelhouse/{filename}", wheel_data
    )
    _replace_pack_payload(
        pack_root,
        "wheelhouse/wheelhouse-manifest.json",
        _json_bytes(wheel_manifest),
    )


def _privacy_control() -> bytes:
    return (
        "absolute-user-path=/Users/synthetic-receiver/private.txt\n"
        "account=synthetic-private-host\n"
        "ip-address=192.0.2.44\n"
        "password=synthetic-secret-token\n"
        "SYNTHETIC_API_KEY=synthetic-environment-value\n"
        "private-operational-record=memory/active_next.md\n"
    ).encode("utf-8")


def _replace_pack_payload(pack_root: Path, relative: str, data: bytes) -> None:
    path = pack_root / relative
    mode = path.stat().st_mode & 0o777
    path.write_bytes(data)
    path.chmod(mode)
    manifest_path = pack_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["members"]:
        if item["path"] == relative:
            item.update(_member(relative, data, mode))
            break
    else:  # pragma: no cover - fixture construction guard
        raise AssertionError(f"missing outer member: {relative}")
    manifest_data = _json_bytes(manifest)
    manifest_path.write_bytes(manifest_data)
    (pack_root / "manifest.sha256").write_text(
        _sha256(manifest_data) + "\n", encoding="ascii"
    )


class FakeRunner:
    collected_test_count = 571

    def __init__(self) -> None:
        self.called_classes: list[str] = []
        self.calls: list[tuple[str, tuple[str, ...], dict[str, str]]] = []
        self.exit_statuses: dict[str, int] = {}
        self.timeouts: set[str] = set()
        self.output_caps: set[str] = set()
        self.control_events = {"write-control", "socket-control"}
        self.nondeterministic_stdout: set[str] = set()
        self.nondeterministic_stderr: set[str] = set()
        self.nondeterministic_status: set[str] = set()
        self.extra_guard_after: str | None = None
        self.undeclared_after: str | None = None
        self.installed_private_after: str | None = None

    @staticmethod
    def _base(command_class: str) -> str:
        return command_class.removesuffix("-repeat")

    def run(
        self,
        command_class: str,
        argv: tuple[str, ...] | list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: float,
        output_budget_bytes: int,
    ) -> acceptance.CommandResult:
        del cwd, timeout_seconds, output_budget_bytes
        self.called_classes.append(command_class)
        self.calls.append((command_class, tuple(argv), dict(env)))
        base = self._base(command_class)
        if command_class in self.control_events:
            operation = (
                "outside-write" if command_class == "write-control" else "socket"
            )
            ledger = Path(env["FRIEND_LAB_LEDGER"])
            with ledger.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {"phase": command_class, "operation_class": operation},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        if self.extra_guard_after == command_class:
            ledger = Path(env["FRIEND_LAB_LEDGER"])
            with ledger.open("a", encoding="utf-8") as stream:
                stream.write(
                    '{"operation_class":"socket","phase":"unexpected"}\n'
                )
        if self.undeclared_after == command_class:
            Path(env["FRIEND_LAB_ROOT"], "undeclared.txt").write_text(
                "unexpected", encoding="utf-8"
            )
        default_status = 1 if (
            command_class in {"write-control", "socket-control", "reachability-probe"}
            or command_class.startswith("negative-")
        ) else 0
        status = self.exit_statuses.get(command_class, default_status)
        if status == 0 and command_class in {"source-install", "wheel-install"}:
            run_root = Path(env["FRIEND_LAB_ROOT"])
            environment = (
                "source-venv" if command_class == "source-install" else "wheel-venv"
            )
            installed = (
                run_root
                / environment
                / "lib/python3.12/site-packages/frontdoor"
            )
            shutil.copytree(run_root / "source/src/frontdoor", installed)
            if self.installed_private_after == command_class:
                (installed / "private_receiver.py").write_text(
                    "API_KEY=sk-privatevalue123\n", encoding="utf-8"
                )
        if base in self.nondeterministic_status and command_class.endswith(
            "-repeat"
        ):
            status = 1 if status == 0 else 2
        timed_out = command_class in self.timeouts
        if command_class in self.output_caps:
            status = -1
        marker = base.encode("ascii")
        if base in self.nondeterministic_stdout and command_class.endswith(
            "-repeat"
        ):
            marker += b"-changed"
        stderr = b""
        if base in self.nondeterministic_stderr and command_class.endswith(
            "-repeat"
        ):
            stderr = b"changed"
        return acceptance.CommandResult(
            command_class=command_class,
            exit_status=(-1 if timed_out else status),
            stdout_sha256=_sha256(marker),
            stderr_sha256=_sha256(stderr),
            timed_out=timed_out,
        )


@pytest.fixture
def acceptance_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> acceptance.AcceptanceRequest:
    outer_pack = tmp_path / "agent-frontdoor-friend-pack-0.2.0.tar.gz"
    outer_pack.write_bytes(b"synthetic verified outer pack")
    detached = tmp_path / "verify_handoff_archive.py"
    detached.write_bytes(b"#!/usr/bin/env python3\n")
    pack_root = tmp_path / PACK_ROOT_NAME
    pack_root.mkdir()

    source_entries = {
        "CHANGELOG.md": (b"# Changelog\n", 0o644),
        "LICENSE": (b"MIT\n", 0o644),
        "README.md": (b"# Agent Frontdoor\n", 0o644),
        "pyproject.toml": (
            b"[project]\nname='agent-frontdoor'\nversion='0.2.0'\n",
            0o644,
        ),
        "src/frontdoor/__init__.py": (b"__version__='0.2.0'\n", 0o644),
        "src/frontdoor/schema/intake.v0.json": (b"{}\n", 0o644),
        "tests/test_cli.py": (b"def test_ok(): assert True\n", 0o644),
        "tools/verify_handoff_archive.py": (detached.read_bytes(), 0o755),
        "fixtures/positive/01_install_only.json": (b"{}\n", 0o644),
    }
    source_data = _tar_gz(source_entries, SOURCE_ROOT_NAME)
    source_records = [
        _member(path, data, mode) for path, (data, mode) in sorted(source_entries.items())
    ]
    source_manifest = {
        "schema_version": "source-archive-manifest.v1",
        "package_version": "0.2.0",
        "public_revision": PUBLIC_REVISION,
        "archive_root": SOURCE_ROOT_NAME,
        "regular_file_count": len(source_records),
        "members": source_records,
    }
    wheel_versions = {
        "agent-frontdoor": "0.2.0",
        "attrs": "25.3.0",
        "iniconfig": "2.1.0",
        "jsonschema": "4.25.0",
        "jsonschema-specifications": "2025.4.1",
        "packaging": "25.0",
        "pluggy": "1.6.0",
        "pygments": "2.19.2",
        "pytest": "8.4.1",
        "referencing": "0.36.2",
        "rpds-py": "0.26.0",
        "setuptools": "80.9.0",
        "wheel": "0.45.1",
    }
    wheel_payloads: dict[str, bytes] = {}
    wheel_records: list[dict[str, object]] = []
    for name, version in sorted(wheel_versions.items()):
        if name == "rpds-py":
            tag = "cp312-cp312-macosx_11_0_arm64"
        else:
            tag = "py3-none-any"
        filename = f"{name.replace('-', '_')}-{version}-{tag}.whl"
        package_payloads = None
        if name == "agent-frontdoor":
            package_payloads = {
                path.removeprefix("src/"): data
                for path, (data, _mode) in source_entries.items()
                if path.startswith("src/frontdoor/")
            }
        data = _wheel_bytes(name, version, tag, package_payloads)
        wheel_payloads[filename] = data
        python_tag, abi_tag, platform_tag = tag.split("-")
        wheel_records.append(
            {
                "name": name,
                "version": version,
                "filename": filename,
                "size": len(data),
                "sha256": _sha256(data),
                "python_tags": [python_tag],
                "abi_tags": [abi_tag],
                "platform_tags": [platform_tag],
                "license_fields": ["License: MIT"],
                "requires_dist": ["jsonschema>=4"] if name == "agent-frontdoor" else [],
            }
        )
    wheel_manifest = {
        "schema_version": "wheelhouse-manifest.v1",
        "package_version": "0.2.0",
        "target": {
            "os_version": "macOS 26.5.2",
            "architecture": "arm64",
            "python_minor": "3.12",
            "abi_tag": "cp312",
            "platform_tags": ["macosx_11_0_arm64"],
            "pip_version": "25.1.1",
        },
        "wheels": wheel_records,
        "build_backend": {
            "name": "setuptools",
            "version": "80.9.0",
            "filename": "setuptools-80.9.0-py3-none-any.whl",
            "sha256": _sha256(
                wheel_payloads["setuptools-80.9.0-py3-none-any.whl"]
            ),
        },
    }
    payloads = {
        "FRIEND_LAB.md": b"# Friend Lab\n",
        f"source/{SOURCE_ROOT_NAME}.tar.gz": source_data,
        f"source/{SOURCE_ROOT_NAME}.tar.gz.sha256": (
            _sha256(source_data) + "\n"
        ).encode("ascii"),
        "source/source-manifest.json": _json_bytes(source_manifest),
        "verifier/verify_handoff_archive.py": detached.read_bytes(),
        "wheelhouse/wheelhouse-manifest.json": _json_bytes(wheel_manifest),
        "schemas/friend_acceptance_receipt.v1.json": (
            Path(acceptance.__file__).resolve().parents[2]
            / "schemas/friend_acceptance_receipt.v1.json"
        ).read_bytes(),
        "schemas/friend_pack_manifest.v1.json": b"{}\n",
        "schemas/source_archive_manifest.v1.json": b"{}\n",
        "schemas/wheelhouse_manifest.v1.json": b"{}\n",
        "lab/acceptance_runner.py": b"# runner\n",
        "lab/sitecustomize.py": b"# guard\n",
        "lab/controls/write_outside_probe.py": b"# write control\n",
        "lab/controls/socket_probe.py": b"# socket control\n",
        "lab/controls/privacy_control.txt": _privacy_control(),
    }
    payloads.update(
        {
            f"wheelhouse/{filename}": data
            for filename, data in wheel_payloads.items()
        }
    )
    executable = {
        "verifier/verify_handoff_archive.py",
        "lab/acceptance_runner.py",
        "lab/controls/write_outside_probe.py",
        "lab/controls/socket_probe.py",
    }
    for relative, data in payloads.items():
        path = pack_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755 if relative in executable else 0o644)
    records = [
        _member(relative, data, 0o755 if relative in executable else 0o644)
        for relative, data in sorted(payloads.items())
    ]
    manifest = {
        "schema_version": "friend-pack-manifest.v1",
        "package_version": "0.2.0",
        "public_revision": PUBLIC_REVISION,
        "source_archive": {
            "path": f"source/{SOURCE_ROOT_NAME}.tar.gz",
            "sha256": _sha256(source_data),
            "regular_file_count": len(source_records),
            "manifest_path": "source/source-manifest.json",
        },
        "verifier": {
            "path": "verifier/verify_handoff_archive.py",
            "sha256": _sha256(detached.read_bytes()),
        },
        "privacy_control": {
            "path": "lab/controls/privacy_control.txt",
            "sha256": _sha256(_privacy_control()),
        },
        "self_exclusions": ["manifest.json", "manifest.sha256"],
        "members": records,
    }
    manifest_data = _json_bytes(manifest)
    (pack_root / "manifest.json").write_bytes(manifest_data)
    (pack_root / "manifest.sha256").write_text(
        _sha256(manifest_data) + "\n", encoding="ascii"
    )
    monkeypatch.setattr(
        acceptance,
        "verify_friend_pack",
        lambda *args, **kwargs: SimpleNamespace(ok=True, errors=()),
    )
    return acceptance.AcceptanceRequest(
        pack_path=outer_pack,
        detached_verifier_path=detached,
        pack_root=pack_root,
        run_root=tmp_path / "run",
        expected_pack_sha256=_sha256(outer_pack.read_bytes()),
        expected_source_sha256=_sha256(source_data),
        expected_verifier_sha256=_sha256(detached.read_bytes()),
        execution_mode="local",
        verifier_role="receiver-human",
        network_disconnected_confirmed=True,
    )


def test_happy_local_flow_writes_schema_valid_receipt(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "PRIVATE_HANDOFF_READY"
    assert receipt["collected_test_count"] == 571
    assert receipt["controls"]["post_control_socket_events"] == 0
    assert receipt["controls"]["post_control_write_events"] == 0
    receipt_path = acceptance_request.run_root / "friend-acceptance-receipt.json"
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt
    schema = json.loads(
        (acceptance_request.pack_root / "schemas/friend_acceptance_receipt.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert not tuple(Draft202012Validator(schema).iter_errors(receipt))


def test_source_install_requests_test_extra_before_pytest_collection(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()

    acceptance.run_acceptance(acceptance_request, command_runner=fake)

    source_install = next(
        argv for command_class, argv, _env in fake.calls
        if command_class == "source-install"
    )
    assert source_install[-1].endswith("/source[test]")
    assert fake.called_classes.index("source-install") < fake.called_classes.index(
        "test-collect"
    )


def test_core_acceptance_excludes_optional_adapter_runtime_tests(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()

    acceptance.run_acceptance(acceptance_request, command_runner=fake)

    excluded = {
        "--ignore=tests/test_hook_adapter.py",
        "--ignore=tests/test_hook_fixtures.py",
        "--ignore=tests/test_hook_state.py",
    }
    for command_class in ("test-collect", "tests", "wheel-tests"):
        argv = next(
            argv
            for called_class, argv, _env in fake.calls
            if called_class == command_class
        )
        assert excluded.issubset(argv)


def test_isolated_environment_does_not_forward_receiver_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    pack_root = tmp_path / "pack"
    run_root.mkdir()
    pack_root.mkdir()
    ledger = run_root / "audit.jsonl"
    ledger.write_bytes(b"")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross-boundary")
    monkeypatch.setenv("GH_TOKEN", "must-not-cross-boundary")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/private/receiver/agent.sock")
    monkeypatch.setenv("PYTHONSTARTUP", "/private/receiver/startup.py")

    env = acceptance._create_isolated_environment(run_root, pack_root, ledger)

    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "GH_TOKEN" not in env
    assert "SSH_AUTH_SOCK" not in env
    assert "PYTHONSTARTUP" not in env
    assert env["PATH"] == os.defpath
    assert env["HOME"].startswith(str(run_root))


def test_remote_flow_is_capped_with_gap(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    acceptance_request = replace(acceptance_request, execution_mode="remote")
    receipt = acceptance.run_acceptance(acceptance_request, command_runner=FakeRunner())

    assert receipt["final_classification"] == "PRIVATE_HANDOFF_READY_WITH_GAPS"
    assert "REMOTE_EXECUTION" in receipt["gaps"]
    assert receipt["controls"]["network_disconnect"] == "REMOTE_UNAVAILABLE"


@pytest.mark.parametrize("execution_mode", ["remote", "local"])
def test_reachable_network_is_a_gap_when_disconnect_was_not_confirmed(
    acceptance_request: acceptance.AcceptanceRequest,
    execution_mode: str,
) -> None:
    acceptance_request = replace(
        acceptance_request,
        execution_mode=execution_mode,
        network_disconnected_confirmed=False,
    )
    fake = FakeRunner()
    fake.exit_statuses["reachability-probe"] = 0

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "PRIVATE_HANDOFF_READY_WITH_GAPS"
    assert "source-venv" in fake.called_classes


def test_missing_out_of_band_equality_stops_before_controls(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    acceptance_request = replace(acceptance_request, expected_source_sha256="f" * 64)
    fake = FakeRunner()

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert receipt["digest_equality"]["source"] is False
    assert fake.called_classes == []


@pytest.mark.parametrize(
    "mutation",
    ["missing-closure", "rpds-platform", "backend-hash", "private-target"],
)
def test_invalid_wheelhouse_semantics_stop_before_controls(
    acceptance_request: acceptance.AcceptanceRequest,
    mutation: str,
) -> None:
    relative = "wheelhouse/wheelhouse-manifest.json"
    wheel_manifest = json.loads(
        (acceptance_request.pack_root / relative).read_text(encoding="utf-8")
    )
    if mutation == "missing-closure":
        wheel_manifest["wheels"] = [
            item for item in wheel_manifest["wheels"] if item["name"] != "referencing"
        ]
    elif mutation == "rpds-platform":
        rpds = next(
            item for item in wheel_manifest["wheels"] if item["name"] == "rpds-py"
        )
        rpds["platform_tags"] = ["manylinux_2_17_aarch64"]
    elif mutation == "backend-hash":
        wheel_manifest["build_backend"]["sha256"] = "f" * 64
    else:
        wheel_manifest["target"]["os_version"] = "/Users/private/machine"
    _replace_pack_payload(
        acceptance_request.pack_root,
        relative,
        _json_bytes(wheel_manifest),
    )
    fake = FakeRunner()

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert fake.called_classes == []


@pytest.mark.parametrize(
    ("member", "payload"),
    [
        ("frontdoor/__init__.py", b"__version__='0.2.1'\n"),
        ("frontdoor/private_receiver.py", b"API_KEY=sk-privatevalue123\n"),
        (
            "agent_frontdoor-0.2.0.dist-info/METADATA",
            b"Metadata-Version: 2.1\nName: agent-frontdoor\nVersion: 0.2.0\nLicense: MIT\nRequires-Dist: jsonschema>=4\nrequires-dist: evil-package\n",
        ),
    ],
)
def test_unbound_or_private_agent_wheel_stops_before_controls(
    acceptance_request: acceptance.AcceptanceRequest,
    member: str,
    payload: bytes,
) -> None:
    wheel_manifest = json.loads(
        (
            acceptance_request.pack_root
            / "wheelhouse/wheelhouse-manifest.json"
        ).read_text(encoding="utf-8")
    )
    filename = next(
        item["filename"]
        for item in wheel_manifest["wheels"]
        if item["name"] == "agent-frontdoor"
    )
    _replace_wheel_member(
        acceptance_request.pack_root, filename, member, payload
    )
    fake = FakeRunner()

    receipt = acceptance.run_acceptance(
        acceptance_request, command_runner=fake
    )

    assert receipt["final_classification"] == "NOT_READY"
    assert fake.called_classes == []


def test_private_installed_package_stops_before_tests(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.installed_private_after = "wheel-install"

    receipt = acceptance.run_acceptance(
        acceptance_request, command_runner=fake
    )

    assert receipt["final_classification"] == "NOT_READY"
    assert "test-collect" not in fake.called_classes


def test_write_control_not_firing_stops_before_socket_control(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.control_events.remove("write-control")

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert fake.called_classes == ["write-control"]


def test_socket_control_not_firing_stops_before_reachability(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.control_events.remove("socket-control")

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert fake.called_classes == ["write-control", "socket-control"]


def test_successful_reachability_with_disconnect_claim_stops_before_venv(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.exit_statuses["reachability-probe"] = 0

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "source-venv" not in fake.called_classes


@pytest.mark.parametrize(
    ("failed_class", "forbidden_later"),
    [
        ("source-install", {"wheel-install", "tests"}),
        ("wheel-install", {"tests", "sample-validate"}),
        ("tests", {"sample-validate", "negative-deploy"}),
    ],
)
def test_positive_phase_failure_stops_later_phases(
    acceptance_request: acceptance.AcceptanceRequest,
    failed_class: str,
    forbidden_later: set[str],
) -> None:
    fake = FakeRunner()
    fake.exit_statuses[failed_class] = 1

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert forbidden_later.isdisjoint(fake.called_classes)


def test_missing_collected_test_count_stops_before_samples(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.collected_test_count = 0

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "sample-validate" not in fake.called_classes
    assert "INCOMPLETE_EVIDENCE" in receipt["gaps"]


def test_negative_fixture_unexpected_zero_stops_next_negative(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.exit_statuses["negative-deploy"] = 0

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "negative-scheduler" not in fake.called_classes


@pytest.mark.parametrize(
    "field",
    [
        "nondeterministic_stdout",
        "nondeterministic_stderr",
        "nondeterministic_status",
    ],
)
def test_nondeterministic_result_stops_before_privacy_scan(
    acceptance_request: acceptance.AcceptanceRequest,
    field: str,
) -> None:
    fake = FakeRunner()
    getattr(fake, field).add("sample-validate")

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "privacy-scan" not in fake.called_classes


def test_privacy_control_miss_stops_before_commands(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    control = acceptance_request.pack_root / "lab/controls/privacy_control.txt"
    control.write_text("not a complete control\n", encoding="utf-8")
    manifest = json.loads((acceptance_request.pack_root / "manifest.json").read_text())
    for item in manifest["members"]:
        if item["path"] == "lab/controls/privacy_control.txt":
            item.update(_member(item["path"], control.read_bytes()))
    manifest["privacy_control"]["sha256"] = _sha256(control.read_bytes())
    manifest_data = _json_bytes(manifest)
    (acceptance_request.pack_root / "manifest.json").write_bytes(manifest_data)
    (acceptance_request.pack_root / "manifest.sha256").write_text(
        _sha256(manifest_data) + "\n", encoding="ascii"
    )
    fake = FakeRunner()

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert fake.called_classes == []


def test_new_guard_event_after_baseline_stops_before_uninstall(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.extra_guard_after = "static-scan"

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "source-uninstall" not in fake.called_classes


def test_undeclared_file_creation_stops_before_uninstall(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.undeclared_after = "static-scan"

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "source-uninstall" not in fake.called_classes


def test_uninstall_leaving_cli_stops_second_uninstall(
    acceptance_request: acceptance.AcceptanceRequest,
) -> None:
    fake = FakeRunner()
    fake.exit_statuses["source-cli-absent"] = 1

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "wheel-uninstall" not in fake.called_classes
    assert receipt["uninstall_result"] == "FAIL"


def test_receipt_write_failure_returns_not_ready_without_retry(
    acceptance_request: acceptance.AcceptanceRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRunner()
    calls = 0

    def fail_write(path: Path, data: bytes) -> None:
        nonlocal calls
        del path, data
        calls += 1
        raise OSError("synthetic receipt failure")

    monkeypatch.setattr(acceptance, "_atomic_write_receipt", fail_write)
    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert "INCOMPLETE_EVIDENCE" in receipt["gaps"]
    assert calls == 1


def test_receipt_validation_stays_strict_without_host_jsonschema(
    acceptance_request: acceptance.AcceptanceRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = acceptance.run_acceptance(
        acceptance_request, command_runner=FakeRunner()
    )
    receipt["final_classification"] = "INVALID"
    real_import = builtins.__import__

    def no_jsonschema(name: str, *args: object, **kwargs: object) -> object:
        if name == "jsonschema" or name.startswith("jsonschema."):
            raise ImportError("synthetic missing jsonschema")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_jsonschema)

    with pytest.raises(acceptance.AcceptanceError, match="schema validation"):
        acceptance._validate_receipt(
            receipt,
            acceptance_request.pack_root
            / "schemas/friend_acceptance_receipt.v1.json",
        )


@pytest.mark.parametrize(
    ("failure_kind", "field"),
    [("timeout", "timeouts"), ("cap", "output_caps")],
)
def test_bounded_command_failure_stops_after_one_attempt(
    acceptance_request: acceptance.AcceptanceRequest,
    failure_kind: str,
    field: str,
) -> None:
    del failure_kind
    fake = FakeRunner()
    getattr(fake, field).add("source-install")

    receipt = acceptance.run_acceptance(acceptance_request, command_runner=fake)

    assert receipt["final_classification"] == "NOT_READY"
    assert fake.called_classes.count("source-install") == 1
    assert "wheel-install" not in fake.called_classes


def test_packaged_runner_loads_without_canonical_tools_package(
    tmp_path: Path,
) -> None:
    pack = tmp_path / PACK_ROOT_NAME
    lab = pack / "lab"
    verifier = pack / "verifier"
    lab.mkdir(parents=True)
    verifier.mkdir()
    shutil.copy2(Path(acceptance.__file__), lab / "acceptance_runner.py")
    source_verifier = Path(acceptance.__file__).resolve().parents[1] / (
        "verify_handoff_archive.py"
    )
    shutil.copy2(source_verifier, verifier / "verify_handoff_archive.py")
    env = dict(os.environ)
    env["PYTHONPATH"] = ""

    result = subprocess.run(
        (sys.executable, str(lab / "acceptance_runner.py"), "--help"),
        cwd=pack,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert "--expected-pack-sha256" in result.stdout


def test_bounded_runner_kills_timed_out_process_group(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    runner = acceptance.BoundedCommandRunner(
        run_root, terminate_grace_seconds=0.05
    )

    result = runner.run(
        "timeout-control",
        (sys.executable, "-c", "import time; time.sleep(30)"),
        cwd=run_root,
        env=dict(os.environ),
        timeout_seconds=0.05,
        output_budget_bytes=1024,
    )

    assert result.timed_out is True
    assert result.exit_status == -1
    assert len(tuple((run_root / "evidence").glob("*.stdout"))) == 1
    assert len(tuple((run_root / "evidence").glob("*.stderr"))) == 1


def test_bounded_runner_kills_sigterm_ignoring_descendant_with_pipes(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    runner = acceptance.BoundedCommandRunner(
        run_root, terminate_grace_seconds=0.05
    )
    child_code = (
        "import signal,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "print('child-ready', flush=True); "
        "time.sleep(2)"
    )
    leader_code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        "time.sleep(30)"
    )

    started = time.monotonic()
    result = runner.run(
        "descendant-timeout-control",
        (sys.executable, "-c", leader_code),
        cwd=run_root,
        env=dict(os.environ),
        timeout_seconds=0.05,
        output_budget_bytes=1024,
    )
    elapsed = time.monotonic() - started

    assert result.timed_out is True
    assert result.exit_status == -1
    assert elapsed < 0.75


def test_bounded_runner_kills_at_output_cap(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    runner = acceptance.BoundedCommandRunner(
        run_root, terminate_grace_seconds=0.05
    )

    result = runner.run(
        "output-cap-control",
        (sys.executable, "-c", "import os; os.write(1, b'x' * 200000)"),
        cwd=run_root,
        env=dict(os.environ),
        timeout_seconds=5,
        output_budget_bytes=1024,
    )

    assert result.timed_out is False
    assert result.exit_status == -1
    stdout = next((run_root / "evidence").glob("*.stdout"))
    assert stdout.stat().st_size == 1024
