import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "EVIDENCE.md"
CORE_REFERENCE = ROOT / "docs" / "CORE_REFERENCE.md"
GETTING_STARTED = ROOT / "docs" / "GETTING_STARTED.md"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE.md"
TROUBLESHOOTING = ROOT / "docs" / "TROUBLESHOOTING.md"
INTENT_LOCK = ROOT / "docs" / "INTENT_LOCK.md"
INTENT_LOCK_SCHEMA = (
    ROOT / "src" / "frontdoor" / "schema" / "intent-lock.v1.json"
)
ADAPTER_README = ROOT / "adapters" / "README.md"
CORE_SOURCE = ROOT / "src" / "frontdoor"
INTAKE_SCHEMA = ROOT / "src" / "frontdoor" / "schema" / "intake.v0.json"


def test_evidence_doc_scopes_every_published_number() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    for marker in (
        "`31 / 31`",
        "`41 / 41`",
        "`16 / 16`",
        "`4 / 4`",
        "zero forbidden core execution/network/worker/routing/source-write paths",
        "e866efa025f5299d638adfb4bf903a8de2594c0e",
        "836 passed",
        "2026-08-09",
        "python3 -m pytest -q tests/test_fixture_metrics.py tests/test_no_execution_paths.py",
        "python3 -m pytest -q",
    ):
        assert marker in text
    source_files = sorted(CORE_SOURCE.glob("*.py"))
    assert source_files
    assert f"`0 / {len(source_files)}` prohibited matches" in text
    assert "`src/frontdoor/*.py` scan population" in text
    normalized = " ".join(text.split()).casefold()
    assert "fixture-corpus regression evidence" in normalized
    assert "not a real-world effectiveness benchmark" in normalized
    assert "not an independent security audit" in normalized


def test_core_reference_owns_intake_cli_gate_and_drift_contracts() -> None:
    text = CORE_REFERENCE.read_text(encoding="utf-8")
    schema = json.loads(INTAKE_SCHEMA.read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert f"`{field}`" in text
    for task_class in schema["properties"]["task_class"]["enum"]:
        assert f"`{task_class}`" in text
    for gate in schema["properties"]["human_gate"]["enum"]:
        assert f"`{gate}`" in text
    for command in (
        "agent-frontdoor validate task.json",
        "agent-frontdoor card task.json",
        "agent-frontdoor explain task.json",
        "agent-frontdoor check-drift before.json after.json",
    ):
        assert command in text
    for exit_contract in (
        "`0`: valid card or no drift",
        "`1`: loaded card is invalid",
        "`2`: input is unreadable or malformed JSON",
        "`3`: boundary drift detected",
    ):
        assert exit_contract in text
    for marker in ("`INVALID`", "`ERROR`", "`DRIFT`"):
        assert marker in text


def test_core_reference_owns_blocking_and_boundary_drift_contracts() -> None:
    text = CORE_REFERENCE.read_text(encoding="utf-8")
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


def test_getting_started_reaches_first_success_without_release_claims() -> None:
    text = GETTING_STARTED.read_text(encoding="utf-8")
    ordered = (
        "## Requirements",
        "## Install from source",
        "## Validate your first task card",
        "## Read the task card",
        "## Next routes",
        "## Uninstall",
    )
    assert [text.index(item) for item in ordered] == sorted(
        text.index(item) for item in ordered
    )
    for marker in (
        "Python 3.10",
        "https://github.com/UMEBOSHIISAN/agent-frontdoor.git",
        '.venv/bin/python -m pip install -e .',
        ".venv/bin/agent-frontdoor validate examples/task-card.json",
        "VALID example-readme-audit",
        ".venv/bin/python -m pip uninstall -y agent-frontdoor",
        "CORE_REFERENCE.md",
        "../examples/README.md",
        "Optional adapter",
        "POSIX",
        "Windows",
    ):
        assert marker in text
    assert "<PUBLIC_REPOSITORY_URL>" not in text
    assert "pip install agent-frontdoor" not in text


def test_architecture_defines_pipeline_and_authority_boundaries() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert (
        "Task Card -> Validation -> Drift Detection -> Intent Lock "
        "-> Human Gate -> Safe Handoff"
    ) in text
    for marker in (
        "`agent-frontdoor`",
        "`agent-frontdoor-hooks`",
        "read-only",
        "privacy-minimized local state",
        "does not grant authority",
        "not a security boundary",
        "human authority remains external",
        "workflow-governance-model",
        "mothership-router",
        "mothership",
    ):
        assert marker in text


def test_troubleshooting_uses_non_escalating_recovery() -> None:
    text = TROUBLESHOOTING.read_text(encoding="utf-8")
    for marker in (
        "`ERROR`", "exit `2`", "`INVALID`", "exit `1`",
        "`DRIFT`", "exit `3`", "`BLOCKING`", "`REPORT_REQUIRED`",
        "mode `0700`", "mode `0600`", "Windows", "outcome-opaque",
    ):
        assert marker in text
    for boundary in (
        "do not retry",
        "do not switch to an adjacent subsystem",
        "does not grant authority",
        "operator-owned settings",
    ):
        assert boundary in text
    assert "| `UNKNOWN` |" in text
    assert "return the task for human clarification" in text
    assert "stop adapter adoption" in text
    assert "return the choice to the operator" in text
    assert "Use the read-only core on Windows" not in text


def test_intent_lock_reference_has_no_internal_labels() -> None:
    text = INTENT_LOCK.read_text(encoding="utf-8")
    schema = json.loads(INTENT_LOCK_SCHEMA.read_text(encoding="utf-8"))
    assert text.startswith("# Intent Lock Reference\n")
    for phase in schema["properties"]["phase"]["enum"]:
        assert f"`{phase}`" in text
    for mode in schema["properties"]["mode"]["enum"]:
        assert f"`{mode}`" in text
    for internal in (
        "CODEX_SELF_CONFIDENT_ADOPTED",
        "REPEATED_EXCESSIVE_DERAILMENT",
        "COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT",
        "CC_UNAUDITED",
        "implementation requested by the human",
    ):
        assert internal not in text
    assert "No independent security audit has been completed" in text


def test_adapter_readme_requires_smoke_before_activation() -> None:
    text = ADAPTER_README.read_text(encoding="utf-8")
    ordered = (
        "## Install in an isolated environment",
        "## Non-live smoke test",
        "## Codex example",
        "## Claude Code example",
        "## Uninstall or deactivate",
    )
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)
    for marker in (
        "--state-dir",
        "UserPromptSubmit",
        "PreToolUse",
        "permissionDecision",
        "INTENT_LOCK_REPORT_REQUIRED",
        "does not modify operator-owned settings",
        "mode `0700`",
        "mode `0600`",
        "Windows is rejected",
    ):
        assert marker in text
