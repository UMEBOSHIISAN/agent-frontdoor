"""Contract tests for the public Agent Frontdoor README."""

import json
from pathlib import Path
import re

from frontdoor.boundary_drift import detect_boundary_drift
from frontdoor.validator import validate_card


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


def test_readme_check_drift_examples_are_runnable() -> None:
    examples = ROOT / "examples"
    drift_before = json.loads(
        (examples / "drift_before.json").read_text(encoding="utf-8")
    )
    drift_after = json.loads(
        (examples / "drift_after.json").read_text(encoding="utf-8")
    )
    safe_before = json.loads(
        (examples / "safe_before.json").read_text(encoding="utf-8")
    )
    safe_after = json.loads(
        (examples / "safe_after.json").read_text(encoding="utf-8")
    )

    for card in (drift_before, drift_after, safe_before, safe_after):
        assert validate_card(card).valid

    drift_result = detect_boundary_drift(drift_before, drift_after)
    assert drift_result.drifted
    assert {
        finding.code for finding in drift_result.findings
    } == {"audit_to_mutation"}

    safe_result = detect_boundary_drift(safe_before, safe_after)
    assert not safe_result.drifted


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
