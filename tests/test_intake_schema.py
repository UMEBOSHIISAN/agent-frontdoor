"""Contract tests for the Agent Frontdoor v0 intake schema."""

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema" / "intake.v0.json"

EXPECTED_CORE_FIELDS = {
    "schema_version",
    "request_id",
    "human_request",
    "task_class",
    "risk_tags",
    "allowed_actions",
    "forbidden_actions",
    "required_evidence",
    "required_manifest",
    "human_gate",
    "predicted_worker_capability",
    "unknowns",
    "assumptions",
    "next_safe_step",
}

EXPECTED_TASK_CLASSES = [
    "RESEARCH",
    "DESIGN_REVIEW",
    "IMPLEMENTATION",
    "CODE_REVIEW",
    "AUDIT",
    "CONTENT_DRAFT",
    "DATA_ANALYSIS",
    "INSTALLATION",
    "OPERATIONS",
    "UNKNOWN",
]

EXPECTED_CAPABILITIES = [
    "research",
    "design-review",
    "implementation",
    "code-review",
    "audit",
    "content-draft",
    "data-analysis",
    "installation",
    "operations",
    "none-until-clarified",
]

EXPECTED_RISK_TAGS = [
    "deploy",
    "production",
    "scheduler",
    "secret",
    "auth",
    "billing",
    "delete",
    "destructive_cleanup",
    "ssot_mutation",
    "external_publish",
    "authority_promotion",
    "cleanup_adjacent",
    "scope_drift",
    "unknown",
]


@pytest.fixture(scope="module")
def schema():
    if not SCHEMA_PATH.exists():
        return None
    return json.loads(SCHEMA_PATH.read_text())


def test_intake_schema_has_exact_core_contract(schema):
    assert schema is not None, f"missing intake schema: {SCHEMA_PATH}"
    assert schema["properties"]["schema_version"]["const"] == "intake.v0"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == EXPECTED_CORE_FIELDS
    assert schema["properties"]["task_class"]["enum"] == EXPECTED_TASK_CLASSES
    assert schema["properties"]["human_gate"]["enum"] == [
        "NONE",
        "CONFIRM",
        "BLOCKING",
    ]
    assert (
        schema["properties"]["predicted_worker_capability"]["enum"]
        == EXPECTED_CAPABILITIES
    )
    assert schema["properties"]["risk_tags"]["items"]["enum"] == EXPECTED_RISK_TAGS

    for field in ("request_id", "human_request", "next_safe_step"):
        assert schema["properties"][field]["minLength"] == 1

    for field in ("allowed_actions", "forbidden_actions"):
        assert schema["properties"][field]["minItems"] == 1
        assert schema["properties"][field]["items"]["type"] == "string"

    manifest_options = schema["properties"]["required_manifest"]["oneOf"]
    assert {option["type"] for option in manifest_options} == {"null", "string"}
    string_manifest = next(
        option for option in manifest_options if option["type"] == "string"
    )
    assert string_manifest["minLength"] == 1

    for field in ("required_evidence", "unknowns", "assumptions"):
        assert schema["properties"][field]["type"] == "array"
        assert schema["properties"][field]["items"]["type"] == "string"
