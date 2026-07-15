"""Schema validation tests for agent-frontdoor v0.1.

Tests that:
- the schema itself is structurally correct
- all valid fixtures pass validation
- structural rules (required fields, enum values, additionalProperties) are enforced
"""
import json
import pathlib
import pytest
import jsonschema

ROOT = pathlib.Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema" / "agent-frontdoor.v0.1.json"
FIXTURES_DIR = ROOT / "fixtures"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def validator(schema):
    return jsonschema.Draft7Validator(schema)


@pytest.fixture(scope="module")
def valid_fixtures():
    return {
        fp.stem: json.loads(fp.read_text())
        for fp in sorted(FIXTURES_DIR.glob("valid_*.json"))
    }


def _base_card():
    """Minimal valid card for structural mutation tests."""
    return {
        "schema": "agent-frontdoor.v0.1",
        "task_id": "20260101_test_001",
        "timestamp": "2026-01-01T00:00:00Z",
        "input_summary": "Read log files and report anomalies",
        "task_class": "READ_ONLY_AUDIT",
        "risk_tags": [],
        "predicted_worker": ["local-classifier-worker"],
        "predicted_confidence": "medium",
        "allowed_actions": ["read_files"],
        "forbidden_actions": ["write_files", "delete_files"],
        "required_manifest": "none",
        "human_gate": "none",
    }


# ── Schema integrity ──────────────────────────────────────────────────────────

class TestSchemaIntegrity:
    def test_schema_parses(self):
        schema = json.loads(SCHEMA_PATH.read_text())
        assert schema["title"] == "Agent Frontdoor v0.1"

    def test_schema_const_is_correct(self, schema):
        assert schema["properties"]["schema"]["const"] == "agent-frontdoor.v0.1"

    def test_additional_properties_is_false(self, schema):
        assert schema["additionalProperties"] is False

    def test_required_fields_present(self, schema):
        required = schema["required"]
        assert "schema" in required
        assert "task_class" in required
        assert "human_gate" in required
        assert "predicted_worker" in required
        assert "required_manifest" in required

    def test_scheduler_process_absent_from_enum(self, schema):
        enum = schema["properties"]["task_class"]["enum"]
        assert "SCHEDULER_PROCESS" not in enum

    def test_scheduler_risk_present_in_risk_tags_enum(self, schema):
        enum = schema["properties"]["risk_tags"]["items"]["enum"]
        assert "scheduler_risk" in enum


# ── Valid fixtures ────────────────────────────────────────────────────────────

class TestValidFixtures:
    def test_fixture_count(self, valid_fixtures):
        assert len(valid_fixtures) == 8, f"Expected 8 fixtures, got {len(valid_fixtures)}"

    @pytest.mark.parametrize("name", [
        "valid_read_only_audit",
        "valid_delete_archive_request",
        "valid_implementation",
        "valid_design_review",
        "valid_cleanup_planning",
        "valid_ssot_mutation",
        "valid_status_classification",
        "valid_unknown_escalation",
    ])
    def test_fixture_validates(self, validator, valid_fixtures, name):
        errors = list(validator.iter_errors(valid_fixtures[name]))
        assert errors == [], f"{name} failed: {[e.message for e in errors]}"

    def test_all_fixtures_use_capability_labels(self, valid_fixtures):
        allowed = {"local-classifier-worker", "architect-review-worker",
                   "implementation-worker", "none-until-approval"}
        for name, fixture in valid_fixtures.items():
            workers = fixture.get("predicted_worker", [])
            unknown = [w for w in workers if w not in allowed]
            assert unknown == [], f"{name}: predicted_worker outside allowlist: {unknown}"

    def test_scheduler_is_risk_tag_not_task_class(self, valid_fixtures):
        for name, fixture in valid_fixtures.items():
            assert fixture["task_class"] != "SCHEDULER_PROCESS", \
                f"{name}: SCHEDULER_PROCESS used as task_class"

    def test_ssot_mutation_fixture_has_scheduler_risk(self, valid_fixtures):
        fixture = valid_fixtures["valid_ssot_mutation"]
        assert "scheduler_risk" in fixture["risk_tags"]
        assert fixture["human_gate"] in ("required", "blocking")

    def test_deletion_fixture_has_blocking_gate(self, valid_fixtures):
        fixture = valid_fixtures["valid_delete_archive_request"]
        assert fixture["human_gate"] in ("required", "blocking")

    def test_schema_const_in_all_fixtures(self, valid_fixtures):
        for name, fixture in valid_fixtures.items():
            assert fixture["schema"] == "agent-frontdoor.v0.1", \
                f"{name}: wrong schema const '{fixture['schema']}'"


# ── Enum enforcement ──────────────────────────────────────────────────────────

class TestEnumEnforcement:
    def test_valid_task_classes_accepted(self, validator):
        valid_classes = [
            "READ_ONLY_AUDIT", "STATUS_CLASSIFICATION", "DESIGN_REVIEW",
            "IMPLEMENTATION", "TEST_VALIDATION", "CLEANUP_PLANNING",
            "SSOT_MUTATION", "DEPLOYMENT", "UNKNOWN",
        ]
        base = _base_card()
        for tc in valid_classes:
            base["task_class"] = tc
            errors = list(validator.iter_errors(base))
            assert errors == [], f"task_class={tc} should be valid but got: {[e.message for e in errors]}"

    def test_valid_human_gate_values(self, validator):
        base = _base_card()
        for gate in ("none", "required", "blocking"):
            base["human_gate"] = gate
            errors = list(validator.iter_errors(base))
            assert errors == [], f"human_gate={gate} should be valid"

    def test_valid_manifest_values(self, validator):
        base = _base_card()
        for m in ("none", "dedupe_manifest", "diff_manifest", "execution_manifest", "approval_manifest"):
            base["required_manifest"] = m
            errors = list(validator.iter_errors(base))
            assert errors == [], f"required_manifest={m} should be valid"

    def test_valid_confidence_values(self, validator):
        base = _base_card()
        for c in ("low", "medium", "high"):
            base["predicted_confidence"] = c
            errors = list(validator.iter_errors(base))
            assert errors == [], f"predicted_confidence={c} should be valid"
