"""Read-only command-line interface for Agent Frontdoor task cards."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import sys
from typing import cast

from frontdoor.boundary_drift import detect_boundary_drift
from frontdoor.formatter import format_card, format_explanation
from frontdoor.validator import ValidationResult, load_card


_INPUT_ERROR_CODES = frozenset({"input_read_error", "input_json_error"})


def build_parser() -> argparse.ArgumentParser:
    """Build the exact four-command read-only argument parser."""

    parser = argparse.ArgumentParser(
        prog="agent-frontdoor",
        description="Inspect and validate bounded task cards.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    for command in ("validate", "card", "explain"):
        subparser = commands.add_parser(command)
        subparser.add_argument("path")

    drift_parser = commands.add_parser("check-drift")
    drift_parser.add_argument("before")
    drift_parser.add_argument("after")
    return parser


def _emit_failures(
    labeled_results: tuple[tuple[str, ValidationResult], ...],
) -> int | None:
    issues = tuple(
        (label, issue)
        for label, result in labeled_results
        for issue in result.issues
    )
    if not issues:
        return None

    has_input_error = any(
        issue.code in _INPUT_ERROR_CODES for _, issue in issues
    )
    for label, issue in issues:
        prefix = "ERROR" if issue.code in _INPUT_ERROR_CODES else "INVALID"
        print(
            f"{prefix} {label}: {issue.code} at {issue.path}",
            file=sys.stderr,
        )
    return 2 if has_input_error else 1


def _validated_mapping(card: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], card)


def _visible_request_id(card: Mapping[str, object]) -> str:
    request_line = format_card(card).split("\n", 1)[0]
    return request_line.removeprefix("Request: ")


def _run_single_card(command: str, path: str) -> int:
    card, result = load_card(path)
    failure_exit = _emit_failures((("task", result),))
    if failure_exit is not None:
        return failure_exit

    validated = _validated_mapping(card)
    if command == "validate":
        print(f"VALID {_visible_request_id(validated)}")
    elif command == "card":
        print(format_card(validated))
    else:
        print(format_explanation(validated))
    return 0


def _run_check_drift(before_path: str, after_path: str) -> int:
    before, before_result = load_card(before_path)
    after, after_result = load_card(after_path)
    failure_exit = _emit_failures(
        (("before", before_result), ("after", after_result))
    )
    if failure_exit is not None:
        return failure_exit

    report = detect_boundary_drift(
        _validated_mapping(before), _validated_mapping(after)
    )
    if not report.drifted:
        print("NO DRIFT")
        return 0

    print("DRIFT")
    for finding in report.findings:
        print(f"- {finding.code}: {finding.message}")
    return 3


def main(argv: Sequence[str] | None = None) -> int:
    """Run one read-only preflight command and return its documented exit."""

    arguments = build_parser().parse_args(argv)
    if arguments.command == "check-drift":
        return _run_check_drift(arguments.before, arguments.after)
    return _run_single_card(arguments.command, arguments.path)
