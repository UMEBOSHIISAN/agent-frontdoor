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
    pending_tool_use_sha256: str | None


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
    rf"^\s*(?P<command>(?:{_EXECUTABLE_ALTERNATION})"
    r"(?:[ \t]+[A-Za-z0-9_./:@%+=,-]+){1,15})"
    r"(?:してや|して|やって|お願い(?:します)?)\s*[。.!！]?\s*$"
)
_FENCED_COMMAND_PATTERN = re.compile(
    r"```(?P<language>bash|sh|zsh|shell)?[ \t]*\r?\n"
    r"(?P<command>.*?)\r?\n```",
    re.IGNORECASE | re.DOTALL,
)
_INLINE_CODE_PATTERN = re.compile(r"`{1,3}([^`\r\n]+)`{1,3}")
_SHELL_LINE_PATTERN = re.compile(r"(?m)^\s*\$\s+([^\r\n]+)$")
_NEGATED_COMMAND_DIRECTIVE_PATTERN = re.compile(
    r"(?:"
    r"(?:do\s+not|don't|never)\s+(?:run|execute)"
    r"(?:\s+(?:this|the)(?:\s+(?:exact\s+)?command)?)?"
    r"|(?:cancel|ignore|skip)"
    r"(?:\s+(?:this|that|the)(?:\s+(?:exact\s+)?command)?)?"
    r")\s*:?\s*$",
    re.IGNORECASE,
)
_AFFIRMATIVE_COMMAND_DIRECTIVE_PATTERN = re.compile(
    r"(?:^|[\r\n.;!?！？])\s*(?:"
    r"(?:please\s+)?(?:run|execute)"
    r"(?:\s+(?:this|the)(?:\s+(?:exact\s+)?command)?)?"
    r"|(?:could|can|would|will)\s+you\s+(?:please\s+)?"
    r"(?:run|execute)"
    r"(?:\s+(?:this|the)(?:\s+(?:exact\s+)?command)?)?"
    r"|実行(?:して)?|やって)\s*:?\s*$",
    re.IGNORECASE,
)
_POST_COMMAND_NEGATION_PATTERN = re.compile(
    r"(?:"
    r"(?:do\s+not|don't|never)\s+(?:run|execute)"
    r"(?:\s+(?:it|this|that)(?:\s+command)?)?"
    r"|(?:cancel|ignore|skip)\s+(?:it|this|that)(?:\s+command)?"
    r"|(?:やめて|中止して|キャンセルして|実行しないで|実行するな)"
    r")",
    re.IGNORECASE,
)
_POST_CORRECTION_NEGATION_PATTERN = re.compile(
    r"(?:"
    r"(?:do\s+not|don't|never)"
    r"(?:\s+(?:do|retry|run|execute|resume|continue))?"
    r"(?:\s+(?:it|this|that|the\s+request))?"
    r"|(?:cancel|ignore|stop|abort|skip)"
    r"(?:\s+(?:it|this|that|the\s+request))?"
    r")",
    re.IGNORECASE,
)
_TERMINAL_COMMAND_CANCELLATION_PATTERN = re.compile(
    r"(?:stop|abort)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_STANDALONE_CANCELLATION_PATTERN = re.compile(
    r"(?:"
    r"stop|abort|(?:cancel|ignore|skip)(?:\s+it)?"
    r"|(?:do\s+not|don't|never)\s+do\s+it"
    r"|やっぱりやめて|やめて|中止して|キャンセルして|実行しないで|実行するな"
    r")[。.!！ ]*",
    re.IGNORECASE,
)
_ERROR_TARGET_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bclient\s+for\s+[`'\"]?"
        r"([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})"
        r"[^\r\n]{0,160}\b(?:failed|error|invalid|rejected|not\s+found)\b",
        r"\b(?:error|failed|invalid|rejected)\b[^\r\n.]{0,80}"
        r"\b(?:server|component)\s+[`'\"]?"
        r"([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})",
        r"\b(?:server|component)\s+[`'\"]?"
        r"([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})"
        r"[^\r\n.]{0,80}\b(?:failed|error|invalid|rejected|not\s+found)\b",
    )
)
_BACKTICK_ERROR_TARGET_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:failed|error|invalid)\b[^`\r\n]{0,80}`"
        r"([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})`",
        r"`([A-Za-z0-9][A-Za-z0-9._:@/-]{0,127})`"
        r"[^`\r\n]{0,80}\b(?:failed|error|invalid)\b",
    )
)
_AFFIRMATIVE_CORRECTION_PATTERN = re.compile(
    r"(?:"
    r"(?:do|retry|run|execute|resume|continue)\s+(?:the\s+)?"
    r"(?:original|first)\s+request"
    r"|(?:最初の依頼|元の依頼).{0,20}"
    r"(?:して|やって|続けて|再開)"
    r")",
    re.IGNORECASE,
)
_NEGATED_CORRECTION_PATTERN = re.compile(
    r"(?:"
    r"(?:do\s+not|don't|never)\s+"
    r"(?:(?:retry|run|execute|do)\s+)?(?:the\s+)?"
    r"(?:original|first)\s+request"
    r"|(?:do\s+not|don't|never)\s+want\s+(?:you\s+)?to\s+"
    r"(?:retry|run|execute|do)\s+(?:the\s+)?"
    r"(?:original|first)\s+request"
    r"|(?:cannot|can't|must\s+not|should\s+not)\s+"
    r"(?:retry|run|execute|do)\s+(?:the\s+)?"
    r"(?:original|first)\s+request"
    r"|(?:please\s+)?refrain\s+from\s+"
    r"(?:retrying|running|executing|doing)\s+(?:the\s+)?"
    r"(?:original|first)\s+request"
    r"|(?:cancel|ignore|stop|abort|skip)\s+(?:the\s+)?"
    r"(?:original|first)\s+request"
    r"|(?:最初の依頼|元の依頼).{0,20}"
    r"(?:しない|やらない|やるな|やめて)"
    r")",
    re.IGNORECASE,
)
_CORRECTION_MENTION_PATTERN = re.compile(
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
_DISPLAY_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SECRET_LIKE_PATTERN = re.compile(
    r"(?:^sk-|bearer|password|secret|token|api[_-]?key)",
    re.IGNORECASE,
)
_CREDENTIAL_PREFIX_PATTERN = re.compile(
    r"^(?:"
    r"AKIA|ASIA|AIza|gh[oprsu]_|github_pat_|glpat-|sk-|rk_|pk_|"
    r"xox[baprs]-|ya29\."
    r")",
    re.IGNORECASE,
)
_SECRET_CONTEXT_PATTERN = re.compile(
    r"(?:access[ _-]?key|api[ _-]?key|authorization|bearer|password|secret|token)"
    r"\s*(?:is\s+)?[:=]?\s*[`'\"]?\s*$",
    re.IGNORECASE,
)
_SECRET_SUFFIX_PATTERN = re.compile(
    r"^\s*[`'\"]?\s*(?:(?:is|was)\s+(?:the\s+|an?\s+)?)?"
    r"(?:invalid\s+)?"
    r"(?:access[ _-]?key|api[ _-]?key|authorization|bearer|password|secret|token)\b",
    re.IGNORECASE,
)
_GENERIC_ERROR_TARGETS = frozenset(
    {
        "an",
        "authentication",
        "error",
        "failed",
        "found",
        "invalid",
        "is",
        "not",
        "rejected",
        "startup",
        "the",
        "unavailable",
        "was",
        "with",
    }
)
_ACTION_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}")

