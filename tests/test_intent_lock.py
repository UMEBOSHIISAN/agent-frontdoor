"""Behavior tests for the pure cross-agent intent-lock contract."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from frontdoor.intent_lock import (
    IntentDecision,
    IntentLock,
    bind_tool_use,
    derive_lock,
    evaluate_action,
    lock_from_dict,
    lock_to_dict,
    matches_tool_use,
    record_result,
)


ERROR_PROMPT = """\
MCP client for `cloudflare-api` failed to start: OAuth refresh token rejected.
invalid_grant: Grant not found
"""
AWS_ACCESS_KEY_FIXTURE = "AK" + "IA1234567890ABCDEF"
GITHUB_TOKEN_FIXTURE = "gh" + "p_1234567890abcdefghijklmn"
PRIVATE_IP_FIXTURE = ".".join(("10", "0", "0", "5"))


def test_structured_error_derives_literal_target_without_raw_prompt() -> None:
    lock = derive_lock(ERROR_PROMPT)

    assert lock is not None
    assert lock.schema_version == "intent-lock.v1"
    assert lock.intent_epoch == 1
    assert lock.mode == "LITERAL_TARGET"
    assert lock.phase == "DIRECT_REQUIRED"
    assert lock.display_targets == ("cloudflare-api",)
    assert len(lock.source_prompt_sha256) == 64
    assert len(lock.target_token_sha256) == 1

    serialized = json.dumps(lock_to_dict(lock), sort_keys=True)
    assert ERROR_PROMPT not in serialized
    assert "invalid_grant" not in serialized
    assert "refresh token" not in serialized


@pytest.mark.parametrize(
    "prompt",
    [
        "Error: `cloudflare-api` failed during startup",
        "The identifier `cloudflare-api` is invalid",
    ],
)
def test_backticked_identifier_near_error_word_derives_target(prompt: str) -> None:
    lock = derive_lock(prompt)

    assert lock is not None
    assert lock.mode == "LITERAL_TARGET"
    assert lock.display_targets == ("cloudflare-api",)


@pytest.mark.parametrize(
    "prompt",
    [
        "restart the server locally",
        "render the component locally",
    ],
)
def test_server_and_component_prose_without_error_evidence_is_not_locked(
    prompt: str,
) -> None:
    assert derive_lock(prompt) is None


@pytest.mark.parametrize(
    "prompt",
    [
        "Error: server cloudflare-api not found",
        "component cloudflare-api failed during startup",
    ],
)
def test_structured_server_or_component_error_derives_target(prompt: str) -> None:
    lock = derive_lock(prompt)

    assert lock is not None
    assert lock.display_targets == ("cloudflare-api",)


@pytest.mark.parametrize(
    ("prompt", "credential"),
    [
        (
            f"Error: invalid token `{GITHUB_TOKEN_FIXTURE}`",
            GITHUB_TOKEN_FIXTURE,
        ),
        (
            f"AWS access key `{AWS_ACCESS_KEY_FIXTURE}` is invalid",
            AWS_ACCESS_KEY_FIXTURE,
        ),
        (
            "invalid token `A1b2C3d4E5f6G7h8I9j0K1l2`",
            "A1b2C3d4E5f6G7h8I9j0K1l2",
        ),
    ],
)
def test_credential_shaped_error_targets_are_never_persisted_or_displayed(
    prompt: str,
    credential: str,
) -> None:
    lock = derive_lock(prompt)

    assert lock is not None
    assert lock.display_targets == ()
    assert credential not in json.dumps(lock_to_dict(lock), sort_keys=True)


def test_secret_label_followed_by_password_context_is_never_displayed() -> None:
    prompt = "The value `hunter2` was the password and is invalid"

    lock = derive_lock(prompt)

    assert lock is not None
    assert lock.display_targets == ()
    assert "hunter2" not in json.dumps(lock_to_dict(lock), sort_keys=True)


@pytest.mark.parametrize(
    "command",
    [
        "curl https://alice:letmein@example.com/private",
        "curl ftp://alice:huntertwo@example.com/private",
        "ssh alice@example.com",
        "curl https://example.com/privatevalue",
        f"ssh {PRIVATE_IP_FIXTURE}",
        "curl internal.example.com",
        "python relative/private_script.py",
    ],
)
def test_exact_command_network_targets_are_hashed_but_never_displayed(
    command: str,
) -> None:
    lock = derive_lock(f"`{command}`")

    assert lock is not None
    assert lock.mode == "EXACT_COMMAND"
    assert lock.display_targets == ()
    assert command.split()[-1] not in json.dumps(lock_to_dict(lock))
    assert evaluate_action(lock, command).allowed


@pytest.mark.parametrize(
    "prompt",
    [
        "Error: server not found",
        "Error: component failed",
        "failed component startup",
        "client for authentication failed",
        "Error: server is unavailable",
        "component failed with an error",
    ],
)
def test_identifier_free_errors_do_not_invent_literal_targets(
    prompt: str,
) -> None:
    assert derive_lock(prompt) is None


def test_target_lock_denies_adjacent_product_and_allows_literal_target() -> None:
    lock = derive_lock(ERROR_PROMPT)
    assert lock is not None

    denied = evaluate_action(lock, "npx wrangler whoami")
    allowed = evaluate_action(lock, "codex mcp login cloudflare-api")

    assert denied == IntentDecision(
        allowed=False,
        code="literal_target_mismatch",
        reason=(
            "Proposed action does not contain the locked literal target: "
            "cloudflare-api."
        ),
    )
    assert allowed.allowed
    assert allowed.code == "literal_target_match"


def test_natural_language_exact_command_requires_exact_normalized_action() -> None:
    prompt = "codex mcp login cloudflare-apiしてや"

    lock = derive_lock(prompt)

    assert lock is not None
    assert lock.mode == "EXACT_COMMAND"
    assert lock.display_targets == ("cloudflare-api",)
    assert lock.exact_command_sha256 is not None
    assert evaluate_action(lock, "codex   mcp login cloudflare-api").allowed
    assert not evaluate_action(lock, "codex mcp list").allowed
    assert not evaluate_action(lock, "npx wrangler whoami").allowed
    serialized = json.dumps(lock_to_dict(lock), sort_keys=True)
    assert "codex mcp login" not in serialized


def test_fenced_shell_command_derives_exact_lock() -> None:
    lock = derive_lock(
        "Run this exact command:\n"
        "```bash\n"
        "codex mcp login cloudflare-api\n"
        "```"
    )

    assert lock is not None
    assert lock.mode == "EXACT_COMMAND"
    assert evaluate_action(lock, "codex mcp login cloudflare-api").allowed


@pytest.mark.parametrize(
    "prompt",
    [
        "Do not run this command:\n```bash\ngit status\n```",
        "Never execute:\n$ git status",
    ],
)
def test_negated_fenced_and_shell_line_commands_do_not_create_locks(
    prompt: str,
) -> None:
    assert derive_lock(prompt) is None


@pytest.mark.parametrize(
    "prompt",
    [
        "Run `git status`, but don't run it.",
        "Run `git status`; actually, never execute that command.",
        "Please run `git status` -- wait, do not run it.",
        "Please run: `git status`\nstop",
        "Please run: `git status`\nabort",
        "Run this exact command:\n```bash\ngit status\n```\nDo not run it.",
        "実行して `git status`。やっぱりやめて。",
    ],
)
def test_post_command_cancellation_does_not_create_exact_lock(
    prompt: str,
) -> None:
    assert derive_lock(prompt) is None


@pytest.mark.parametrize(
    "prompt",
    [
        "Run git status please.",
        "git status please",
        "Don't run git status; run git diff.",
        "The error mentions git status but do not execute it.",
    ],
)
def test_prose_and_negated_command_mentions_do_not_create_exact_locks(
    prompt: str,
) -> None:
    assert derive_lock(prompt) is None


def test_negated_inline_command_is_skipped_for_affirmative_command() -> None:
    lock = derive_lock("Do not run `git status`; run `git diff`.")

    assert lock is not None
    assert not evaluate_action(lock, "git status").allowed
    assert evaluate_action(lock, "git diff").allowed


def test_negating_a_later_command_does_not_cancel_the_first_command() -> None:
    lock = derive_lock("Run `git status`, but do not run `git diff`.")

    assert lock is not None
    assert evaluate_action(lock, "git status").allowed
    assert not evaluate_action(lock, "git diff").allowed


def test_inline_command_in_failure_prose_does_not_become_exact_intent() -> None:
    assert derive_lock("The command `git status` failed; inspect the error.") is None


@pytest.mark.parametrize(
    ("locked_command", "different_action"),
    [
        ("git add 'foo bar'", "git add foo bar"),
        ("git add 'foo; touch /tmp/other'", "git add foo; touch /tmp/other"),
        ("bash -c 'echo safe; exit 1'", "bash -c echo safe; exit 1"),
        ("git add '>'", "git add >"),
        (
            "python -c pass touch /tmp/other",
            "python -c pass\ntouch /tmp/other",
        ),
    ],
)
def test_exact_command_hash_preserves_quotes_and_shell_boundaries(
    locked_command: str,
    different_action: str,
) -> None:
    lock = derive_lock(f"`{locked_command}`")
    assert lock is not None

    assert evaluate_action(lock, locked_command).allowed
    assert not evaluate_action(lock, different_action).allowed


@pytest.mark.parametrize(
    "different_action",
    [
        "\ngit status",
        "git status\n",
        "\rgit status",
        "git status\r",
        "\vgit status",
        "git status\v",
    ],
)
def test_exact_command_hash_preserves_edge_vertical_whitespace(
    different_action: str,
) -> None:
    lock = derive_lock("`git status`")
    assert lock is not None

    assert not evaluate_action(lock, different_action).allowed


def test_failed_matching_action_requires_report_before_any_other_tool() -> None:
    lock = derive_lock("`codex mcp login cloudflare-api`")
    assert lock is not None

    failed = record_result(
        lock,
        "codex mcp login cloudflare-api",
        failed=True,
    )

    assert failed.phase == "REPORT_REQUIRED"
    assert evaluate_action(failed, "rg cloudflare-api .") == IntentDecision(
        allowed=False,
        code="report_required",
        reason="A human-facing response is required before using another tool.",
    )


def test_tool_use_binding_is_epoch_local_and_persists_only_a_digest() -> None:
    lock = derive_lock("`codex mcp login cloudflare-api`")
    assert lock is not None

    bound = bind_tool_use(lock, "raw-tool-use-id")

    assert bound.intent_epoch == lock.intent_epoch
    assert bound.pending_tool_use_sha256 is not None
    assert len(bound.pending_tool_use_sha256) == 64
    assert "raw-tool-use-id" not in json.dumps(lock_to_dict(bound))
    assert matches_tool_use(bound, "raw-tool-use-id")
    assert not matches_tool_use(bound, "different-tool-use-id")
    relocked = derive_lock("do the original request", previous=bound)
    assert relocked is not None
    assert relocked.pending_tool_use_sha256 is None


def test_success_releases_exact_command_but_keeps_target_lock_bounded() -> None:
    exact = derive_lock("`codex mcp login cloudflare-api`")
    target = derive_lock(ERROR_PROMPT)
    assert exact is not None
    assert target is not None

    exact_after = record_result(
        exact,
        "codex mcp login cloudflare-api",
        failed=False,
    )
    target_after = record_result(
        target,
        "codex mcp list cloudflare-api",
        failed=False,
    )

    assert exact_after.phase == "RELEASED"
    assert evaluate_action(exact_after, "npx wrangler whoami").allowed
    assert target_after.phase == "DIRECT_REQUIRED"
    assert not evaluate_action(target_after, "npx wrangler whoami").allowed


def test_released_lock_is_terminal_for_later_results() -> None:
    lock = derive_lock("`git status`")
    assert lock is not None
    released = record_result(lock, "git status", failed=False)

    assert released.phase == "RELEASED"
    assert record_result(released, "unrelated action", failed=True) is released


@pytest.mark.parametrize(
    "prompt",
    [
        "まず最初の依頼して",
        "do the original request",
        "やって",
        "proceed",
    ],
)
def test_human_relock_preserves_previous_intent(prompt: str) -> None:
    previous = derive_lock("`codex mcp login cloudflare-api`")
    assert previous is not None
    failed = record_result(
        previous,
        "codex mcp login cloudflare-api",
        failed=True,
    )

    relocked = derive_lock(prompt, previous=failed)

    assert relocked is not None
    assert relocked.intent_epoch == failed.intent_epoch + 1
    assert relocked.phase == "DIRECT_REQUIRED"
    assert relocked.mode == failed.mode
    assert relocked.exact_command_sha256 == failed.exact_command_sha256
    assert relocked.target_token_sha256 == failed.target_token_sha256


@pytest.mark.parametrize(
    "prompt",
    [
        "do not retry the original request",
        "never run the first request",
        "cancel the original request",
        "ignore the first request",
        "最初の依頼はやらないで",
    ],
)
def test_negated_correction_holds_instead_of_reenabling_previous_action(
    prompt: str,
) -> None:
    previous = derive_lock("`codex mcp login cloudflare-api`")
    assert previous is not None
    failed = record_result(
        previous,
        "codex mcp login cloudflare-api",
        failed=True,
    )

    held = derive_lock(prompt, previous=failed)

    assert held is not None
    assert held.intent_epoch == failed.intent_epoch + 1
    assert held.phase == "REPORT_REQUIRED"
    assert not evaluate_action(
        held,
        "codex mcp login cloudflare-api",
    ).allowed


def test_negated_correction_stops_a_not_yet_run_previous_action() -> None:
    previous = derive_lock("`git status`")
    assert previous is not None

    held = derive_lock("do not run the original request", previous=previous)

    assert held is not None
    assert held.phase == "REPORT_REQUIRED"
    assert held.intent_epoch == previous.intent_epoch + 1
    assert not evaluate_action(held, "git status").allowed


@pytest.mark.parametrize(
    "prompt",
    [
        "do the original request, but do not do it",
        "do the original request—actually, don't",
        "do the original request; cancel it",
    ],
)
def test_cancellation_after_affirmative_correction_never_relocks(
    prompt: str,
) -> None:
    previous = derive_lock("`git status`")
    assert previous is not None

    held = derive_lock(prompt, previous=previous)

    assert held is not None
    assert held.phase == "REPORT_REQUIRED"
    assert held.intent_epoch == previous.intent_epoch + 1
    assert not evaluate_action(held, "git status").allowed


@pytest.mark.parametrize(
    "prompt",
    [
        "stop",
        "cancel it",
        "abort",
        "skip it",
        "do not do it",
        "やめて",
        "キャンセルして",
    ],
)
def test_standalone_cancellation_holds_active_lock(prompt: str) -> None:
    previous = derive_lock("`git status`")
    assert previous is not None

    held = derive_lock(prompt, previous=previous)

    assert held is not None
    assert held.phase == "REPORT_REQUIRED"
    assert held.intent_epoch == previous.intent_epoch + 1
    assert not evaluate_action(held, "git status").allowed


def test_ambiguous_original_request_mention_preserves_previous_hold() -> None:
    previous = derive_lock("`git status`")
    assert previous is not None
    held = record_result(previous, "git status", failed=True)

    assert derive_lock("the original request", previous=held) is held


def test_substantive_unrelated_prompt_releases_previous_lock() -> None:
    previous = derive_lock("`codex mcp login cloudflare-api`")
    assert previous is not None

    assert derive_lock(
        "READMEの文章を監査して結果だけ教えて",
        previous=previous,
    ) is None


def test_lock_serialization_round_trip_is_validated_and_immutable() -> None:
    lock = derive_lock(ERROR_PROMPT)
    assert lock is not None
    original = deepcopy(lock)

    restored = lock_from_dict(lock_to_dict(lock))

    assert restored == lock
    assert lock == original

    malformed = lock_to_dict(lock)
    malformed["phase"] = "WANDER"
    with pytest.raises(ValueError, match="invalid intent-lock.v1"):
        lock_from_dict(malformed)


def test_record_result_ignores_mismatched_action_without_mutation() -> None:
    lock = derive_lock(ERROR_PROMPT)
    assert lock is not None

    assert record_result(lock, "npx wrangler whoami", failed=True) is lock


def test_contract_dataclass_is_frozen() -> None:
    lock = derive_lock(ERROR_PROMPT)
    assert isinstance(lock, IntentLock)

    with pytest.raises(AttributeError):
        lock.phase = "RELEASED"  # type: ignore[misc]
