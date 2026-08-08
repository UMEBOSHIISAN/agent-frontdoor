"""Behavior tests for the optional Codex and Claude Code hook adapter."""

from __future__ import annotations

from pathlib import Path

from frontdoor_hooks.hook import handle_event
from frontdoor_hooks.state import load_session_lock


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


def test_human_correction_relocks_failed_intent(
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
    assert "epoch=2" in output["hookSpecificOutput"]["additionalContext"]
    assert load_session_lock(tmp_path, SESSION).phase == "DIRECT_REQUIRED"


def test_substantive_new_prompt_clears_previous_lock(tmp_path: Path) -> None:
    _activate_exact_lock(tmp_path)

    output = handle_event(
        _payload(
            "UserPromptSubmit",
            prompt="READMEの文章を監査して結果だけ教えて",
        ),
        tmp_path,
        platform="codex",
    )

    assert output is None
    assert load_session_lock(tmp_path, SESSION) is None


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
    assert "state is invalid" in output["hookSpecificOutput"][
        "permissionDecisionReason"
    ]