_REPORT_REASON = (
    "A human-facing response is required before using another tool."
)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _normalized_command(value: str) -> str:
    """Normalize horizontal whitespace without erasing shell data."""

    candidate = value.strip(" \t")
    if "<<" in candidate:
        # Heredoc bodies are data, not shell-token whitespace. Conservatively
        # require a byte-for-byte horizontal-whitespace match for the whole
        # command instead of attempting to reimplement shell parsing here.
        return candidate
    normalized: list[str] = []
    quote: str | None = None
    escaped = False
    pending_space = False
    for character in candidate:
        if escaped:
            if pending_space and normalized:
                normalized.append(" ")
                pending_space = False
            normalized.append(character)
            escaped = False
            continue
        if character == "\\" and quote != "'":
            if pending_space and normalized:
                normalized.append(" ")
                pending_space = False
            normalized.append(character)
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                if pending_space and normalized:
                    normalized.append(" ")
                    pending_space = False
                quote = character
            elif quote == character:
                quote = None
            normalized.append(character)
            continue
        if character in {" ", "\t"} and quote is None:
            pending_space = True
            continue
        if pending_space and normalized:
            normalized.append(" ")
            pending_space = False
        normalized.append(character)
    return "".join(normalized)


def _command_parts(value: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(_normalized_command(value), posix=True))
    except ValueError:
        return ()


def _looks_like_command(value: str) -> bool:
    parts = _command_parts(value)
    if not parts:
        return False
    executable = parts[0]
    return (
        executable in _COMMAND_EXECUTABLES
        or "/" in executable
        or executable.startswith(".")
    )


