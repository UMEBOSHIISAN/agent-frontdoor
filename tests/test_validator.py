"""Behavior tests for the fail-closed Agent Frontdoor validator."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json

import pytest

from frontdoor.validator import (
    ValidationIssue,
    ValidationResult,
    load_card,
    validate_card,
)


@pytest.fixture
def valid_card():
    return {
        "schema_version": "intake.v0",
        "request_id": "case-001",
        "human_request": "Review the supplied source files",
        "task_class": "CODE_REVIEW",
        "risk_tags": [],
        "allowed_actions": ["read_files", "produce_report"],
        "forbidden_actions": ["write_files", "delete_files"],
        "required_evidence": ["review findings"],
        "required_manifest": None,
        "human_gate": "NONE",
        "predicted_worker_capability": "code-review",
        "unknowns": [],
        "assumptions": [],
        "next_safe_step": "Inspect the requested files",
    }


def issue_codes(result):
    return {issue.code for issue in result.issues}


def make_unknown(card):
    card.update(
        task_class="UNKNOWN",
        human_gate="BLOCKING",
        predicted_worker_capability="none-until-clarified",
        allowed_actions=["clarify_request"],
        unknowns=["The requested outcome is unclear"],
        next_safe_step="Ask the human to clarify the request",
    )
    return card


def test_validation_types_are_frozen_and_issue_collection_is_a_tuple():
    issue = ValidationIssue("example", "Example issue", "$.field")
    result = ValidationResult(False, (issue,))

    assert result.issues == (issue,)
    with pytest.raises(FrozenInstanceError):
        issue.code = "changed"
    with pytest.raises(FrozenInstanceError):
        result.valid = True


def test_valid_card_passes(valid_card):
    assert validate_card(valid_card) == ValidationResult(True, ())


def test_validation_is_deterministic_and_does_not_mutate_input(valid_card):
    valid_card.pop("request_id")
    valid_card["predicted_worker_capability"] = "qwen"
    before = deepcopy(valid_card)

    first = validate_card(valid_card)
    second = validate_card(valid_card)

    assert first == second
    assert valid_card == before
    assert isinstance(first.issues, tuple)


def test_model_name_is_not_a_capability(valid_card):
    valid_card["predicted_worker_capability"] = "qwen"

    result = validate_card(valid_card)

    assert not result.valid
    assert "schema_error" in issue_codes(result)
    assert "$.predicted_worker_capability" in {
        issue.path for issue in result.issues
    }


@pytest.mark.parametrize(
    "risk_tag",
    [
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
        "unknown",
    ],
)
def test_blocking_risk_tag_requires_blocking_gate(valid_card, risk_tag):
    valid_card.update(risk_tags=[risk_tag], human_gate="CONFIRM")

    result = validate_card(valid_card)

    assert not result.valid
    assert "blocking_gate_required" in issue_codes(result)
    assert "$.human_gate" in {issue.path for issue in result.issues}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("human_request", "Deploy to production"),
        ("human_request", "Rotate the API key"),
        ("allowed_actions", ["change_scheduler_config"]),
        ("allowed_actions", ["purge_old_records"]),
        ("next_safe_step", "Publish the draft externally"),
        ("next_safe_step", "Promote this proposal to approved"),
    ],
)
def test_unsafe_keywords_require_blocking_gate(valid_card, field, value):
    valid_card[field] = value
    valid_card["human_gate"] = "NONE"

    result = validate_card(valid_card)

    assert not result.valid
    assert "blocking_gate_required" in issue_codes(result)


def test_unsafe_keyword_matching_is_case_insensitive(valid_card):
    valid_card.update(human_request="RoTaTe the SECRET", human_gate="CONFIRM")

    assert "blocking_gate_required" in issue_codes(validate_card(valid_card))


@pytest.mark.parametrize(
    "human_request",
    [
        "Rotate all secrets",
        "Rotate the API token",
        "Rotate the API tokens",
        "Start destroying obsolete records",
        "Begin purging obsolete records",
    ],
)
def test_unsafe_keyword_inflections_require_blocking(
    valid_card, human_request
):
    valid_card.update(human_request=human_request, human_gate="CONFIRM")

    assert "blocking_gate_required" in issue_codes(validate_card(valid_card))


def test_cleanup_adjacent_language_does_not_require_blocking(valid_card):
    valid_card.update(
        human_request="Plan cleanup of generated artifacts",
        risk_tags=["cleanup_adjacent"],
        human_gate="NONE",
    )

    assert validate_card(valid_card).valid


def test_destructive_cleanup_language_requires_blocking(valid_card):
    valid_card.update(
        human_request="Perform destructive cleanup of old logs",
        human_gate="CONFIRM",
    )

    assert "blocking_gate_required" in issue_codes(validate_card(valid_card))


def test_forbidden_actions_are_not_scanned_for_unsafe_intent(valid_card):
    valid_card["forbidden_actions"] = [
        "deploy_to_production",
        "delete_records",
        "publish_externally",
    ]

    assert validate_card(valid_card).valid


def test_unknown_requires_blocking(valid_card):
    make_unknown(valid_card)
    valid_card["human_gate"] = "CONFIRM"

    assert "unknown_requires_blocking" in issue_codes(
        validate_card(valid_card)
    )


def test_unknown_requires_no_worker_capability(valid_card):
    make_unknown(valid_card)
    valid_card["predicted_worker_capability"] = "research"

    assert "unknown_requires_no_worker" in issue_codes(
        validate_card(valid_card)
    )


def test_unknown_requires_at_least_one_unknown(valid_card):
    make_unknown(valid_card)
    valid_card["unknowns"] = []

    assert "unknown_details_required" in issue_codes(
        validate_card(valid_card)
    )


def test_unknown_requires_at_least_one_nonblank_unknown(valid_card):
    make_unknown(valid_card)
    valid_card["unknowns"] = ["", "   "]

    assert "unknown_details_required" in issue_codes(
        validate_card(valid_card)
    )


@pytest.mark.parametrize(
    "action",
    [
        "rename_files",
        "move_files",
        "copy_files",
        "touch_file",
        "replace_config",
        "truncate_log",
    ],
)
def test_unknown_rejects_actions_outside_safe_allowlist(valid_card, action):
    make_unknown(valid_card)
    valid_card["allowed_actions"] = [action]

    assert "unknown_mutation_forbidden" in issue_codes(
        validate_card(valid_card)
    )


@pytest.mark.parametrize(
    "action",
    [
        "ask_human",
        "clarify_request",
        "read_files",
        "inspect_files",
        "review_input",
        "report_findings",
        "analyze_data",
        "classify_request",
        "list_files",
        "summarize_input",
        "identify_unknowns",
        "describe_state",
        "explain_issue",
        "compare_inputs",
        "validate_schema",
        "check_status",
        "wait_for_human",
    ],
)
def test_unknown_accepts_explicitly_safe_actions(valid_card, action):
    make_unknown(valid_card)
    valid_card["allowed_actions"] = [action]

    assert validate_card(valid_card).valid


def test_unknown_rejects_next_step_outside_safe_allowlist(valid_card):
    make_unknown(valid_card)
    valid_card["next_safe_step"] = "Move the requested files"

    assert "unknown_mutation_forbidden" in issue_codes(
        validate_card(valid_card)
    )


def test_unknown_accepts_next_step_from_safe_allowlist(valid_card):
    make_unknown(valid_card)
    valid_card["next_safe_step"] = "Inspect the requested files"

    assert validate_card(valid_card).valid


def test_same_normalized_action_cannot_be_allowed_and_forbidden(valid_card):
    valid_card["allowed_actions"] = ["  Read--Files  "]
    valid_card["forbidden_actions"] = ["read_files"]

    result = validate_card(valid_card)

    assert not result.valid
    assert "action_conflict" in issue_codes(result)
    assert "$.allowed_actions" in {issue.path for issue in result.issues}


def test_load_card_returns_card_and_validation_result(tmp_path, valid_card):
    path = tmp_path / "card.json"
    path.write_text(json.dumps(valid_card), encoding="utf-8")

    card, result = load_card(path)

    assert card == valid_card
    assert result == ValidationResult(True, ())


def test_load_card_returns_typed_json_error(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{not-json", encoding="utf-8")

    card, result = load_card(path)

    assert card is None
    assert not result.valid
    assert [issue.code for issue in result.issues] == ["input_json_error"]
    assert result.issues[0].path == "$"


def test_load_card_returns_typed_read_error(tmp_path):
    path = tmp_path / "missing.json"

    card, result = load_card(path)

    assert card is None
    assert not result.valid
    assert [issue.code for issue in result.issues] == ["input_read_error"]
    assert result.issues[0].path == "$"


def test_load_card_validates_loaded_structure(tmp_path):
    path = tmp_path / "array.json"
    path.write_text("[]", encoding="utf-8")

    card, result = load_card(path)

    assert card == []
    assert not result.valid
    assert "schema_error" in issue_codes(result)
