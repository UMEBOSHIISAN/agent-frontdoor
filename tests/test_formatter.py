"""Behavior tests for deterministic, human-readable task formatting."""

from copy import deepcopy

import pytest

from frontdoor.formatter import format_card, format_explanation


@pytest.fixture
def valid_card():
    return {
        "schema_version": "intake.v0",
        "request_id": "case-001",
        "human_request": "Clarify whether the draft should be published",
        "task_class": "UNKNOWN",
        "risk_tags": ["external_publish", "unknown"],
        "allowed_actions": ["clarify request", "read supplied context"],
        "forbidden_actions": ["publish externally"],
        "required_evidence": [],
        "required_manifest": None,
        "human_gate": "BLOCKING",
        "predicted_worker_capability": "none-until-clarified",
        "unknowns": ["Whether external publication is intended"],
        "assumptions": [],
        "next_safe_step": "Ask the human to clarify publication intent",
    }


def test_card_output_is_deterministic_and_does_not_mutate(valid_card):
    original = deepcopy(valid_card)
    expected = """Request: case-001
Schema version: intake.v0
Human request: Clarify whether the draft should be published
Task class: UNKNOWN
Risk tags:
- external_publish
- unknown
Allowed actions:
- clarify request
- read supplied context
Forbidden actions:
- publish externally
Required evidence:
- none
Required manifest: none
Human gate: BLOCKING
Predicted worker capability: none-until-clarified
Unknowns:
- Whether external publication is intended
Assumptions:
- none
Next safe step: Ask the human to clarify publication intent"""

    assert format_card(valid_card) == expected
    assert format_card(valid_card) == expected
    assert valid_card == original


def test_explanation_is_deterministic_and_does_not_mutate(valid_card):
    original = deepcopy(valid_card)
    expected = """Request case-001 is classified as UNKNOWN.
Human gate: BLOCKING.
Risk tags: external_publish; unknown.
Allowed scope: clarify request; read supplied context.
Forbidden scope: publish externally.
Required evidence: none.
Required manifest: none.
Predicted worker capability: none-until-clarified.
Unknowns: Whether external publication is intended.
Assumptions: none.
Next safe step: Ask the human to clarify publication intent."""

    assert format_explanation(valid_card) == expected
    assert format_explanation(valid_card) == expected
    assert valid_card == original


def test_card_output_includes_manifest_when_required(valid_card):
    valid_card["required_manifest"] = "changed-files.json"

    output = format_card(valid_card)

    assert "Required manifest: changed-files.json" in output