def _post_command_is_negated(prompt: str, end: int) -> bool:
    suffix = prompt[end : end + 160]
    if _TERMINAL_COMMAND_CANCELLATION_PATTERN.search(suffix):
        return True
    for match in _POST_COMMAND_NEGATION_PATTERN.finditer(suffix):
        remainder = suffix[match.end() :].lstrip(" \t:;,.-–—")
        matched = match.group(0).rstrip()
        has_bare_run_verb = bool(
            re.search(r"\b(?:run|execute)\s*$", matched, re.IGNORECASE)
        )
        cancellation_tail = re.match(
            r"(?:again|anymore|yet|now|because|until|unless|while|when)\b",
            remainder,
            re.IGNORECASE,
        )
        if has_bare_run_verb and remainder and cancellation_tail is None:
            # A non-pronominal object belongs to a separate prohibition:
            # "run `git status`, but do not run tests".
            continue
        if remainder.startswith("`") or re.match(r"\$[ \t]+", remainder):
            continue
        return True
    return False


def _extract_exact_command(prompt: str) -> str | None:
    for pattern in (_FENCED_COMMAND_PATTERN, _SHELL_LINE_PATTERN):
        for match in pattern.finditer(prompt):
            if pattern is _FENCED_COMMAND_PATTERN:
                candidate = match.group("command").strip()
                explicit_shell = match.group("language") is not None
            else:
                candidate = match.group(1).strip()
                explicit_shell = True
            prefix = prompt[: match.start()]
            is_standalone = prompt.strip() == match.group(0).strip()
            is_negated = bool(
                _NEGATED_COMMAND_DIRECTIVE_PATTERN.search(prefix)
            ) or _post_command_is_negated(prompt, match.end())
            is_affirmative = bool(
                _AFFIRMATIVE_COMMAND_DIRECTIVE_PATTERN.search(prefix)
            )
            if (
                candidate
                and (explicit_shell or _looks_like_command(candidate))
                and not is_negated
                and (is_standalone or is_affirmative)
            ):
                return _normalized_command(candidate)

    for match in _INLINE_CODE_PATTERN.finditer(prompt):
        candidate = match.group(1).strip()
        prefix = prompt[: match.start()]
        is_standalone = prompt.strip() == match.group(0)
        is_negated = bool(
            _NEGATED_COMMAND_DIRECTIVE_PATTERN.search(prefix)
        ) or _post_command_is_negated(prompt, match.end())
        is_affirmative = bool(
            _AFFIRMATIVE_COMMAND_DIRECTIVE_PATTERN.search(prefix)
        )
        if (
            _looks_like_command(candidate)
            and not is_negated
            and (is_standalone or is_affirmative)
        ):
            return _normalized_command(candidate)

    match = _NATURAL_COMMAND_PATTERN.fullmatch(prompt)
    if match:
        return _normalized_command(match.group("command"))
    return None


def _extract_negated_command(prompt: str) -> str | None:
    for pattern in (_FENCED_COMMAND_PATTERN, _SHELL_LINE_PATTERN):
        for match in pattern.finditer(prompt):
            if pattern is _FENCED_COMMAND_PATTERN:
                candidate = match.group("command").strip()
                explicit_shell = match.group("language") is not None
            else:
                candidate = match.group(1).strip()
                explicit_shell = True
            prefix = prompt[: match.start()]
            is_negated = bool(
                _NEGATED_COMMAND_DIRECTIVE_PATTERN.search(prefix)
            ) or _post_command_is_negated(prompt, match.end())
            if (
                candidate
                and (explicit_shell or _looks_like_command(candidate))
                and is_negated
            ):
                return _normalized_command(candidate)

    for match in _INLINE_CODE_PATTERN.finditer(prompt):
        candidate = match.group(1).strip()
        prefix = prompt[: match.start()]
        is_negated = bool(
            _NEGATED_COMMAND_DIRECTIVE_PATTERN.search(prefix)
        ) or _post_command_is_negated(prompt, match.end())
        if _looks_like_command(candidate) and is_negated:
            return _normalized_command(candidate)
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
    for pattern in (*_ERROR_TARGET_PATTERNS, *_BACKTICK_ERROR_TARGET_PATTERNS):
        for match in pattern.finditer(prompt):
            target = match.group(1).rstrip(".:,;")
            if target.casefold() in _GENERIC_ERROR_TARGETS:
                continue
            if target not in targets:
                targets.append(target)
    return tuple(targets)


def _credential_shaped(target: str) -> bool:
    if _CREDENTIAL_PREFIX_PATTERN.search(target):
        return True
    if len(target) < 20:
        return False
    return len(set(target.casefold())) >= 10


def _target_has_secret_context(prompt: str, target: str) -> bool:
    prompt_folded = prompt.casefold()
    target_folded = target.casefold()
    offset = 0
    while True:
        index = prompt_folded.find(target_folded, offset)
        if index < 0:
            return False
        prefix = prompt[max(0, index - 64) : index]
        if _SECRET_CONTEXT_PATTERN.search(prefix):
            return True
        suffix = prompt[index + len(target) : index + len(target) + 64]
        if _SECRET_SUFFIX_PATTERN.search(suffix):
            return True
        offset = index + len(target)


