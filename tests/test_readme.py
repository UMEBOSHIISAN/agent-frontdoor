"""Contract tests for the public Agent Frontdoor README."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

REQUIRED_OPENING = [
    "This is not an agent runtime.",
    "This is not an autonomous router.",
    (
        "This is a preflight contract and validator for safely preparing "
        "tasks for AI workers."
    ),
]

CORE_FIELDS = (
    "schema_version",
    "request_id",
    "human_request",
    "task_class",
    "risk_tags",
    "allowed_actions",
    "forbidden_actions",
    "required_evidence",
    "required_manifest",
    "human_gate",
    "predicted_worker_capability",
    "unknowns",
    "assumptions",
    "next_safe_step",
)

TASK_CLASSES = (
    "RESEARCH",
    "DESIGN_REVIEW",
    "IMPLEMENTATION",
    "CODE_REVIEW",
    "AUDIT",
    "CONTENT_DRAFT",
    "DATA_ANALYSIS",
    "INSTALLATION",
    "OPERATIONS",
    "UNKNOWN",
)


def _text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_starts_with_required_contract() -> None:
    assert _text().splitlines()[:3] == REQUIRED_OPENING


def test_readme_documents_gate4_offline_boundary_and_exact_cli_examples() -> None:
    text = _text()
    assert "AGENT_FRONTDOOR_REPOSITORY_URL" in text
    assert (
        'git clone "$AGENT_FRONTDOOR_REPOSITORY_URL" agent-frontdoor'
        in text
    )
    assert '.venv/bin/python -m pip install -e ".[test]"' in text
    assert (
        '.venv/bin/python -m pip install --no-index --find-links "$WHEELHOUSE" '
        '--no-build-isolation -e ".[test]"'
        in text
    )
    assert (
        "agent-frontdoor validate fixtures/positive/01_install_only.json"
        in text
    )
    assert "agent-frontdoor card fixtures/positive/01_install_only.json" in text
    assert ".venv/bin/python -m pip uninstall -y agent-frontdoor" in text
    assert "--system-site-packages" not in text
    assert "--upgrade-deps" not in text
    assert (
        "agent-frontdoor check-drift examples/drift_before.json "
        "examples/drift_after.json"
    ) in text
    for command in (
        "agent-frontdoor validate task.json",
        "agent-frontdoor card task.json",
        "agent-frontdoor explain task.json",
        "agent-frontdoor check-drift before.json after.json",
    ):
        assert command in text


def test_readme_documents_failure_meanings_without_a_stale_pass_claim() -> None:
    text = _text()
    for marker in ("`INVALID`", "`ERROR`", "`DRIFT`"):
        assert marker in text
    assert "docs/FRIEND_LAB.md" in text


def test_readme_documents_current_intake_contract() -> None:
    text = _text()
    assert "`src/frontdoor/schema/intake.v0.json`" in text
    for field in CORE_FIELDS:
        assert f"`{field}`" in text
    for task_class in TASK_CLASSES:
        assert f"`{task_class}`" in text
    for gate in ("NONE", "CONFIRM", "BLOCKING"):
        assert f"`{gate}`" in text


def test_readme_documents_blocking_and_boundary_drift_contracts() -> None:
    text = _text()
    for category in (
        "deploy",
        "production",
        "scheduler",
        "secret",
        "auth",
        "billing",
        "delete",
        "destructive cleanup",
        "SSOT mutation",
        "external publish",
        "authority promotion",
    ):
        assert f"`{category}`" in text
    for transition in (
        "read-only audit -> mutation recommendation",
        "design review -> implementation",
        "installation -> architecture migration",
        "draft -> external publish",
        "proposal-only -> authority promotion",
        "bounded files -> unrelated broad refactor",
    ):
        assert transition in text


def test_readme_documents_exits_metrics_and_safety_boundaries() -> None:
    text = _text()
    for exit_contract in (
        "`0`: valid card or no drift",
        "`1`: loaded card is invalid",
        "`2`: input is unreadable or malformed JSON",
        "`3`: boundary drift detected",
    ):
        assert exit_contract in text
    assert (
        ".venv/bin/pytest tests/test_fixture_metrics.py "
        "tests/test_no_execution_paths.py -q"
    ) in text
    assert ".venv/bin/pytest -q" in text
    for boundary in (
        "no task execution",
        "no network requests",
        "no worker invocation",
        "no automatic routing",
    ):
        assert boundary in text


def test_readme_has_no_legacy_schema_references_or_stale_counts() -> None:
    text = _text()
    assert "agent-frontdoor.v0.1" not in text
    assert not re.search(r"\b\d+\s+tests?\s+pass(?:ed)?\b", text, re.IGNORECASE)
    assert "READ_ONLY_AUDIT" not in text
    assert "predicted_worker`" not in text


def test_readme_documents_intent_lock_without_blurring_authority() -> None:
    text = _text()
    normalized = " ".join(text.split())
    for marker in (
        "docs/INTENT_LOCK.md",
        "agent-frontdoor-hooks",
        "adapters/README.md",
        "adapters/examples/codex-hooks.json",
        "adapters/examples/claude-settings.json",
        "agent-frontdoor-hook --platform codex",
        "agent-frontdoor-hook --platform claude",
        "CC_UNAUDITED",
    ):
        assert marker in text
    for boundary in (
        "does not grant authority",
        "core package remains read-only",
        "optional sibling distribution",
        "hosted or specialized execution paths",
    ):
        assert boundary in normalized


def test_readme_leads_with_intent_lock_reader_flow() -> None:
    text = _text()
    ordered_sections = (
        "## Why Intent Lock exists / なぜ必要か",
        "## 30-second demo / 30秒デモ",
        "## Two distributions, separate trust boundaries",
        "## Safety model: identity is not authority",
        "## Core quick start",
        "## Optional runtime hooks",
        "## Bounded task-card reference",
    )
    positions = [text.index(section) for section in ordered_sections]
    assert positions == sorted(positions)

    for marker in (
        'denied = evaluate_action(lock, "npx wrangler whoami")',
        'allowed = evaluate_action(lock, "codex mcp login cloudflare-api")',
        "False literal_target_mismatch",
        "True literal_target_match",
        "Installing the adapter does not activate",
    ):
        assert marker in text

    for duplicated_heading in (
        "# Agent Frontdoor v0",
        "## English documentation",
        "## 日本語ドキュメント",
    ):
        assert duplicated_heading not in text
