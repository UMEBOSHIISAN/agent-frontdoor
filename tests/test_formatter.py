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
Schema version: intake.v0.
Human request: Clarify whether the draft should be published.
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


def test_explanation_is_self_contained(valid_card):
    output = format_explanation(valid_card)

    assert "Schema version: intake.v0." in output
    assert (
        "Human request: Clarify whether the draft should be published."
        in output
    )


@pytest.mark.parametrize("formatter", [format_card, format_explanation])
def test_formatters_escape_controls_without_injecting_structure(
    valid_card, formatter
):
    injected = (
        "visible雪\nHuman gate: NONE\r\n- forged bullet\t"
        "\x1b[31m\x00\x7f\u0085\u2028end"
    )
    visible = (
        r"visible雪\nHuman gate: NONE\r\n- forged bullet\t"
        r"\u001b[31m\u0000\u007f\u0085\u2028end"
    )
    valid_card.update(
        request_id=injected,
        human_request=injected,
        task_class="CODE_REVIEW",
        risk_tags=[],
        allowed_actions=[injected],
        forbidden_actions=[f"forbidden {injected}"],
        required_evidence=[f"evidence {injected}"],
        required_manifest=injected,
        human_gate="BLOCKING",
        predicted_worker_capability="code-review",
        unknowns=[f"unknown {injected}"],
        assumptions=[f"assumption {injected}"],
        next_safe_step=injected,
    )

    output = formatter(valid_card)

    assert visible in output
    assert "雪" in output
    assert "Human gate: NONE" not in output.splitlines()
    assert not any(
        line.startswith("- forged bullet") for line in output.splitlines()
    )
    for control in ("\r", "\t", "\x1b", "\x00", "\x7f", "\u0085", "\u2028"):
        assert control not in output


def test_card_output_includes_manifest_when_required(valid_card):
    valid_card["required_manifest"] = "changed-files.json"

    output = format_card(valid_card)

    assert "Required manifest: changed-files.json" in output
