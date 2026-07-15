"""Direct, subprocess-free tests for the read-only Frontdoor CLI."""

import json

import pytest

from frontdoor.cli import build_parser, main
from frontdoor.formatter import format_card, format_explanation


@pytest.fixture
def valid_card():
    return {
        "schema_version": "intake.v0",
        "request_id": "case-001",
        "human_request": "Review the supplied source files",
        "task_class": "CODE_REVIEW",
        "risk_tags": [],
        "allowed_actions": ["read files", "report findings"],
        "forbidden_actions": ["write files", "delete files"],
        "required_evidence": ["review report"],
        "required_manifest": None,
        "human_gate": "NONE",
        "predicted_worker_capability": "code-review",
        "unknowns": [],
        "assumptions": [],
        "next_safe_step": "Inspect the requested files",
    }


def _write_json(tmp_path, name, card):
    path = tmp_path / name
    path.write_text(json.dumps(card), encoding="utf-8")
    return path


def _write_malformed(tmp_path, name="malformed.json"):
    path = tmp_path / name
    path.write_text("{not-json", encoding="utf-8")
    return path


def test_parser_exposes_exact_four_commands():
    parser = build_parser()

    for command, paths in (
        ("validate", ["task.json"]),
        ("card", ["task.json"]),
        ("explain", ["task.json"]),
        ("check-drift", ["before.json", "after.json"]),
    ):
        assert parser.parse_args([command, *paths]).command == command


def test_validate_command_returns_zero_for_valid_card(
    tmp_path, capsys, valid_card
):
    path = _write_json(tmp_path, "task.json", valid_card)

    assert main(["validate", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "VALID case-001\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("command", "formatter"),
    [("card", format_card), ("explain", format_explanation)],
)
def test_format_commands_print_only_valid_formatted_cards(
    tmp_path, capsys, valid_card, command, formatter
):
    path = _write_json(tmp_path, "task.json", valid_card)

    assert main([command, str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"{formatter(valid_card)}\n"
    assert captured.err == ""


@pytest.mark.parametrize("command", ["validate", "card", "explain"])
def test_single_card_commands_return_one_for_loaded_invalid_card(
    tmp_path, capsys, valid_card, command
):
    valid_card["request_id"] = ""
    path = _write_json(tmp_path, "invalid.json", valid_card)

    assert main([command, str(path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INVALID task: schema_error at $.request_id\n"


@pytest.mark.parametrize("command", ["validate", "card", "explain"])
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [("missing", "input_read_error"), ("malformed", "input_json_error")],
)
def test_single_card_commands_return_two_for_input_errors(
    tmp_path, capsys, command, failure, expected_code
):
    path = (
        tmp_path / "missing.json"
        if failure == "missing"
        else _write_malformed(tmp_path)
    )

    assert main([command, str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"ERROR task: {expected_code} at $\n"


def test_check_drift_returns_zero_for_unchanged_valid_cards(
    tmp_path, capsys, valid_card
):
    before = _write_json(tmp_path, "before.json", valid_card)
    after = _write_json(tmp_path, "after.json", valid_card)

    assert main(["check-drift", str(before), str(after)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "NO DRIFT\n"
    assert captured.err == ""


def test_check_drift_returns_three_and_prints_all_findings(
    tmp_path, capsys, valid_card
):
    valid_card.update(
        task_class="DESIGN_REVIEW",
        predicted_worker_capability="design-review",
        allowed_actions=["review the proposed design"],
        next_safe_step="Report design findings",
    )
    after_card = dict(valid_card)
    after_card.update(
        task_class="IMPLEMENTATION",
        predicted_worker_capability="implementation",
        allowed_actions=["implement the proposed design"],
        next_safe_step="Write the implementation",
    )
    before = _write_json(tmp_path, "before.json", valid_card)
    after = _write_json(tmp_path, "after.json", after_card)

    assert main(["check-drift", str(before), str(after)]) == 3
    captured = capsys.readouterr()
    assert captured.out == (
        "DRIFT\n"
        "- design_to_implementation: "
        "Design review scope expanded to implementation.\n"
    )
    assert captured.err == ""


@pytest.mark.parametrize("invalid_position", ["before", "after"])
def test_check_drift_returns_one_when_either_loaded_card_is_invalid(
    tmp_path, capsys, valid_card, invalid_position
):
    invalid_card = dict(valid_card)
    invalid_card["request_id"] = ""
    before_card = invalid_card if invalid_position == "before" else valid_card
    after_card = invalid_card if invalid_position == "after" else valid_card
    before = _write_json(tmp_path, "before.json", before_card)
    after = _write_json(tmp_path, "after.json", after_card)

    assert main(["check-drift", str(before), str(after)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"INVALID {invalid_position}: schema_error at $.request_id\n"
    )


@pytest.mark.parametrize(
    ("failed_position", "failure", "expected_code"),
    [
        ("before", "missing", "input_read_error"),
        ("after", "malformed", "input_json_error"),
    ],
)
def test_check_drift_returns_two_when_either_input_cannot_be_loaded(
    tmp_path,
    capsys,
    valid_card,
    failed_position,
    failure,
    expected_code,
):
    valid = _write_json(tmp_path, "valid.json", valid_card)
    failed = (
        tmp_path / "missing.json"
        if failure == "missing"
        else _write_malformed(tmp_path)
    )
    before = failed if failed_position == "before" else valid
    after = failed if failed_position == "after" else valid

    assert main(["check-drift", str(before), str(after)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"ERROR {failed_position}: {expected_code} at $\n"
    )


def test_check_drift_validates_both_inputs_before_returning(
    tmp_path, capsys
):
    before = tmp_path / "missing.json"
    after = _write_malformed(tmp_path)

    assert main(["check-drift", str(before), str(after)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "ERROR before: input_read_error at $\n"
        "ERROR after: input_json_error at $\n"
    )
