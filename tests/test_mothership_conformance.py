from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath

from frontdoor.cli import main
from frontdoor.formatter import format_card, format_explanation
from frontdoor.validator import load_card
from jsonschema import Draft202012Validator
import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "suite/mothership-0.2-conformance.json"
EXAMPLE = ROOT / "examples/mothership-task.json"
SCHEMA = ROOT / "src/frontdoor/schema/intake.v0.json"
EXPECTED_KEYS = {
    "schema_version",
    "suite_release",
    "repository",
    "protocol_kind",
    "protocol_version",
    "schema_path",
    "schema_sha256",
    "example_path",
    "authority_effect",
    "execution_effect",
}


def _validate_manifest(document: object) -> None:
    assert type(document) is dict
    assert set(document) == EXPECTED_KEYS
    assert document["schema_version"] == "mothership.conformance.v1"
    assert document["suite_release"] == "0.2.0"
    assert document["repository"] == "agent-frontdoor"
    assert document["protocol_kind"] == "frontdoor-task"
    assert document["protocol_version"] == "intake.v0"
    assert document["schema_path"] == "src/frontdoor/schema/intake.v0.json"
    assert document["example_path"] == "examples/mothership-task.json"
    assert document["authority_effect"] is False
    assert document["execution_effect"] is False
    for name in ("schema_path", "example_path"):
        value = document[name]
        assert type(value) is str
        parsed = PurePosixPath(value)
        assert not parsed.is_absolute()
        assert parsed.as_posix() == value
        assert all(part not in ("", ".", "..") for part in parsed.parts)
        assert (ROOT / value).is_file()
    digest = document["schema_sha256"]
    assert type(digest) is str
    assert digest == hashlib.sha256(SCHEMA.read_bytes()).hexdigest()


def test_closed_manifest_binds_owner_schema_and_example() -> None:
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    _validate_manifest(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("repository", "mothership"),
        ("protocol_kind", "governance-handoff"),
        ("protocol_version", "1.0"),
        ("schema_path", "../intake.v0.json"),
        ("example_path", "examples/missing.json"),
        ("schema_sha256", "0" * 64),
        ("authority_effect", True),
        ("execution_effect", True),
    ),
)
def test_manifest_contract_rejects_drift(field: str, value: object) -> None:
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    manifest[field] = value
    with pytest.raises(AssertionError):
        _validate_manifest(manifest)


def test_manifest_contract_rejects_unknown_fields() -> None:
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    manifest["extra"] = "not-allowed"
    with pytest.raises(AssertionError):
        _validate_manifest(manifest)


def test_synthetic_card_passes_owner_schema_and_production_validator() -> None:
    document = json.loads(EXAMPLE.read_text("utf-8"))
    schema = json.loads(SCHEMA.read_text("utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(document)) == []

    loaded, result = load_card(EXAMPLE)
    assert loaded == document
    assert result.valid
    assert result.issues == ()
    assert document["request_id"] == "demo-review-001"
    assert document["predicted_worker_capability"] == "code-review"


def test_cli_and_renderers_preserve_preflight_only_ownership(capsys) -> None:
    assert main(["validate", str(EXAMPLE)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "VALID demo-review-001\n"
    assert captured.err == ""

    document = json.loads(EXAMPLE.read_text("utf-8"))
    original = deepcopy(document)
    for output in (format_card(document), format_explanation(document)):
        assert "demo-review-001" in output
        for forbidden in (
            "authority_effect",
            "execution_effect",
            "protocol_kind",
            "suite_release",
            "schema_sha256",
        ):
            assert forbidden not in output
    assert document == original
