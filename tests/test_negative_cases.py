"""Negative-case tests for agent-frontdoor v0.1.

Tests that invalid or policy-violating task cards are correctly rejected.
Covers both structural violations (JSON Schema) and semantic violations
(application-level policy rules).

Required negative cases:
1. unknown/invalid task_class
2. SCHEDULER_PROCESS as task_class
3. predicted_worker outside the allowlist (e.g. VendorModelX)
4. predicted_worker outside the allowlist (e.g. ProprietaryWorker)
5. additionalProperties violation
6. missing human_gate
7. deletion_sensitive without human approval
8. scheduler change without scheduler_risk
"""
import json
import pathlib
import pytest
import jsonschema

ROOT = pathlib.Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema" / "agent-frontdoor.v0.1.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def validator(schema):
    return jsonschema.Draft7Validator(schema)


def _base_card():
    """Minimal valid card; individual tests mutate this to create violations."""
    return {
        "schema": "agent-frontdoor.v0.1",
        "task_id": "20260101_neg_001",
        "timestamp": "2026-01-01T00:00:00Z",
        "input_summary": "Inspect log files for anomalies",
        "task_class": "READ_ONLY_AUDIT",
        "risk_tags": [],
        "predicted_worker": ["local-classifier-worker"],
        "predicted_confidence": "medium",
        "allowed_actions": ["read_files"],
        "forbidden_actions": ["write_files", "delete_files"],
        "required_manifest": "none",
        "human_gate": "none",
    }


# ── Semantic validator (application-level policy) ─────────────────────────────

ALLOWED_WORKERS = {
    "local-classifier-worker",
    "architect-review-worker",
    "implementation-worker",
    "none-until-approval",
}


def semantic_validate(card: dict) -> list[str]:
    """Return a list of semantic policy violations (not JSON Schema errors).

    These rules cannot be expressed in JSON Schema and require application logic.
    """
    errors = []

    # Rule S-1: predicted_worker must be from the allowlist of capability labels.
    # Any value outside the allowlist is rejected — denylist matching is not sufficient
    # because unknown names would silently pass.
    for w in card.get("predicted_worker", []):
        if w not in ALLOWED_WORKERS:
            errors.append(
                f"unknown predicted_worker '{w}'; "
                f"must be one of: {sorted(ALLOWED_WORKERS)}"
            )

    # Rule S-2: deletion_sensitive tasks require human_gate
    risk_tags = card.get("risk_tags", [])
    if "deletion_sensitive" in risk_tags and card.get("human_gate") == "none":
        errors.append(
            "deletion_sensitive risk tag requires human_gate 'required' or 'blocking'"
        )

    # Rule S-3: scheduler-related SSOT_MUTATION must carry scheduler_risk tag
    if card.get("task_class") == "SSOT_MUTATION":
        summary = card.get("input_summary", "").lower()
        scheduler_keywords = ("schedule", "cron", "timer", "interval", "periodic")
        if any(kw in summary for kw in scheduler_keywords):
            if "scheduler_risk" not in risk_tags:
                errors.append(
                    "scheduler-related SSOT_MUTATION is missing 'scheduler_risk' in risk_tags"
                )

    return errors


# ── Negative test cases (structural) ─────────────────────────────────────────

class TestStructuralViolations:
    def test_neg1_invalid_task_class_rejected(self, validator):
        """Case 1: A task_class value not in the enum must be rejected."""
        card = _base_card()
        card["task_class"] = "MAKE_IT_ALL_WORK_SOMEHOW"
        errors = list(validator.iter_errors(card))
        assert errors, "Expected validation error for unknown task_class"
        messages = [e.message for e in errors]
        assert any("MAKE_IT_ALL_WORK_SOMEHOW" in m for m in messages)

    def test_neg2_scheduler_process_rejected(self, validator):
        """Case 2: SCHEDULER_PROCESS is not in the OSS v0 task_class enum."""
        card = _base_card()
        card["task_class"] = "SCHEDULER_PROCESS"
        errors = list(validator.iter_errors(card))
        assert errors, "SCHEDULER_PROCESS must not be a valid task_class in OSS v0"

    def test_neg5_additional_properties_rejected(self, validator):
        """Case 5: Extra fields not in the schema must be rejected."""
        card = _base_card()
        card["internal_field_that_does_not_exist"] = "some_value"
        errors = list(validator.iter_errors(card))
        assert errors, "additionalProperties: false must reject unknown fields"

    def test_neg6_missing_human_gate_rejected(self, validator):
        """Case 6: human_gate is a required field."""
        card = _base_card()
        del card["human_gate"]
        errors = list(validator.iter_errors(card))
        assert errors, "Missing human_gate must be rejected"
        messages = [e.message for e in errors]
        assert any("human_gate" in m for m in messages)

    def test_neg6_missing_task_class_rejected(self, validator):
        """task_class is required; omitting it must fail."""
        card = _base_card()
        del card["task_class"]
        errors = list(validator.iter_errors(card))
        assert errors

    def test_neg6_missing_predicted_worker_rejected(self, validator):
        """predicted_worker is required; omitting it must fail."""
        card = _base_card()
        del card["predicted_worker"]
        errors = list(validator.iter_errors(card))
        assert errors

    def test_neg_empty_predicted_worker_rejected(self, validator):
        """predicted_worker has minItems: 1; empty array must fail."""
        card = _base_card()
        card["predicted_worker"] = []
        errors = list(validator.iter_errors(card))
        assert errors, "Empty predicted_worker must be rejected (minItems: 1)"

    def test_neg_empty_allowed_actions_rejected(self, validator):
        """allowed_actions has minItems: 1; empty array must fail."""
        card = _base_card()
        card["allowed_actions"] = []
        errors = list(validator.iter_errors(card))
        assert errors

    def test_neg_invalid_human_gate_value(self, validator):
        """human_gate must be one of: none, required, blocking."""
        card = _base_card()
        card["human_gate"] = "maybe"
        errors = list(validator.iter_errors(card))
        assert errors

    def test_neg_invalid_confidence_value(self, validator):
        """predicted_confidence must be: low, medium, or high."""
        card = _base_card()
        card["predicted_confidence"] = "extremely_high"
        errors = list(validator.iter_errors(card))
        assert errors

    def test_neg_invalid_risk_tag(self, validator):
        """risk_tags items must be from the enum."""
        card = _base_card()
        card["risk_tags"] = ["this_tag_does_not_exist"]
        errors = list(validator.iter_errors(card))
        assert errors

    def test_neg_wrong_schema_const(self, validator):
        """schema field must be exactly 'agent-frontdoor.v0.1'."""
        card = _base_card()
        card["schema"] = "some-other-schema.v99"
        errors = list(validator.iter_errors(card))
        assert errors


