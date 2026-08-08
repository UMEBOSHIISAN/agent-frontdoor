"""Distribution contract for the public intent-lock schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "src" / "frontdoor" / "schema" / "intent-lock.v1.json"


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_intent_lock_schema_is_valid_and_closed() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "intent_epoch",
        "source_prompt_sha256",
        "phase",
        "mode",
        "exact_command_sha256",
        "target_token_sha256",
        "display_targets",
        "pending_tool_use_sha256",
    }


def test_intent_lock_schema_exposes_only_the_public_modes_and_phases() -> None:
    properties = _schema()["properties"]
    assert properties["schema_version"]["const"] == "intent-lock.v1"
    assert properties["mode"]["enum"] == ["EXACT_COMMAND", "LITERAL_TARGET"]
    assert properties["phase"]["enum"] == [
        "DIRECT_REQUIRED",
        "REPORT_REQUIRED",
        "RELEASED",
    ]
    assert properties["source_prompt_sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert properties["target_token_sha256"]["items"]["pattern"] == (
        "^[0-9a-f]{64}$"
    )


def test_exact_command_mode_requires_a_hash_and_literal_target_requires_null() -> None:
    validator = Draft202012Validator(_schema())
    base = {
        "schema_version": "intent-lock.v1",
        "intent_epoch": 1,
        "source_prompt_sha256": "a" * 64,
        "phase": "DIRECT_REQUIRED",
        "target_token_sha256": ["b" * 64],
        "display_targets": ["cloudflare-api"],
        "pending_tool_use_sha256": None,
    }

    assert not list(
        validator.iter_errors(
            {**base, "mode": "EXACT_COMMAND", "exact_command_sha256": "c" * 64}
        )
    )
    assert list(
        validator.iter_errors(
            {**base, "mode": "EXACT_COMMAND", "exact_command_sha256": None}
        )
    )
    assert not list(
        validator.iter_errors(
            {**base, "mode": "LITERAL_TARGET", "exact_command_sha256": None}
        )
    )
    assert list(
        validator.iter_errors(
            {**base, "mode": "LITERAL_TARGET", "exact_command_sha256": "c" * 64}
        )
    )


def test_core_distribution_declares_all_public_schemas_as_package_data() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'frontdoor = ["schema/*.json"]' in pyproject
