"""Pure, deterministic intent locking for literal agent tasks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
import json
import re
import shlex
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class IntentLock:
    """One immutable, privacy-minimized literal intent boundary."""

    schema_version: str
    intent_epoch: int
    source_prompt_sha256: str
    phase: str
    mode: str
    exact_command_sha256: str | None
    target_token_sha256: tuple[str, ...]
    display_targets: tuple[str, ...]


@dataclass(frozen=True)
class IntentDecision:
    """Whether one proposed action stays attached to the current intent."""

    allowed: bool
    code: str
    reason: str


_SCHEMA = json.loads(
    resources.files("frontdoor")
    .joinpath("schema/intent-lock.v1.json")
    .read_text(encoding="utf-8")
)
_VALIDATOR = Draft202012Validator(_SCHEMA)

_COMMAND_EXECUTABLES = (
    "ansible",
    "bash",
    "cargo",
    "claude",
    "codex",
    "curl",
    "docker",
    "gh",
    "git",
    "go",
    "kubectl",
    "make",
    "node",
    "npm",
    "npx",
    "pip",
    "pip3",
    "pipx",
    "pnpm",
    "poetry",
    "python",
    "python3",
    "rsync",
    "sh",
    "ssh",
    "terraform",
    "uv",
    "wrangler",
    "yarn",
    "zsh",
)
_EXECUTABLE_ALTERNATION = "|".join(
    sorted(_COMMAND_EXECUTABLES, key=len, reverse=True)
)
_NATURAL_COMMAND_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9_./-])(?P<command>(?:{_EXECUTABLE_ALTERNATION})"
    r"(?:[ \t]+[A-Za-z0-9_./:@%+=,-]+){1,15})"
)
_INLINE_CODE_PATTERN = re.compile(r"`{1,3}([^`\r\n]+)`{1,3}")
_SHELL_LINE_PATTERN = re.compile(r"(?m)^\s*\$\s+([^\r\n]+)$")
_ERROR_TARGET_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bclient\s+for\s+[`'\"]?([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})",
        r"\bserver\s+[`'\"]?([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})",
        r"\bcomponent\s+[`'\"]?([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})",
    )
)
_CORRECTION_PATTERN = re.compile(
    r"(?:最初の依頼|元の依頼|original request|first request)",
    re.IGNORECASE,
)
_CONTINUATION_PATTERN = re.compile(
    r"^(?:やって|全部やって|続けて|進めて|うん|はい|go|proceed|continue|yes)[。.!！ ]*$",
    re.IGNORECASE,
)
_SAFE_LABEL_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$"
)
_SECRET_LIKE_PATTERN = re.compile(
    r"(?:^sk-|bearer|password|secret|token|api[_-]?key)",
    re.IGNORECASE,
)
_ACTION_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}")

_REPORT_REASON = (
    "The direct action failed. Report that result to the human before using "
    "another tool."
)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _normalized_command(value: str) -> str:
    candidate = value.strip()
    try:
        parts = shlex.split(candidate, posix=True)
    except ValueError:
        parts = candidate.split()
    return " ".join(parts)


def _command_parts(value: str) -> tuple[str, ...]:
    normalized = _normalized_command(value)
    return tuple(normalized.split())


def _looks_like_command(value: str) -> bool:
    parts = _command_parts(value)
    if len(parts) < 2:
        return False
    executable = parts[0]
    return (
        executable in _COMMAND_EXECUTABLES
        or "/" in executable
        or executable.startswith(".")
    )


def _extract_exact_command(prompt: str) -> str | None:
    for pattern in (_SHELL_LINE_PATTERN, _INLINE_CODE_PATTERN):
        for match in pattern.finditer(prompt):
            candidate = match.group(1).strip()
            if _looks_like_command(candidate):
                return _normalized_command(candidate)

    match = _NATURAL_COMMAND_PATTERN.search(prompt)
    if match:
        return _normalized_command(match.group("command"))
    return None


def _command_target(command: str) -> str | None:
    parts = _command_parts(command)
    candidates = [
        part
        for part in parts[1:]
        if not part.startswith("-") and _SAFE_LABEL_PATTERN.fullmatch(part)
    ]
    return candidates[-1] if candidates else None


def _extract_error_targets(prompt: str) -> tuple[str, ...]:
    targets: list[str] = []
    for pattern in _ERROR_TARGET_PATTERNS:
        for match in pattern.finditer(prompt):
            target = match.group(1).rstrip(".:,;")
            if target not in targets:
                targets.append(target)
    return tuple(targets)


def _display_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        target
        for target in targets
        if _SAFE_LABEL_PATTERN.fullmatch(target)
        and not _SECRET_LIKE_PATTERN.search(target)
    )


def _new_lock(
    prompt: str,
    *,
    epoch: int,
    mode: str,
    command: str | None,
    targets: tuple[str, ...],
) -> IntentLock:
    lock = IntentLock(
        schema_version="intent-lock.v1",
        intent_epoch=epoch,
        source_prompt_sha256=_digest(prompt),
        phase="DIRECT_REQUIRED",
        mode=mode,
        exact_command_sha256=(
            _digest(_normalized_command(command)) if command is not None else None
        ),
        target_token_sha256=tuple(
            dict.fromkeys(_digest(target.casefold()) for target in targets)
        ),
        display_targets=_display_targets(targets),
    )
    lock_from_dict(lock_to_dict(lock))
    return lock


def _relock(prompt: str, previous: IntentLock) -> IntentLock:
    return IntentLock(
        schema_version=previous.schema_version,
        intent_epoch=previous.intent_epoch + 1,
        source_prompt_sha256=_digest(prompt),
        phase="DIRECT_REQUIRED",
        mode=previous.mode,
        exact_command_sha256=previous.exact_command_sha256,
        target_token_sha256=previous.target_token_sha256,
        display_targets=previous.display_targets,
    )


def derive_lock(
    prompt: str,
    previous: IntentLock | None = None,
) -> IntentLock | None:
    """Derive a literal lock, preserve a human re-lock, or return no lock."""

    command = _extract_exact_command(prompt)
    epoch = 1 if previous is None else previous.intent_epoch + 1
    if command is not None:
        target = _command_target(command)
        targets = (target,) if target is not None else (command.split()[0],)
        return _new_lock(
            prompt,
            epoch=epoch,
            mode="EXACT_COMMAND",
            command=command,
            targets=targets,
        )

    targets = _extract_error_targets(prompt)
    if targets:
        return _new_lock(
            prompt,
            epoch=epoch,
            mode="LITERAL_TARGET",
            command=None,
            targets=targets,
        )

    if previous is not None and (
        _CORRECTION_PATTERN.search(prompt)
        or _CONTINUATION_PATTERN.fullmatch(prompt.strip())
    ):
        return _relock(prompt, previous)
    return None


def _target_reason(lock: IntentLock) -> str:
    if lock.display_targets:
        labels = ", ".join(lock.display_targets)
        return (
            "Proposed action does not contain the locked literal target: "
            f"{labels}."
        )
    return "Proposed action does not contain the locked literal target."


def evaluate_action(lock: IntentLock, action: str) -> IntentDecision:
    """Check task identity only; this function never grants authority."""

    if lock.phase == "REPORT_REQUIRED":
        return IntentDecision(False, "report_required", _REPORT_REASON)
    if lock.phase == "RELEASED":
        return IntentDecision(True, "released", "Intent lock is released.")

    if lock.mode == "EXACT_COMMAND":
        matches = _digest(_normalized_command(action)) == lock.exact_command_sha256
        if matches:
            return IntentDecision(
                True,
                "exact_command_match",
                "Proposed action matches the locked exact command.",
            )
        return IntentDecision(
            False,
            "exact_command_mismatch",
            "Proposed action does not match the locked exact command.",
        )

    action_digests = {
        _digest(token.casefold()) for token in _ACTION_TOKEN_PATTERN.findall(action)
    }
    if all(digest in action_digests for digest in lock.target_token_sha256):
        return IntentDecision(
            True,
            "literal_target_match",
            "Proposed action contains the locked literal target.",
        )
    return IntentDecision(
        False,
        "literal_target_mismatch",
        _target_reason(lock),
    )


def record_result(
    lock: IntentLock,
    action: str,
    *,
    failed: bool,
) -> IntentLock:
    """Record a matching direct result without mutating the supplied lock."""

    if not evaluate_action(lock, action).allowed:
        return lock
    if failed:
        phase = "REPORT_REQUIRED"
    elif lock.mode == "EXACT_COMMAND":
        phase = "RELEASED"
    else:
        return lock
    return IntentLock(
        schema_version=lock.schema_version,
        intent_epoch=lock.intent_epoch,
        source_prompt_sha256=lock.source_prompt_sha256,
        phase=phase,
        mode=lock.mode,
        exact_command_sha256=lock.exact_command_sha256,
        target_token_sha256=lock.target_token_sha256,
        display_targets=lock.display_targets,
    )


def lock_to_dict(lock: IntentLock) -> dict[str, object]:
    """Render the versioned JSON contract without raw prompt or command text."""

    return {
        "schema_version": lock.schema_version,
        "intent_epoch": lock.intent_epoch,
        "source_prompt_sha256": lock.source_prompt_sha256,
        "phase": lock.phase,
        "mode": lock.mode,
        "exact_command_sha256": lock.exact_command_sha256,
        "target_token_sha256": list(lock.target_token_sha256),
        "display_targets": list(lock.display_targets),
    }


def lock_from_dict(value: Mapping[str, Any]) -> IntentLock:
    """Validate and restore an `intent-lock.v1` mapping."""

    candidate = dict(value)
    errors = sorted(
        _VALIDATOR.iter_errors(candidate),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    if errors:
        summary = "; ".join(error.message for error in errors)
        raise ValueError(f"invalid intent-lock.v1: {summary}")
    return IntentLock(
        schema_version=candidate["schema_version"],
        intent_epoch=candidate["intent_epoch"],
        source_prompt_sha256=candidate["source_prompt_sha256"],
        phase=candidate["phase"],
        mode=candidate["mode"],
        exact_command_sha256=candidate["exact_command_sha256"],
        target_token_sha256=tuple(candidate["target_token_sha256"]),
        display_targets=tuple(candidate["display_targets"]),
    )