# ── Negative test cases (semantic) ───────────────────────────────────────────

class TestSemanticViolations:
    def test_neg3_worker_outside_allowlist_vendor_name(self):
        """Case 3: A name outside the allowlist must be rejected by semantic validator."""
        card = _base_card()
        card["predicted_worker"] = ["VendorModelX"]
        errors = semantic_validate(card)
        assert errors, "VendorModelX is not in ALLOWED_WORKERS and must be rejected"
        assert any("VendorModelX" in e for e in errors)

    def test_neg4_worker_outside_allowlist_proprietary_name(self):
        """Case 4: A proprietary name outside the allowlist must be rejected."""
        card = _base_card()
        card["predicted_worker"] = ["ProprietaryWorker"]
        errors = semantic_validate(card)
        assert errors, "ProprietaryWorker is not in ALLOWED_WORKERS and must be rejected"
        assert any("ProprietaryWorker" in e for e in errors)

    def test_neg_worker_outside_allowlist_legacy_name(self):
        """Any name not in ALLOWED_WORKERS must be rejected, regardless of label form."""
        card = _base_card()
        card["predicted_worker"] = ["LegacyPipeline"]
        errors = semantic_validate(card)
        assert errors

    def test_neg7_deletion_sensitive_without_human_approval(self):
        """Case 7: deletion_sensitive + human_gate=none must be flagged."""
        card = _base_card()
        card["risk_tags"] = ["deletion_sensitive"]
        card["human_gate"] = "none"
        errors = semantic_validate(card)
        assert errors, "deletion_sensitive without human_gate must be flagged"
        assert any("deletion_sensitive" in e for e in errors)

    def test_neg7_deletion_sensitive_with_gate_passes(self):
        """deletion_sensitive + human_gate=blocking must pass semantic check."""
        card = _base_card()
        card["risk_tags"] = ["deletion_sensitive"]
        card["human_gate"] = "blocking"
        errors = semantic_validate(card)
        assert errors == []

    def test_neg8_scheduler_ssot_without_scheduler_risk(self):
        """Case 8: SSOT_MUTATION with schedule-related summary must have scheduler_risk."""
        card = _base_card()
        card["task_class"] = "SSOT_MUTATION"
        card["input_summary"] = "Update the nightly pipeline schedule interval"
        card["risk_tags"] = []  # missing scheduler_risk
        errors = semantic_validate(card)
        assert errors, "Scheduler-related SSOT_MUTATION missing scheduler_risk must be flagged"
        assert any("scheduler_risk" in e for e in errors)

    def test_neg8_scheduler_ssot_with_scheduler_risk_passes(self):
        """SSOT_MUTATION with schedule summary AND scheduler_risk must pass."""
        card = _base_card()
        card["task_class"] = "SSOT_MUTATION"
        card["input_summary"] = "Update the nightly pipeline schedule interval"
        card["risk_tags"] = ["scheduler_risk", "human_approval_required"]
        errors = semantic_validate(card)
        assert errors == []

    def test_valid_capability_labels_pass_semantic(self):
        """Capability labels must not be flagged as internal names."""
        card = _base_card()
        card["predicted_worker"] = [
            "local-classifier-worker",
            "architect-review-worker",
            "implementation-worker",
            "none-until-approval",
        ]
        errors = semantic_validate(card)
        assert errors == []
