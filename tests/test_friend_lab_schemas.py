from __future__ import annotations

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
SCHEMA_PATHS = {
    "receipt": SCHEMAS / "friend_acceptance_receipt.v1.json",
    "friend_pack": SCHEMAS / "friend_pack_manifest.v1.json",
    "source": SCHEMAS / "source_archive_manifest.v1.json",
    "wheelhouse": SCHEMAS / "wheelhouse_manifest.v1.json",
}
HEX = "a" * 64
REVISION = "b" * 40


def load_schema(name: str) -> dict[str, object] | None:
    path = SCHEMA_PATHS[name]
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def member(path: str = "README.md") -> dict[str, object]:
    return {"path": path, "mode": 420, "size": 1, "sha256": HEX}


def valid_source_manifest() -> dict[str, object]:
    return {
        "schema_version": "source-archive-manifest.v1",
        "package_version": "0.2.0",
        "public_revision": REVISION,
        "archive_root": "agent-frontdoor-0.2.0",
        "regular_file_count": 1,
        "members": [member()],
    }


def valid_friend_pack_manifest() -> dict[str, object]:
    return {
        "schema_version": "friend-pack-manifest.v1",
        "package_version": "0.2.0",
        "public_revision": REVISION,
        "source_archive": {
            "path": "source/agent-frontdoor-0.2.0.tar.gz",
            "sha256": HEX,
            "regular_file_count": 1,
            "manifest_path": "source/source-manifest.json",
        },
        "verifier": {
            "path": "verifier/verify_handoff_archive.py",
            "sha256": HEX,
        },
        "privacy_control": {
            "path": "lab/controls/privacy_control.txt",
            "sha256": HEX,
        },
        "self_exclusions": ["manifest.json", "manifest.sha256"],
        "members": [member("FRIEND_LAB.md")],
    }


def valid_wheelhouse_manifest() -> dict[str, object]:
    return {
        "schema_version": "wheelhouse-manifest.v1",
        "package_version": "0.2.0",
        "target": {
            "os_version": "macOS 26.5.2",
            "architecture": "arm64",
            "python_minor": "3.14",
            "abi_tag": "cp314",
            "platform_tags": ["macosx_11_0_arm64"],
            "pip_version": "26.1.1",
        },
        "wheels": [
            {
                "name": "jsonschema",
                "version": "4.25.1",
                "filename": "jsonschema-4.25.1-py3-none-any.whl",
                "size": 1,
                "sha256": HEX,
                "python_tags": ["py3"],
                "abi_tags": ["none"],
                "platform_tags": ["any"],
                "license_fields": ["MIT"],
                "requires_dist": ["attrs>=22.2.0"],
            }
        ],
        "build_backend": {
            "name": "setuptools",
            "version": "80.9.0",
            "filename": "setuptools-80.9.0-py3-none-any.whl",
            "sha256": HEX,
        },
    }


def valid_receipt() -> dict[str, object]:
    return {
        "schema_version": "friend-acceptance-receipt.v1",
        "package_version": "0.2.0",
        "public_revision": REVISION,
        "pack_sha256": HEX,
        "source_archive_sha256": HEX,
        "source_manifest_sha256": HEX,
        "verifier_sha256": HEX,
        "platform": {
            "os_version": "macOS 26.5.2",
            "architecture": "arm64",
            "python_version": "3.14.6",
            "pip_version": "26.1.1",
        },
        "digest_equality": {
            "pack": True,
            "source": True,
            "verifier": True,
        },
        "controls": {
            "network_disconnect": "CONFIRMED",
            "socket_guard": "PASS",
            "write_guard": "PASS",
            "privacy_scan": "PASS",
            "secret_scan": "PASS",
            "post_control_socket_events": 0,
            "post_control_write_events": 0,
        },
        "steps": [
            {
                "phase": "verify-pack",
                "command_class": "verify-pack",
                "exit_status": 0,
                "result": "PASS",
                "stdout_sha256": HEX,
                "stderr_sha256": HEX,
            }
        ],
        "collected_test_count": 507,
        "deterministic_output_hashes": [
            {
                "command_class": "sample-validate",
                "exit_status": 0,
                "stdout_sha256": HEX,
                "stderr_sha256": HEX,
            }
        ],
        "uninstall_result": "PASS",
        "final_classification": "PRIVATE_HANDOFF_READY",
        "verifier_role": "receiver-human",
        "gaps": [],
    }


