"""Behavior tests for the pure cross-agent intent-lock contract."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from frontdoor.intent_lock import (
    IntentDecision,
    IntentLock,
    derive_lock,
    evaluate_action,
    lock_from_dict,
    lock_to_dict,
    record_result,
)


ERROR_PROMPT = """\
MCP client for `cloudflare-api` failed to start: OAuth refresh token rejected.
invalid_grant: Grant not found
"""


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
        reason=(
            "The direct action failed. Report that result to the human before "
            "using another tool."
        ),
    )


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