def _display_targets(
    targets: tuple[str, ...],
    *,
    prompt: str,
) -> tuple[str, ...]:
    return tuple(
        target
        for target in targets
        if _DISPLAY_LABEL_PATTERN.fullmatch(target)
        and not _SECRET_LIKE_PATTERN.search(target)
        and not _CREDENTIAL_PREFIX_PATTERN.search(target)
        and not _credential_shaped(target)
        and not _target_has_secret_context(prompt, target)
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
        display_targets=_display_targets(targets, prompt=prompt),
        pending_tool_use_sha256=None,
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
        pending_tool_use_sha256=None,
    )


def _hold(prompt: str, previous: IntentLock) -> IntentLock:
    """Stop tool use after an explicit negation of the previous action."""

    return IntentLock(
        schema_version=previous.schema_version,
        intent_epoch=previous.intent_epoch + 1,
        source_prompt_sha256=_digest(prompt),
        phase="REPORT_REQUIRED",
        mode=previous.mode,
        exact_command_sha256=previous.exact_command_sha256,
        target_token_sha256=previous.target_token_sha256,
        display_targets=previous.display_targets,
        pending_tool_use_sha256=None,
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

    if previous is not None and _extract_negated_command(prompt) is not None:
        return _hold(prompt, previous)

    targets = _extract_error_targets(prompt)
    if targets:
        return _new_lock(
            prompt,
            epoch=epoch,
            mode="LITERAL_TARGET",
            command=None,
            targets=targets,
        )

    affirmative_correction = _AFFIRMATIVE_CORRECTION_PATTERN.search(prompt)
    correction_is_cancelled = bool(
        affirmative_correction
        and _POST_CORRECTION_NEGATION_PATTERN.search(
            prompt[affirmative_correction.end() : affirmative_correction.end() + 160]
        )
    )
    standalone_cancellation = _STANDALONE_CANCELLATION_PATTERN.fullmatch(
        prompt.strip()
    )
    if previous is not None and (
        _NEGATED_CORRECTION_PATTERN.search(prompt)
        or correction_is_cancelled
        or standalone_cancellation
    ):
        return _hold(prompt, previous)

    if previous is not None and (
        affirmative_correction
        or _CONTINUATION_PATTERN.fullmatch(prompt.strip())
    ):
        return _relock(prompt, previous)
    if previous is not None and _CORRECTION_MENTION_PATTERN.search(prompt):
        return previous
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


def bind_tool_use(lock: IntentLock, tool_use_id: str) -> IntentLock:
    """Bind one accepted tool call to the current immutable lock epoch."""

    if lock.phase != "DIRECT_REQUIRED" or not tool_use_id:
        return lock
    digest = _digest(tool_use_id)
    if digest == lock.pending_tool_use_sha256:
        return lock
    return IntentLock(
        schema_version=lock.schema_version,
        intent_epoch=lock.intent_epoch,
        source_prompt_sha256=lock.source_prompt_sha256,
        phase=lock.phase,
        mode=lock.mode,
        exact_command_sha256=lock.exact_command_sha256,
        target_token_sha256=lock.target_token_sha256,
        display_targets=lock.display_targets,
        pending_tool_use_sha256=digest,
    )


def matches_tool_use(lock: IntentLock, tool_use_id: str) -> bool:
    """Return whether a result belongs to the accepted call for this epoch."""

    return (
        bool(tool_use_id)
        and lock.pending_tool_use_sha256 is not None
        and _digest(tool_use_id) == lock.pending_tool_use_sha256
    )


def record_result(
    lock: IntentLock,
    action: str,
    *,
    failed: bool,
) -> IntentLock:
    """Record a matching direct result without mutating the supplied lock."""

    if lock.phase == "RELEASED":
        return lock
    if not evaluate_action(lock, action).allowed:
        return lock
    if failed:
        phase = "REPORT_REQUIRED"
    elif lock.mode == "EXACT_COMMAND":
        phase = "RELEASED"
    else:
        phase = lock.phase
    return IntentLock(
        schema_version=lock.schema_version,
        intent_epoch=lock.intent_epoch,
        source_prompt_sha256=lock.source_prompt_sha256,
        phase=phase,
        mode=lock.mode,
        exact_command_sha256=lock.exact_command_sha256,
        target_token_sha256=lock.target_token_sha256,
        display_targets=lock.display_targets,
        pending_tool_use_sha256=None,
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
        "pending_tool_use_sha256": lock.pending_tool_use_sha256,
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
        pending_tool_use_sha256=candidate["pending_tool_use_sha256"],
    )
