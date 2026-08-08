"""Executable cross-platform regression fixtures for the hook adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from frontdoor_hooks.state import load_session_lock


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "intent-lock"
EXAMPLES = ROOT / "adapters" / "examples"


def _run_hook(
    payload: object,
    *,
    platform: str,
    state_root: Path,
    serialize: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT / "src"), str(ROOT / "adapters" / "src"))
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "frontdoor_hooks.hook",
            "--platform",
            platform,
            "--state-dir",
            str(state_root),
        ],
        input=json.dumps(payload) if serialize else str(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=environment,
    )


@pytest.mark.parametrize(
    ("fixture_name", "platform"),
    [
        ("codex_failure_sequence.json", "codex"),
        ("claude_failure_sequence.json", "claude"),
    ],
)
def test_platform_sequence_reaches_same_report_required_state(
    tmp_path: Path,
    fixture_name: str,
    platform: str,
) -> None:
    sequence = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))

    outputs = []
    for event in sequence["events"]:
        result = _run_hook(
            event["input"],
            platform=platform,
            state_root=tmp_path,
        )
        assert result.returncode == event["returncode"], result.stderr
        outputs.append(json.loads(result.stdout) if result.stdout else None)

    assert outputs[0]["hookSpecificOutput"]["hookEventName"] == (
        "UserPromptSubmit"
    )
    assert outputs[1]["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert outputs[2] is None
    assert "REPORT_REQUIRED" in str(outputs[3])
    assert outputs[4]["hookSpecificOutput"]["permissionDecision"] == "deny"
    lock = load_session_lock(tmp_path, sequence["session_id"])
    assert lock is not None
    assert lock.phase == "REPORT_REQUIRED"


def test_cli_rejects_malformed_json_without_echoing_input(tmp_path: Path) -> None:
    secret_marker = "do-not-echo-this-value"
    result = _run_hook(
        f'{{"secret":"{secret_marker}"',
        platform="codex",
        state_root=tmp_path,
        serialize=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert secret_marker not in result.stderr
    assert result.stderr.startswith("Invalid hook JSON:")


def test_public_examples_register_required_platform_events() -> None:
    codex = json.loads(
        (EXAMPLES / "codex-hooks.json").read_text(encoding="utf-8")
    )
    claude = json.loads(
        (EXAMPLES / "claude-settings.json").read_text(encoding="utf-8")
    )

    assert set(codex["hooks"]) == {
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "SessionEnd",
    }
    assert set(claude["hooks"]) == {
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "SessionEnd",
    }
    for event in codex["hooks"].values():
        command = event[0]["hooks"][0]["command"]
        assert command == "agent-frontdoor-hook --platform codex"
    for event in claude["hooks"].values():
        command = event[0]["hooks"][0]["command"]
        assert command == "agent-frontdoor-hook --platform claude"
    serialized = json.dumps({"codex": codex, "claude": claude})
    absolute_user_prefix = "/" + "Users" + "/"
    assert absolute_user_prefix not in serialized
    assert "transcript_path" not in serialized
