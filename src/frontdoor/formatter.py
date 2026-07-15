"""Deterministic, human-readable formatting for validated task cards."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import cast


_NAMED_CONTROL_ESCAPES = {
    "\b": r"\b",
    "\t": r"\t",
    "\n": r"\n",
    "\f": r"\f",
    "\r": r"\r",
}


def _visible_text(value: str) -> str:
    visible: list[str] = []
    for character in value:
        if character == "\\":
            visible.append(r"\\")
        elif character in _NAMED_CONTROL_ESCAPES:
            visible.append(_NAMED_CONTROL_ESCAPES[character])
        elif unicodedata.category(character) in {"Cc", "Zl", "Zp"}:
            visible.append(f"\\u{ord(character):04x}")
        else:
            visible.append(character)
    return "".join(visible)


def _text(card: Mapping[str, object], field: str) -> str:
    return _visible_text(cast(str, card[field]))


def _items(card: Mapping[str, object], field: str) -> tuple[str, ...]:
    return tuple(
        _visible_text(item) for item in cast(list[str], card[field])
    )


def _bullets(items: tuple[str, ...]) -> tuple[str, ...]:
    if not items:
        return ("- none",)
    return tuple(f"- {item}" for item in items)


def _joined(items: tuple[str, ...]) -> str:
    return "; ".join(items) if items else "none"


def _manifest(card: Mapping[str, object]) -> str:
    manifest = cast(str | None, card["required_manifest"])
    return _visible_text(manifest) if manifest is not None else "none"


def format_card(card: Mapping[str, object]) -> str:
    """Return a fixed-order task card without mutating the validated input."""

    lines = [
        f"Request: {_text(card, 'request_id')}",
        f"Schema version: {_text(card, 'schema_version')}",
        f"Human request: {_text(card, 'human_request')}",
        f"Task class: {_text(card, 'task_class')}",
        "Risk tags:",
        *_bullets(_items(card, "risk_tags")),
        "Allowed actions:",
        *_bullets(_items(card, "allowed_actions")),
        "Forbidden actions:",
        *_bullets(_items(card, "forbidden_actions")),
        "Required evidence:",
        *_bullets(_items(card, "required_evidence")),
        f"Required manifest: {_manifest(card)}",
        f"Human gate: {_text(card, 'human_gate')}",
        (
            "Predicted worker capability: "
            f"{_text(card, 'predicted_worker_capability')}"
        ),
        "Unknowns:",
        *_bullets(_items(card, "unknowns")),
        "Assumptions:",
        *_bullets(_items(card, "assumptions")),
        f"Next safe step: {_text(card, 'next_safe_step')}",
    ]
    return "\n".join(lines)


def format_explanation(card: Mapping[str, object]) -> str:
    """Explain a validated task card in concise, fixed-order prose."""

    lines = [
        (
            f"Request {_text(card, 'request_id')} is classified as "
            f"{_text(card, 'task_class')}."
        ),
        f"Schema version: {_text(card, 'schema_version')}.",
        f"Human request: {_text(card, 'human_request')}.",
        f"Human gate: {_text(card, 'human_gate')}.",
        f"Risk tags: {_joined(_items(card, 'risk_tags'))}.",
        f"Allowed scope: {_joined(_items(card, 'allowed_actions'))}.",
        f"Forbidden scope: {_joined(_items(card, 'forbidden_actions'))}.",
        f"Required evidence: {_joined(_items(card, 'required_evidence'))}.",
        f"Required manifest: {_manifest(card)}.",
        (
            "Predicted worker capability: "
            f"{_text(card, 'predicted_worker_capability')}."
        ),
        f"Unknowns: {_joined(_items(card, 'unknowns'))}.",
        f"Assumptions: {_joined(_items(card, 'assumptions'))}.",
        f"Next safe step: {_text(card, 'next_safe_step')}.",
    ]
    return "\n".join(lines)
