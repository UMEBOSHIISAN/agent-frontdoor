"""Codex and Claude Code hook JSON adapter for Agent Frontdoor."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import sys
from typing import Any

from frontdoor.intent_lock import (
    IntentLock,
    bind_tool_use,
    derive_lock,
    evaluate_action,
    matches_tool_use,
    record_result,
)
from frontdoor_hooks.state import (
    StateError,
    delete_session_lock,
    load_session_lock,
    save_session_lock,
)


_REPORT_CONTEXT = (
    "INTENT_LOCK_REPORT_REQUIRED: report the direct failure; do not try an "
    "alternative tool or subsystem."
)
_CODEX_OPAQUE_REPORT_CONTEXT = (
    "INTENT_LOCK_REPORT_REQUIRED: report the direct result; Codex Bash hooks "
    "do not expose its exit status. Do not try another tool or subsystem first."
)
_SHELL_TOOL_NAMES = frozenset(
    {
        "bash",
        "shell",
        "exec_command",
        "functions.exec",
        "functions.exec_command",
        "unified_exec",
    }
)


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _session_id(payload: Mapping[str, object]) -> str | None:
    value = payload.get("session_id")
    return value if isinstance(value, str) and value else None


def _tool_use_id(payload: Mapping[str, object]) -> str | None:
    value = payload.get("tool_use_id")
    return value if isinstance(value, str) and value else None


def _tool_action(payload: Mapping[str, object]) -> str:
    tool_input = payload.get("tool_input")
    tool_name = payload.get("tool_name")
    is_shell_tool = (
        isinstance(tool_name, str)
        and tool_name.casefold() in _SHELL_TOOL_NAMES
    )
    if is_shell_tool and isinstance(tool_input, Mapping):
        for key in ("command", "cmd"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
    envelope = {
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _lock_context(lock: IntentLock) -> str:
    target = ",".join(lock.display_targets) if lock.display_targets else "hashed"
    return (
        f"INTENT_LOCK_ACTIVE epoch={lock.intent_epoch} mode={lock.mode} "
        f"target={target}. This checks task identity only and does not grant "
        "authority."
    )


def _load_or_deny(
    state_root: Path,
    session_id: str,
) -> tuple[IntentLock | None, dict[str, object] | None]:
    try:
        return load_session_lock(state_root, session_id), None
    except StateError:
        return None, _deny(
            "Intent Lock state is invalid; tool use is denied until the state "
            "is repaired or the session ends."
        )


def handle_user_prompt(
    payload: Mapping[str, object],
    state_root: Path,
) -> dict[str, object] | None:
    session_id = _session_id(payload)
    prompt = payload.get("prompt")
    if session_id is None or not isinstance(prompt, str):
        return {
            "decision": "block",
            "reason": "Intent Lock requires a session id and string prompt.",
        }
    try:
        previous = load_session_lock(state_root, session_id)
    except StateError as error:
        return {
            "decision": "block",
            "reason": f"Intent Lock state is invalid: {error}",
        }

    lock = derive_lock(prompt, previous=previous)
    if lock is None:
        delete_session_lock(state_root, session_id)
        return None
    save_session_lock(state_root, session_id, lock)
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": _lock_context(lock),
        }
    }


def handle_pre_tool(
    payload: Mapping[str, object],
    state_root: Path,
) -> dict[str, object] | None:
    session_id = _session_id(payload)
    if session_id is None:
        return _deny(
            "Intent Lock cannot identify this session; tool use is denied."
        )
    lock, failure = _load_or_deny(state_root, session_id)
    if failure is not None:
        return failure
    if lock is None:
        return None

    decision = evaluate_action(lock, _tool_action(payload))
    if decision.allowed:
        tool_use_id = _tool_use_id(payload)
        if tool_use_id is None:
            return _deny(
                "Intent Lock cannot bind this action without a tool use id; "
                "tool use is denied."
            )
        save_session_lock(
            state_root,
            session_id,
            bind_tool_use(lock, tool_use_id),
        )
        return None
    return _deny(decision.reason)


def _explicit_failure(value: object) -> bool | None:
    if isinstance(value, Mapping):
        for key in ("exit_code", "exitCode"):
            code = value.get(key)
            if isinstance(code, int) and not isinstance(code, bool):
                return code != 0
        success = value.get("success")
        if isinstance(success, bool):
            return not success
        for key in ("isError", "is_error"):
            failed = value.get(key)
            if isinstance(failed, bool):
                return failed
    return None


def _result_status(
    payload: Mapping[str, object],
    platform: str,
) -> str | None:
    event = payload.get("hook_event_name")
    if event == "PostToolUseFailure":
        return "failure"
    if event != "PostToolUse":
        return None
    if platform == "claude":
        return "success"
    response = payload.get("tool_response")
    if isinstance(response, str):
        return "opaque"
    failed = _explicit_failure(response)
    if failed is not None:
        return "failure" if failed else "success"
    return None


def _report_feedback(
    event: str,
    *,
    opaque_codex_result: bool = False,
) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": (
                _CODEX_OPAQUE_REPORT_CONTEXT
                if opaque_codex_result
                else _REPORT_CONTEXT
            ),
        }
    }


def handle_tool_result(
    payload: Mapping[str, object],
    state_root: Path,
    *,
    platform: str,
) -> dict[str, object] | None:
    session_id = _session_id(payload)
    if session_id is None:
        return None
    try:
        lock = load_session_lock(state_root, session_id)
    except StateError:
        return None
    if lock is None:
        return None

    tool_use_id = _tool_use_id(payload)
    if tool_use_id is None or not matches_tool_use(lock, tool_use_id):
        return None

    status = _result_status(payload, platform)
    if status is None:
        return None
    action = _tool_action(payload)
    updated = record_result(lock, action, failed=status != "success")
    if updated is lock:
        return None
    if updated.phase == "RELEASED":
        delete_session_lock(state_root, session_id)
        return None
    save_session_lock(state_root, session_id, updated)
    event = str(payload.get("hook_event_name"))
    return _report_feedback(
        event,
        opaque_codex_result=status == "opaque",
    )


def handle_session_end(
    payload: Mapping[str, object],
    state_root: Path,
) -> None:
    session_id = _session_id(payload)
    if session_id is not None:
        delete_session_lock(state_root, session_id)
    return None


def handle_event(
    payload: Mapping[str, object],
    state_root: Path,
    *,
    platform: str,
) -> dict[str, object] | None:
    """Normalize one supported lifecycle event without executing the task."""

    if platform not in {"codex", "claude"}:
        raise ValueError("platform must be 'codex' or 'claude'")
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        return handle_user_prompt(payload, state_root)
    if event == "PreToolUse":
        return handle_pre_tool(payload, state_root)
    if event in {"PostToolUse", "PostToolUseFailure"}:
        return handle_tool_result(payload, state_root, platform=platform)
    if event == "SessionEnd":
        return handle_session_end(payload, state_root)
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-frontdoor-hook")
    parser.add_argument(
        "--platform",
        choices=("codex", "claude"),
        default=os.environ.get("AGENT_FRONTDOOR_PLATFORM"),
        required="AGENT_FRONTDOOR_PLATFORM" not in os.environ,
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "AGENT_FRONTDOOR_STATE_DIR",
                Path.home() / ".local/state/agent-frontdoor/intent-lock",
            )
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Read one hook event from stdin and emit only supported JSON output."""

    arguments = _parser().parse_args(argv)
    try:
        payload: Any = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"Invalid hook JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(payload, Mapping):
        print("Invalid hook JSON: root must be an object", file=sys.stderr)
        return 2
    try:
        output = handle_event(
            payload,
            arguments.state_dir,
            platform=arguments.platform,
        )
    except (StateError, ValueError) as error:
        print(f"Intent Lock hook failure: {error}", file=sys.stderr)
        return 2
    if output is not None:
        json.dump(output, sys.stdout, ensure_ascii=False, sort_keys=True)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
