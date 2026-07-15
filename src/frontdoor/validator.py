"""Pure, deterministic validation for Agent Frontdoor intake cards."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from os import PathLike
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class ValidationIssue:
    """One deterministic validation failure."""

    code: str
    message: str
    path: str


@dataclass(frozen=True)
class ValidationResult:
    """The immutable outcome of validating one intake card."""

    valid: bool
    issues: tuple[ValidationIssue, ...]


_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "intake.v0.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA)

_BLOCKING_RISK_TAGS = frozenset(
    {
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
    }
)

_UNSAFE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bdeploy(?:ment|ed|ing|s)?\b",
        r"\bprod(?:uction)?\b",
        r"\b(?:scheduler|schedule|scheduled|scheduling|cron)\b",
        r"\b(?:secrets?|credentials?|passwords?|api (?:keys?|tokens?)|"
        r"access tokens?)\b",
        r"\b(?:auth|authentication|authorization|logins?|permissions?)\b",
        r"\b(?:billing|invoices?|payments?|charges?)\b",
        r"\b(?:delete|deletion|deleting|deleted|destroy(?:s|ed|ing)?|"
        r"purg(?:e|es|ed|ing)|remove|removal|removing|removed|"
        r"destructive (?:cleanup|clean up))\b",
        r"\b(?:ssot|source of truth)\b",
        r"\b(?:publish|published|publishing|external publish|go live)\b",
        r"\b(?:authority promotion|promote|promoted|promoting|"
        r"grant authority|grant permission|elevate permission)\b",
    )
)

_UNKNOWN_SAFE_VERBS = frozenset(
    {
        "ask",
        "clarify",
        "read",
        "inspect",
        "review",
        "report",
        "analyze",
        "classify",
        "list",
        "summarize",
        "identify",
        "describe",
        "explain",
        "compare",
        "validate",
        "check",
        "wait",
    }
)


def _json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            path += f".{part}"
        else:
            path += f"[{json.dumps(part, ensure_ascii=True)}]"
    return path


def _schema_issues(card: object) -> list[ValidationIssue]:
    candidate = dict(card) if isinstance(card, Mapping) else card
    errors = sorted(
        _VALIDATOR.iter_errors(candidate),
        key=lambda error: (
            _json_path(error.absolute_path),
            error.validator or "",
            error.message,
        ),
    )
    return [
        ValidationIssue(
            code="schema_error",
            message=error.message,
            path=_json_path(error.absolute_path),
        )
        for error in errors
    ]


def _searchable_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", value.casefold())).strip()


def _contains_unsafe_keyword(value: str) -> bool:
    text = _searchable_text(value)
    return any(pattern.search(text) for pattern in _UNSAFE_PATTERNS)


def _is_unknown_action_safe(value: str) -> bool:
    words = _searchable_text(value).split()
    return bool(words) and words[0] in _UNKNOWN_SAFE_VERBS


def _semantic_issues(card: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    risk_tags = card.get("risk_tags")
    blocking_risk = (
        isinstance(risk_tags, list)
        and any(
            isinstance(tag, str) and tag in _BLOCKING_RISK_TAGS
            for tag in risk_tags
        )
    )

    unsafe_text = False
    human_request = card.get("human_request")
    if isinstance(human_request, str):
        unsafe_text = _contains_unsafe_keyword(human_request)

    allowed_actions = card.get("allowed_actions")
    if isinstance(allowed_actions, list):
        unsafe_text = unsafe_text or any(
            isinstance(action, str) and _contains_unsafe_keyword(action)
            for action in allowed_actions
        )

    next_safe_step = card.get("next_safe_step")
    if isinstance(next_safe_step, str):
        unsafe_text = unsafe_text or _contains_unsafe_keyword(next_safe_step)

    if (blocking_risk or unsafe_text) and card.get("human_gate") != "BLOCKING":
        issues.append(
            ValidationIssue(
                code="blocking_gate_required",
                message="Unsafe or unknown work requires human_gate BLOCKING.",
                path="$.human_gate",
            )
        )

    if card.get("task_class") == "UNKNOWN":
        if card.get("human_gate") != "BLOCKING":
            issues.append(
                ValidationIssue(
                    code="unknown_requires_blocking",
                    message="UNKNOWN tasks require human_gate BLOCKING.",
                    path="$.human_gate",
                )
            )

        if card.get("predicted_worker_capability") != "none-until-clarified":
            issues.append(
                ValidationIssue(
                    code="unknown_requires_no_worker",
                    message=(
                        "UNKNOWN tasks require the none-until-clarified "
                        "worker capability."
                    ),
                    path="$.predicted_worker_capability",
                )
            )

        unknowns = card.get("unknowns")
        has_stated_unknown = isinstance(unknowns, list) and any(
            isinstance(unknown, str) and unknown.strip()
            for unknown in unknowns
        )
        if not has_stated_unknown:
            issues.append(
                ValidationIssue(
                    code="unknown_details_required",
                    message="UNKNOWN tasks require at least one explicit unknown.",
                    path="$.unknowns",
                )
            )

        if isinstance(allowed_actions, list):
            for index, action in enumerate(allowed_actions):
                if isinstance(action, str) and not _is_unknown_action_safe(action):
                    issues.append(
                        ValidationIssue(
                            code="unknown_mutation_forbidden",
                            message=(
                                "UNKNOWN tasks may only allow explicitly "
                                "non-mutating actions."
                            ),
                            path=f"$.allowed_actions[{index}]",
                        )
                    )

        if (
            isinstance(next_safe_step, str)
            and not _is_unknown_action_safe(next_safe_step)
        ):
            issues.append(
                ValidationIssue(
                    code="unknown_mutation_forbidden",
                    message=(
                        "UNKNOWN tasks may only name an explicitly "
                        "non-mutating next step."
                    ),
                    path="$.next_safe_step",
                )
            )

    forbidden_actions = card.get("forbidden_actions")
    if isinstance(allowed_actions, list) and isinstance(forbidden_actions, list):
        forbidden_normalized = {
            _normalize_action(action)
            for action in forbidden_actions
            if isinstance(action, str) and _normalize_action(action)
        }
        for index, action in enumerate(allowed_actions):
            if not isinstance(action, str):
                continue
            normalized = _normalize_action(action)
            if normalized and normalized in forbidden_normalized:
                issues.append(
                    ValidationIssue(
                        code="action_conflict",
                        message=(
                            f"Action {normalized!r} is both allowed and forbidden."
                        ),
                        path="$.allowed_actions",
                    )
                )
                break

    return issues


def _normalize_action(action: str) -> str:
    return " ".join(
        part for part in re.split(r"[\W_]+", action.casefold()) if part
    )


def validate_card(card: object) -> ValidationResult:
    """Validate a Python mapping without mutating it."""

    issues = _schema_issues(card)
    if isinstance(card, Mapping):
        issues.extend(_semantic_issues(card))
    return ValidationResult(valid=not issues, issues=tuple(issues))


def load_card(
    path: str | PathLike[str],
) -> tuple[object | None, ValidationResult]:
    """Read and validate one JSON card, returning typed failures."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        issue = ValidationIssue(
            code="input_read_error",
            message=f"Unable to read input: {error}",
            path="$",
        )
        return None, ValidationResult(False, (issue,))

    try:
        card = json.loads(text)
    except json.JSONDecodeError as error:
        issue = ValidationIssue(
            code="input_json_error",
            message=(
                f"Invalid JSON at line {error.lineno}, column {error.colno}: "
                f"{error.msg}"
            ),
            path="$",
        )
        return None, ValidationResult(False, (issue,))

    return card, validate_card(card)