VALID_OBJECTS = {
    "receipt": valid_receipt,
    "friend_pack": valid_friend_pack_manifest,
    "source": valid_source_manifest,
    "wheelhouse": valid_wheelhouse_manifest,
}


@pytest.mark.parametrize("name", sorted(SCHEMA_PATHS))
def test_schema_is_valid_draft_2020_12_and_accepts_minimal_object(
    name: str,
) -> None:
    schema = load_schema(name)
    assert schema is not None, f"missing schema: {SCHEMA_PATHS[name]}"
    Draft202012Validator.check_schema(schema)

    errors = tuple(
        Draft202012Validator(schema).iter_errors(VALID_OBJECTS[name]())
    )
    assert errors == ()


@pytest.mark.parametrize(
    ("name", "package_version", "versioned_member"),
    [
        ("receipt", "0.1.0", None),
        ("receipt", "0.2.0", None),
        (
            "friend_pack",
            "0.1.0",
            "source/agent-frontdoor-0.1.0.tar.gz",
        ),
        (
            "friend_pack",
            "0.2.0",
            "source/agent-frontdoor-0.2.0.tar.gz",
        ),
        ("source", "0.1.0", "agent-frontdoor-0.1.0"),
        ("source", "0.2.0", "agent-frontdoor-0.2.0"),
        ("wheelhouse", "0.1.0", None),
        ("wheelhouse", "0.2.0", None),
    ],
)
def test_v1_schema_accepts_each_development_candidate(
    name: str,
    package_version: str,
    versioned_member: str | None,
) -> None:
    schema = load_schema(name)
    assert schema is not None
    value = VALID_OBJECTS[name]()
    value["package_version"] = package_version
    if name == "friend_pack":
        value["source_archive"]["path"] = versioned_member
    elif name == "source":
        value["archive_root"] = versioned_member

    assert tuple(Draft202012Validator(schema).iter_errors(value)) == ()


@pytest.mark.parametrize(
    ("package_version", "source_path"),
    [
        ("0.1.0", "source/agent-frontdoor-0.2.0.tar.gz"),
        ("0.2.0", "source/agent-frontdoor-0.1.0.tar.gz"),
    ],
)
def test_friend_pack_rejects_mismatched_version_and_source_path(
    package_version: str,
    source_path: str,
) -> None:
    schema = load_schema("friend_pack")
    assert schema is not None
    manifest = valid_friend_pack_manifest()
    manifest["package_version"] = package_version
    manifest["source_archive"]["path"] = source_path

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))


@pytest.mark.parametrize(
    ("package_version", "archive_root"),
    [
        ("0.1.0", "agent-frontdoor-0.2.0"),
        ("0.2.0", "agent-frontdoor-0.1.0"),
    ],
)
def test_source_manifest_rejects_mismatched_version_and_archive_root(
    package_version: str,
    archive_root: str,
) -> None:
    schema = load_schema("source")
    assert schema is not None
    manifest = valid_source_manifest()
    manifest["package_version"] = package_version
    manifest["archive_root"] = archive_root

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))


@pytest.mark.parametrize(
    ("name", "versioned_member"),
    [
        ("receipt", None),
        ("friend_pack", "source/agent-frontdoor-0.3.0.tar.gz"),
        ("source", "agent-frontdoor-0.3.0"),
        ("wheelhouse", None),
    ],
)
def test_v1_schema_rejects_unknown_package_version(
    name: str,
    versioned_member: str | None,
) -> None:
    schema = load_schema(name)
    assert schema is not None
    value = VALID_OBJECTS[name]()
    value["package_version"] = "0.3.0"
    if name == "friend_pack":
        value["source_archive"]["path"] = versioned_member
    elif name == "source":
        value["archive_root"] = versioned_member

    assert tuple(Draft202012Validator(schema).iter_errors(value))


@pytest.mark.parametrize(
    ("name", "schema_version"),
    [
        ("receipt", "friend-acceptance-receipt.v2"),
        ("friend_pack", "friend-pack-manifest.v2"),
        ("source", "source-archive-manifest.v2"),
        ("wheelhouse", "wheelhouse-manifest.v2"),
    ],
)
def test_v1_schema_rejects_other_schema_version(
    name: str,
    schema_version: str,
) -> None:
    schema = load_schema(name)
    assert schema is not None
    value = VALID_OBJECTS[name]()
    value["schema_version"] = schema_version

    assert tuple(Draft202012Validator(schema).iter_errors(value))


def object_schemas(value: object):
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield value
        for child in value.values():
            yield from object_schemas(child)
    elif isinstance(value, list):
        for child in value:
            yield from object_schemas(child)


