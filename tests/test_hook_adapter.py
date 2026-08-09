"""Behavior tests for the optional Codex and Claude Code hook adapter."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from threading import Event, Thread, current_thread

import pytest

import frontdoor_hooks.hook as hook_module
from frontdoor_hooks.hook import handle_event
from frontdoor_hooks.state import StateError, load_session_lock


SESSION = "session-123"
ERROR_PROMPT = (
    "MCP client for `cloudflare-api` failed to start: "
    "invalid_grant: Grant not found"
)


def _payload(event: str, **values):
    return {
        "session_id": SESSION,
        "hook_event_name": event,
        **values,
    }


def _activate_target_lock(state_root: Path) -> dict[str, object]:
    result = handle_event(
        _payload("UserPromptSubmit", prompt=ERROR_PROMPT),
        state_root,
        platform="codex",
    )
    assert result is not None
    return result


def _activate_exact_lock(state_root: Path) -> None:
    result = handle_event(
        _payload(
            "UserPromptSubmit",
            prompt="codex mcp login cloudflare-apiしてや",
        ),
        state_root,
        platform="codex",
    )
    assert result is not None


def _accept_exact_tool(
    state_root: Path,
    *,
    tool_use_id: str = "accepted-tool",
) -> None:
    result = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id=tool_use_id,
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        state_root,
        platform="codex",
    )
    assert result is None


def _activate_report_hold(
    state_root: Path,
    *,
    prompt: str,
    command: str,
) -> None:
    assert handle_event(
        _payload("UserPromptSubmit", prompt=prompt),
        state_root,
        platform="codex",
    ) is not None
    action = {"command": command}
    assert handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="failed-tool",
            tool_input=action,
        ),
        state_root,
        platform="codex",
    ) is None
    assert handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="failed-tool",
            tool_input=action,
            tool_response={"exit_code": 1, "output": "failed"},
        ),
        state_root,
        platform="codex",
    ) is not None
    current = load_session_lock(state_root, SESSION)
    assert current is not None
    assert current.phase == "REPORT_REQUIRED"


def _assert_report_hold_preserved(
    state_root: Path,
    *,
    prompt: str,
    command: str,
) -> None:
    before = load_session_lock(state_root, SESSION)
    assert before is not None
    followup = handle_event(
        _payload("UserPromptSubmit", prompt=prompt),
        state_root,
        platform="codex",
    )
    denied = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="next-tool",
            tool_input={"command": command},
        ),
        state_root,
        platform="codex",
    )

    assert followup is not None
    current = load_session_lock(state_root, SESSION)
    assert current is not None
    assert current == before
    assert denied is not None
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert denied["hookSpecificOutput"]["permissionDecisionReason"] == (
        "A human-facing response is required before using another tool."
    )


def test_user_prompt_creates_lock_and_injects_bounded_context(
    tmp_path: Path,
) -> None:
    output = _activate_target_lock(tmp_path)

    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "INTENT_LOCK_ACTIVE epoch=1 mode=LITERAL_TARGET "
                "target=cloudflare-api. This checks task identity only and "
                "does not grant authority."
            ),
        }
    }
    assert load_session_lock(tmp_path, SESSION) is not None
    assert "invalid_grant" not in str(output)


def test_pre_tool_denies_lateral_target_and_silently_accepts_match(
    tmp_path: Path,
) -> None:
    _activate_target_lock(tmp_path)

    denied = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "npx wrangler whoami"},
        ),
        tmp_path,
        platform="codex",
    )
    matched = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="matched-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="codex",
    )

    assert denied == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Proposed action does not contain the locked literal target: "
                "cloudflare-api."
            ),
        }
    }
    assert matched is None


@pytest.mark.parametrize(
    ("command", "allowed"),
    [
        ("npx wrangler whoami # cloudflare-api", False),
        ("echo foo# cloudflare-api", True),
        (r"echo foo\# cloudflare-api", True),
        ('echo "foo# note" cloudflare-api', True),
        (r'echo "foo\" # cloudflare-api"', True),
        ("echo 'foo# note' cloudflare-api", True),
    ],
)
def test_literal_target_obeys_posix_comment_boundaries(
    tmp_path: Path,
    command: str,
    allowed: bool,
) -> None:
    _activate_target_lock(tmp_path)

    output = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="comment-boundary-tool",
            tool_input={"command": command},
        ),
        tmp_path,
        platform="codex",
    )

    if allowed:
        assert output is None
    else:
        assert output is not None
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert output["hookSpecificOutput"]["permissionDecisionReason"] == (
            "Proposed action does not contain the locked literal target: "
            "cloudflare-api."
        )


def test_literal_target_rejects_non_shell_payload_containing_target(
    tmp_path: Path,
) -> None:
    _activate_target_lock(tmp_path)

    output = handle_event(
        _payload(
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="patch-tool",
            tool_input={
                "patch": "*** Begin Patch\n+cloudflare-api\n*** End Patch"
            },
        ),
        tmp_path,
        platform="codex",
    )

    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert output["hookSpecificOutput"]["permissionDecisionReason"] == (
        "Intent matching requires a recognized shell action."
    )


def test_exact_command_requires_a_known_shell_tool_identity(tmp_path: Path) -> None:
    _activate_exact_lock(tmp_path)
    command = "codex mcp login cloudflare-api"

    unrelated = handle_event(
        _payload(
            "PreToolUse",
            tool_name="mcp__example__run",
            tool_input={"command": command},
        ),
        tmp_path,
        platform="codex",
    )
    unified_exec = handle_event(
        _payload(
            "PreToolUse",
            tool_name="exec_command",
            tool_use_id="unified-tool",
            tool_input={"cmd": command},
        ),
        tmp_path,
        platform="codex",
    )

    assert unrelated is not None
    assert unrelated["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert unified_exec is None


def test_exact_lock_rejects_matching_apply_patch_envelope_without_claim(
    tmp_path: Path,
) -> None:
    tool_input = {"patch": "*** Add File: cloudflare-api"}
    envelope = json.dumps(
        {"tool_name": "apply_patch", "tool_input": tool_input},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    activated = handle_event(
        _payload("UserPromptSubmit", prompt=f"Run `{envelope}`."),
        tmp_path,
        platform="codex",
    )
    assert activated is not None
    current = load_session_lock(tmp_path, SESSION)
    assert current is not None
    assert current.mode == "EXACT_COMMAND"

    denied = handle_event(
        _payload(
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="patch-tool",
            tool_input=tool_input,
        ),
        tmp_path,
        platform="codex",
    )

    assert denied is not None
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert denied["hookSpecificOutput"]["permissionDecisionReason"] == (
        "Intent matching requires a recognized shell action."
    )
    after = load_session_lock(tmp_path, SESSION)
    assert after is not None
    assert after.pending_tool_use_sha256 is None


@pytest.mark.parametrize("tool_name", ["Baſh", "Ｂash", "Básh"])
def test_non_ascii_tool_name_is_never_trusted_as_shell(
    tmp_path: Path,
    tool_name: str,
) -> None:
    _activate_target_lock(tmp_path)

    output = handle_event(
        _payload(
            "PreToolUse",
            tool_name=tool_name,
            tool_use_id="confusable-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert output["hookSpecificOutput"]["permissionDecisionReason"] == (
        "Intent matching requires a recognized shell action."
    )


def test_ascii_tool_name_normalizes_case_only(tmp_path: Path) -> None:
    _activate_target_lock(tmp_path)

    output = handle_event(
        _payload(
            "PreToolUse",
            tool_name="bAsH",
            tool_use_id="ascii-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is None


def test_matching_tool_without_tool_use_id_is_denied_as_uncorrelatable(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)

    output = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "tool use id" in output["hookSpecificOutput"][
        "permissionDecisionReason"
    ]


def test_stale_tool_result_cannot_mutate_a_new_lock_epoch(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path, tool_use_id="old-tool")
    old_epoch = load_session_lock(tmp_path, SESSION).intent_epoch
    handle_event(
        _payload("UserPromptSubmit", prompt="do the original request"),
        tmp_path,
        platform="codex",
    )
    current = load_session_lock(tmp_path, SESSION)
    assert current is not None
    assert current.intent_epoch == old_epoch + 1

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="old-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response={"exit_code": 0, "output": "ok"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is None
    assert load_session_lock(tmp_path, SESSION) == current


def test_concurrent_pre_tool_cannot_restore_replaced_intent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _activate_exact_lock(tmp_path)
    save_started = Event()
    resume_save = Event()
    prompt_finished = Event()
    real_save = hook_module.save_session_lock

    def gated_save(state_root, session_id, lock):
        if (
            current_thread().name == "old-pre-tool"
            and lock.pending_tool_use_sha256 is not None
        ):
            save_started.set()
            assert resume_save.wait(2)
        return real_save(state_root, session_id, lock)

    monkeypatch.setattr(hook_module, "save_session_lock", gated_save)
    results = []
    pre_tool = Thread(
        name="old-pre-tool",
        target=lambda: results.append(
            handle_event(
                _payload(
                    "PreToolUse",
                    tool_name="Bash",
                    tool_use_id="old-tool",
                    tool_input={"command": "codex mcp login cloudflare-api"},
                ),
                tmp_path,
                platform="codex",
            )
        ),
    )
    replacement = Thread(
        name="replacement-prompt",
        target=lambda: (
            handle_event(
                _payload("UserPromptSubmit", prompt="`git diff`"),
                tmp_path,
                platform="codex",
            ),
            prompt_finished.set(),
        ),
    )

    pre_tool.start()
    assert save_started.wait(2)
    replacement.start()
    prompt_finished.wait(0.2)
    resume_save.set()
    pre_tool.join(2)
    replacement.join(2)

    current = load_session_lock(tmp_path, SESSION)
    assert not pre_tool.is_alive()
    assert not replacement.is_alive()
    assert results == [None]
    assert current is not None
    assert current.display_targets == ("diff",)
    assert current.pending_tool_use_sha256 is None


def test_concurrent_old_result_cannot_delete_replacement_intent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path, tool_use_id="old-tool")
    delete_started = Event()
    resume_delete = Event()
    prompt_finished = Event()
    real_delete = hook_module.delete_session_lock

    def gated_delete(state_root, session_id):
        if current_thread().name == "old-result":
            delete_started.set()
            assert resume_delete.wait(2)
        return real_delete(state_root, session_id)

    monkeypatch.setattr(hook_module, "delete_session_lock", gated_delete)
    old_result = Thread(
        name="old-result",
        target=lambda: handle_event(
            _payload(
                "PostToolUse",
                tool_name="Bash",
                tool_use_id="old-tool",
                tool_input={"command": "codex mcp login cloudflare-api"},
                tool_response={"exit_code": 0, "output": "ok"},
            ),
            tmp_path,
            platform="codex",
        ),
    )
    replacement = Thread(
        name="replacement-prompt",
        target=lambda: (
            handle_event(
                _payload("UserPromptSubmit", prompt="`git diff`"),
                tmp_path,
                platform="codex",
            ),
            prompt_finished.set(),
        ),
    )

    old_result.start()
    assert delete_started.wait(2)
    replacement.start()
    prompt_finished.wait(0.2)
    resume_delete.set()
    old_result.join(2)
    replacement.join(2)

    current = load_session_lock(tmp_path, SESSION)
    assert not old_result.is_alive()
    assert not replacement.is_alive()
    assert current is not None
    assert current.display_targets == ("diff",)


def test_concurrent_old_failure_cannot_overwrite_replacement_intent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path, tool_use_id="old-tool")
    save_started = Event()
    resume_save = Event()
    prompt_finished = Event()
    real_save = hook_module.save_session_lock

    def gated_save(state_root, session_id, lock):
        if (
            current_thread().name == "old-failure"
            and lock.phase == "REPORT_REQUIRED"
        ):
            save_started.set()
            assert resume_save.wait(2)
        return real_save(state_root, session_id, lock)

    monkeypatch.setattr(hook_module, "save_session_lock", gated_save)
    old_failure = Thread(
        name="old-failure",
        target=lambda: handle_event(
            _payload(
                "PostToolUseFailure",
                tool_name="Bash",
                tool_use_id="old-tool",
                tool_input={"command": "codex mcp login cloudflare-api"},
                error="failed",
            ),
            tmp_path,
            platform="claude",
        ),
    )
    replacement = Thread(
        name="replacement-prompt",
        target=lambda: (
            handle_event(
                _payload(
                    "UserPromptSubmit",
                    prompt="new task: `git diff`",
                ),
                tmp_path,
                platform="codex",
            ),
            prompt_finished.set(),
        ),
    )

    old_failure.start()
    assert save_started.wait(2)
    replacement.start()
    prompt_finished.wait(0.2)
    resume_save.set()
    old_failure.join(2)
    replacement.join(2)

    current = load_session_lock(tmp_path, SESSION)
    assert not old_failure.is_alive()
    assert not replacement.is_alive()
    assert current is not None
    assert current.display_targets == ("diff",)
    assert current.phase == "DIRECT_REQUIRED"


def test_unaccepted_tool_result_cannot_mutate_current_lock(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    current = load_session_lock(tmp_path, SESSION)

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="never-accepted",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response={"exit_code": 0, "output": "ok"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is None
    assert load_session_lock(tmp_path, SESSION) == current


def test_second_matching_tool_is_denied_until_first_result_arrives(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path, tool_use_id="first-tool")

    second = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="second-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="codex",
    )
    first_result = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="first-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response={"exit_code": 1, "output": "failed"},
        ),
        tmp_path,
        platform="codex",
    )

    assert second is not None
    assert second["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "result pending" in second["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
    assert first_result is not None
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


def test_ambiguous_correction_keeps_report_required_lock(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)
    handle_event(
        _payload(
            "PostToolUseFailure",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            error="failed",
        ),
        tmp_path,
        platform="claude",
    )

    output = handle_event(
        _payload("UserPromptSubmit", prompt="the original request"),
        tmp_path,
        platform="claude",
    )

    assert output is not None
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


@pytest.mark.parametrize(
    "prompt",
    [
        "Why did that fail?",
        "Thanks.",
        "It will rain on Monday.",
        "Fix docs.",
        "Work on another project.",
        "READMEの文章を監査して結果だけ教えて",
        "Tell me what failed",
        "Review the failure",
        "Explain why cloudflare-api failed",
        "Explain the problem.",
        "Can you explain this issue?",
        "`codex mcp login cloudflare-api`",
        "do the original request",
        "proceed",
        "Okay?",
        "What about that?",
    ],
)
def test_ordinary_prompt_keeps_report_hold_and_denies_next_tool(
    tmp_path: Path,
    prompt: str,
) -> None:
    _activate_report_hold(
        tmp_path,
        prompt="codex mcp login cloudflare-apiしてや",
        command="codex mcp login cloudflare-api",
    )
    _assert_report_hold_preserved(
        tmp_path,
        prompt=prompt,
        command="codex mcp login cloudflare-api",
    )


@pytest.mark.parametrize(
    "prompt",
    [
        "Check https://example.com/private.",
        "Explain the problem with https://example.com/private.",
    ],
)
def test_hidden_target_followup_keeps_report_hold_and_denies_next_tool(
    tmp_path: Path,
    prompt: str,
) -> None:
    _activate_report_hold(
        tmp_path,
        prompt="component https://example.com/private failed during startup",
        command="curl https://example.com/private",
    )
    initial = load_session_lock(tmp_path, SESSION)
    assert initial is not None
    assert initial.display_targets == ()
    _assert_report_hold_preserved(
        tmp_path,
        prompt=prompt,
        command="curl https://example.com/private",
    )


def test_same_error_target_keeps_report_hold_and_denies_next_tool(
    tmp_path: Path,
) -> None:
    _activate_report_hold(
        tmp_path,
        prompt=ERROR_PROMPT,
        command="codex mcp login cloudflare-api",
    )
    _assert_report_hold_preserved(
        tmp_path,
        prompt="component cloudflare-api failed again",
        command="codex mcp login cloudflare-api",
    )


@pytest.mark.parametrize(
    (
        "initial_prompt",
        "initial_command",
        "replacement_prompt",
        "replacement_command",
        "expected_mode",
        "expected_targets",
    ),
    [
        (
            "codex mcp login cloudflare-apiしてや",
            "codex mcp login cloudflare-api",
            "new task: `git status`",
            "git status",
            "EXACT_COMMAND",
            ("status",),
        ),
        (
            ERROR_PROMPT,
            "codex mcp login cloudflare-api",
            "別件: component docs failed during validation",
            "echo docs",
            "LITERAL_TARGET",
            ("docs",),
        ),
        (
            "codex mcp login cloudflare-apiしてや",
            "codex mcp login cloudflare-api",
            "NEW TASK: `codex mcp login cloudflare-api`",
            "codex mcp login cloudflare-api",
            "EXACT_COMMAND",
            ("cloudflare-api",),
        ),
    ],
)
def test_explicit_new_task_marker_replaces_hold_and_accepts_next_tool(
    tmp_path: Path,
    initial_prompt: str,
    initial_command: str,
    replacement_prompt: str,
    replacement_command: str,
    expected_mode: str,
    expected_targets: tuple[str, ...],
) -> None:
    _activate_report_hold(
        tmp_path,
        prompt=initial_prompt,
        command=initial_command,
    )
    held = load_session_lock(tmp_path, SESSION)
    assert held is not None

    replacement = handle_event(
        _payload("UserPromptSubmit", prompt=replacement_prompt),
        tmp_path,
        platform="codex",
    )
    fresh = load_session_lock(tmp_path, SESSION)
    assert fresh is not None
    assert replacement is not None
    assert fresh.phase == "DIRECT_REQUIRED"
    assert fresh.mode == expected_mode
    assert fresh.intent_epoch == held.intent_epoch + 1
    assert fresh.display_targets == expected_targets
    accepted = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="replacement-tool",
            tool_input={"command": replacement_command},
        ),
        tmp_path,
        platform="codex",
    )

    current = load_session_lock(tmp_path, SESSION)
    assert current is not None
    assert current.phase == "DIRECT_REQUIRED"
    assert current.mode == expected_mode
    assert current.intent_epoch == fresh.intent_epoch
    assert current.display_targets == expected_targets
    assert current.pending_tool_use_sha256 is not None
    assert accepted is None


def test_codex_failed_post_tool_requires_report_and_blocks_next_tool(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)
    action = {"command": "codex mcp login cloudflare-api"}

    feedback = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input=action,
            tool_response={"exit_code": 1, "output": "server not found"},
        ),
        tmp_path,
        platform="codex",
    )
    denied = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "rg cloudflare-api ."},
        ),
        tmp_path,
        platform="codex",
    )

    assert feedback == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "INTENT_LOCK_REPORT_REQUIRED: report the direct failure; do not "
                "try an alternative tool or subsystem."
            ),
        },
    }
    assert denied is not None
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


def test_claude_failure_event_produces_equivalent_report_lock(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)

    feedback = handle_event(
        _payload(
            "PostToolUseFailure",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            error="Exit code 1",
            is_interrupt=False,
        ),
        tmp_path,
        platform="claude",
    )

    assert feedback == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUseFailure",
            "additionalContext": (
                "INTENT_LOCK_REPORT_REQUIRED: report the direct failure; do not "
                "try an alternative tool or subsystem."
            ),
        }
    }
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


def test_structured_codex_success_releases_and_removes_adapter_state(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response={"exit_code": 0, "output": "ok"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is None
    assert load_session_lock(tmp_path, SESSION) is None


@pytest.mark.parametrize(
    "tool_response",
    [
        {"exit_code": 0, "success": False},
        {"exit_code": 0, "isError": True},
        {"exit_code": 1, "success": True},
    ],
)
def test_conflicting_codex_status_fields_never_release_lock(
    tmp_path: Path,
    tool_response: dict[str, object],
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response=tool_response,
        ),
        tmp_path,
        platform="codex",
    )

    current = load_session_lock(tmp_path, SESSION)
    assert output is not None
    assert "report the direct failure" in str(output)
    assert current is not None
    assert current.phase == "REPORT_REQUIRED"


def test_literal_target_success_stays_locked_without_failure_feedback(
    tmp_path: Path,
) -> None:
    _activate_target_lock(tmp_path)
    action = {"command": "codex mcp list cloudflare-api"}
    assert handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="target-tool",
            tool_input=action,
        ),
        tmp_path,
        platform="codex",
    ) is None

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="target-tool",
            tool_input=action,
            tool_response={"exit_code": 0, "output": "ok"},
        ),
        tmp_path,
        platform="codex",
    )

    current = load_session_lock(tmp_path, SESSION)
    assert output is None
    assert current is not None
    assert current.phase == "DIRECT_REQUIRED"
    assert current.pending_tool_use_sha256 is None


def test_actual_codex_raw_result_requires_human_report_before_more_tools(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response="Error: server not found",
        ),
        tmp_path,
        platform="codex",
    )

    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "INTENT_LOCK_REPORT_REQUIRED: report the direct result; "
                "Codex Bash hooks do not expose its exit status. Do not try "
                "another tool or subsystem first."
            ),
        }
    }
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


def test_actual_codex_raw_success_is_also_held_for_report(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response="Successfully logged in",
        ),
        tmp_path,
        platform="codex",
    )

    assert output is not None
    assert "report the direct result" in str(output)
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


def test_codex_raw_json_stdout_cannot_forge_structured_success(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            tool_response='{"success": true}',
        ),
        tmp_path,
        platform="codex",
    )

    assert output is not None
    assert "do not expose its exit status" in str(output)
    assert load_session_lock(tmp_path, SESSION).phase == "REPORT_REQUIRED"


def test_statusless_codex_mapping_is_opaque_instead_of_staying_pending(
    tmp_path: Path,
) -> None:
    _activate_target_lock(tmp_path)
    action = {"command": "codex mcp list cloudflare-api"}
    assert handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="mapping-tool",
            tool_input=action,
        ),
        tmp_path,
        platform="codex",
    ) is None

    output = handle_event(
        _payload(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="mapping-tool",
            tool_input=action,
            tool_response={"content": [{"type": "text", "text": "done"}]},
        ),
        tmp_path,
        platform="codex",
    )

    current = load_session_lock(tmp_path, SESSION)
    assert output is not None
    assert "report the direct result" in str(output)
    assert current is not None
    assert current.phase == "REPORT_REQUIRED"
    assert current.pending_tool_use_sha256 is None


def test_human_correction_cannot_bypass_adapter_report_hold(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    _accept_exact_tool(tmp_path)
    handle_event(
        _payload(
            "PostToolUseFailure",
            tool_name="Bash",
            tool_use_id="accepted-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
            error="Exit code 1",
        ),
        tmp_path,
        platform="claude",
    )

    output = handle_event(
        _payload("UserPromptSubmit", prompt="まず最初の依頼して"),
        tmp_path,
        platform="claude",
    )

    assert output is not None
    current = load_session_lock(tmp_path, SESSION)
    assert current is not None
    assert current.phase == "REPORT_REQUIRED"
    denied = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="next-tool",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="claude",
    )
    assert denied is not None
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert denied["hookSpecificOutput"]["permissionDecisionReason"] == (
        "A human-facing response is required before using another tool."
    )


@pytest.mark.parametrize(
    "prompt",
    [
        "new task: Fix docs.",
        "NEW TASK: Run tests.",
        "\u3000NeW TaSk: Translate this sentence",
        "別件: READMEの文章を監査して結果だけ教えて",
        "  別件: なぜ空は青いのですか",
        "new task:\u200bA\u200d",
        "new task:\u200b7\u200d",
        "new task:\u200b!\u200d",
        "別件:\u200b©\u200d",
    ],
)
def test_explicit_new_task_marker_clears_report_hold(
    tmp_path: Path,
    prompt: str,
) -> None:
    _activate_report_hold(
        tmp_path,
        prompt="codex mcp login cloudflare-apiしてや",
        command="codex mcp login cloudflare-api",
    )

    output = handle_event(
        _payload(
            "UserPromptSubmit",
            prompt=prompt,
        ),
        tmp_path,
        platform="codex",
    )

    assert output is None
    assert load_session_lock(tmp_path, SESSION) is None
    assert handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="unlocked-tool",
            tool_input={"command": "git status"},
        ),
        tmp_path,
        platform="codex",
    ) is None


@pytest.mark.parametrize(
    "prompt",
    [
        "new task:",
        "NEW TASK:   ",
        "別件:",
        "Please use new task: Fix docs.",
        '"new task: Fix docs."',
        "new taſk: Fix docs.",
        "new task:\u200b",
        "別件:\u200d",
        "new task:\ufeff",
        "別件:\x00",
        "別件:\u0301",
        "new task: \t\u200b\u200d\ufeff\x00\u00a0\u2028\u3000\n",
    ],
)
def test_invalid_or_invisible_marker_keeps_hold_and_denies_next_tool(
    tmp_path: Path,
    prompt: str,
) -> None:
    _activate_report_hold(
        tmp_path,
        prompt="codex mcp login cloudflare-apiしてや",
        command="codex mcp login cloudflare-api",
    )
    _assert_report_hold_preserved(
        tmp_path,
        prompt=prompt,
        command="codex mcp login cloudflare-api",
    )


def test_session_end_deletes_only_current_session_state(tmp_path: Path) -> None:
    _activate_exact_lock(tmp_path)

    assert handle_event(
        _payload("SessionEnd", reason="other"),
        tmp_path,
        platform="codex",
    ) is None
    assert load_session_lock(tmp_path, SESSION) is None


def test_missing_session_fails_closed_for_pre_tool(tmp_path: Path) -> None:
    output = handle_event(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "npx wrangler whoami"},
        },
        tmp_path,
        platform="codex",
    )

    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Intent Lock cannot identify this session; tool use is denied."
            ),
        }
    }


def test_malformed_persisted_state_fails_closed_for_pre_tool(
    tmp_path: Path,
) -> None:
    _activate_exact_lock(tmp_path)
    path = next(tmp_path.glob("*.json"))
    path.write_text("{}", encoding="utf-8")

    output = handle_event(
        _payload(
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "codex mcp login cloudflare-api"},
        ),
        tmp_path,
        platform="codex",
    )

    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert output["hookSpecificOutput"]["permissionDecisionReason"] == (
        "INTENT_LOCK_STATE_ERROR: Intent Lock state is unavailable; "
        "the event is blocked."
    )


def test_state_error_private_path_is_redacted_from_hook_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_path = "/private/operator/secrets/intent-lock-state"

    def fail_guard(state_root: Path, session_id: str):
        raise StateError(f"unable to inspect {private_path}")

    monkeypatch.setattr(hook_module, "session_state_guard", fail_guard)
    monkeypatch.setattr(
        hook_module.sys,
        "stdin",
        StringIO(json.dumps(_payload("UserPromptSubmit", prompt=ERROR_PROMPT))),
    )

    exit_code = hook_module.main(
        ["--platform", "codex", "--state-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == {
        "decision": "block",
        "reason": (
            "INTENT_LOCK_STATE_ERROR: Intent Lock state is unavailable; "
            "the event is blocked."
        ),
    }
    assert captured.err == ""
    assert private_path not in captured.out
    assert private_path not in captured.err


def test_uncaught_state_error_private_path_is_redacted_from_hook_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_path = "/private/operator/secrets/intent-lock-state"

    def fail_event(*args, **kwargs):
        raise StateError(f"unable to inspect {private_path}")

    monkeypatch.setattr(hook_module, "handle_event", fail_event)
    monkeypatch.setattr(hook_module.sys, "stdin", StringIO("{}"))

    exit_code = hook_module.main(
        ["--platform", "codex", "--state-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert captured.err == (
        "INTENT_LOCK_STATE_ERROR: Intent Lock state is unavailable; "
        "the event is blocked.\n"
    )
    assert private_path not in captured.out
    assert private_path not in captured.err