@pytest.mark.parametrize("name", sorted(SCHEMA_PATHS))
def test_every_object_boundary_is_closed(name: str) -> None:
    schema = load_schema(name)
    assert schema is not None, f"missing schema: {SCHEMA_PATHS[name]}"
    objects = tuple(object_schemas(schema))
    assert objects
    assert all(item.get("additionalProperties") is False for item in objects)


def test_receipt_rejects_receiver_identity() -> None:
    schema = load_schema("receipt")
    assert schema is not None
    receipt = valid_receipt()
    receipt["hostname"] = "private-host"

    assert tuple(Draft202012Validator(schema).iter_errors(receipt))


@pytest.mark.parametrize(
    "classification",
    ["READY", "VERIFIED", "PUBLIC_RELEASE_READY", ""],
)
def test_receipt_rejects_unknown_classification(classification: str) -> None:
    schema = load_schema("receipt")
    assert schema is not None
    receipt = valid_receipt()
    receipt["final_classification"] = classification

    assert tuple(Draft202012Validator(schema).iter_errors(receipt))


@pytest.mark.parametrize(
    "role", ["producer", "vendor-codex", "friend", ""]
)
def test_receipt_rejects_unknown_verifier_role(role: str) -> None:
    schema = load_schema("receipt")
    assert schema is not None
    receipt = valid_receipt()
    receipt["verifier_role"] = role

    assert tuple(Draft202012Validator(schema).iter_errors(receipt))


def test_receipt_rejects_missing_hash() -> None:
    schema = load_schema("receipt")
    assert schema is not None
    receipt = valid_receipt()
    del receipt["source_archive_sha256"]

    assert tuple(Draft202012Validator(schema).iter_errors(receipt))


def test_receipt_rejects_raw_command_and_output_fields() -> None:
    schema = load_schema("receipt")
    assert schema is not None
    receipt = valid_receipt()
    receipt["steps"][0]["command"] = "private command"
    receipt["steps"][0]["stdout"] = "private output"

    assert tuple(Draft202012Validator(schema).iter_errors(receipt))


def test_friend_pack_rejects_widened_self_exclusions() -> None:
    schema = load_schema("friend_pack")
    assert schema is not None
    manifest = valid_friend_pack_manifest()
    manifest["self_exclusions"].append("private.txt")

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))


@pytest.mark.parametrize("name", ["source", "friend_pack"])
def test_member_manifest_rejects_traversal_and_extra_fields(name: str) -> None:
    schema = load_schema(name)
    assert schema is not None
    manifest = VALID_OBJECTS[name]()
    manifest["members"][0]["path"] = "../escape"
    manifest["members"][0]["owner"] = "private"

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))


def test_source_manifest_duplicate_path_is_rejected_semantically() -> None:
    schema = load_schema("source")
    assert schema is not None
    manifest = valid_source_manifest()
    second = deepcopy(manifest["members"][0])
    second["mode"] = 384
    manifest["members"].append(second)
    manifest["regular_file_count"] = 2
    assert tuple(Draft202012Validator(schema).iter_errors(manifest)) == ()

    sys.path.insert(0, str(ROOT / "tools"))
    verifier = importlib.import_module("verify_handoff_archive")
    _records, _count, _root, errors = verifier._load_source_manifest_bytes(
        (json.dumps(manifest) + "\n").encode("utf-8")
    )
    assert "source manifest member paths not unique" in errors


def test_wheelhouse_requires_exact_setuptools_hash() -> None:
    schema = load_schema("wheelhouse")
    assert schema is not None
    manifest = valid_wheelhouse_manifest()
    manifest["build_backend"] = {
        "name": "setuptools",
        "version": "80.9.0",
    }

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))


@pytest.mark.parametrize(
    "filename",
    ["setuptools-80.9.0.tar.gz", "package-1.0.zip", "package.whl.txt"],
)
def test_wheelhouse_rejects_sdist_or_nonwheel(filename: str) -> None:
    schema = load_schema("wheelhouse")
    assert schema is not None
    manifest = valid_wheelhouse_manifest()
    manifest["wheels"][0]["filename"] = filename

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))


def test_wheelhouse_rejects_target_extra_property() -> None:
    schema = load_schema("wheelhouse")
    assert schema is not None
    manifest = valid_wheelhouse_manifest()
    manifest["target"]["hostname"] = "private-host"

    assert tuple(Draft202012Validator(schema).iter_errors(manifest))
