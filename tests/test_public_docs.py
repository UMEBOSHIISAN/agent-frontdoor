from __future__ import annotations

import html
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest


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
ADAPTER_ROOT = ROOT / "adapters"
ADAPTER_PYPROJECT = ROOT / "adapters" / "pyproject.toml"
ADAPTER_SOURCE_PRESENT = ADAPTER_ROOT.is_dir()
CORE_SOURCE = ROOT / "src" / "frontdoor"
INTAKE_SCHEMA = ROOT / "src" / "frontdoor" / "schema" / "intake.v0.json"

CORE_PUBLIC_MARKDOWN = (
    Path("README.md"),
    Path("CHANGELOG.md"),
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path("SUPPORT.md"),
    Path("CODE_OF_CONDUCT.md"),
    Path("docs/GETTING_STARTED.md"),
    Path("docs/ARCHITECTURE.md"),
    Path("docs/EVIDENCE.md"),
    Path("docs/CORE_REFERENCE.md"),
    Path("docs/INTENT_LOCK.md"),
    Path("docs/TROUBLESHOOTING.md"),
    Path("docs/FRIEND_LAB.md"),
    Path("examples/README.md"),
    Path(".github/pull_request_template.md"),
)
PUBLIC_MARKDOWN = CORE_PUBLIC_MARKDOWN + (
    (Path("adapters/README.md"),) if ADAPTER_SOURCE_PRESENT else ()
)

MARKDOWN_LINK = re.compile(
    r"(?P<image>!)?\[(?P<label>[^\]]*)\]"
    r"\((?P<target><[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)"
)
MARKDOWN_REFERENCE_TARGET = re.compile(
    r"^\s*\[[^\]]+\]:\s*(?P<target><[^>]+>|\S+)",
    re.MULTILINE,
)
HTML_TARGET = re.compile(
    r"(?:src|href)\s*=\s*['\"](?P<target>[^'\"]+)['\"]",
    re.IGNORECASE,
)
HTML_IMAGE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE)
HTML_ATTRIBUTE = re.compile(
    r"\b(?P<name>src|alt)\s*=\s*(?P<quote>['\"])"
    r"(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)


def _link_targets(text: str) -> list[str]:
    targets = [match.group("target") for match in MARKDOWN_LINK.finditer(text)]
    targets.extend(
        match.group("target")
        for match in MARKDOWN_REFERENCE_TARGET.finditer(text)
    )
    targets.extend(match.group("target") for match in HTML_TARGET.finditer(text))
    return targets


def _local_target(source: Path, raw_target: str) -> Path | None:
    target = html.unescape(raw_target).strip().strip("<>")
    if not target or target.startswith(("#", "//")):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    assert not parsed.path.startswith("/"), (source, raw_target)

    resolved = (ROOT / source.parent / unquote(parsed.path)).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise AssertionError(
            f"public link escapes repository: {source} -> {raw_target}"
        ) from error
    return resolved


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
        "python3 -m venv .venv",
        ". .venv/bin/activate",
        '.venv/bin/python -m pip install -e ".[test]"',
        (
            ".venv/bin/python -m pytest -q "
            "tests/test_fixture_metrics.py tests/test_no_execution_paths.py"
        ),
        ".venv/bin/python -m pytest -q",
    ):
        assert marker in text
    assert "python3 -m pytest" not in text
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
        "runtime quick start intentionally omits test extras",
        "EVIDENCE.md",
    ):
        assert marker in text
    assert "<PUBLIC_REPOSITORY_URL>" not in text
    assert "pip install agent-frontdoor" not in text
    assert '-e ".[test]"' not in text


def test_architecture_defines_independent_primitives_and_authority_boundaries() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for independent_route in (
        "Task Card -> Validation -> VALID / INVALID",
        "Baseline + revised card -> Drift Detection -> NO DRIFT / DRIFT",
        (
            "Prompt + proposed action -> Intent Lock -> "
            "IntentDecision (allowed, code, reason)"
        ),
    ):
        assert independent_route in text
    assert "three independent primitives" in text
    assert "maps supported lifecycle events to Intent Lock only" in text
    assert (
        "Task Card -> Validation -> Drift Detection -> Intent Lock"
        not in text
    )
    assert "CLEAR / DRIFT" not in text
    assert "ALLOW / DENY / HOLD" not in text
    assert "`REPORT_REQUIRED` is a lock phase" in text
    assert "`allowed=False` with code `report_required`" in text
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


def test_unreleased_public_docs_do_not_promise_cli_or_exit_stability() -> None:
    unsupported_stability_claim = re.compile(
        r"(?:public\s+)?CLI(?:\s+and\s+exit\s+codes?)?\s+"
        r"(?:is|are)\s+stable|exit\s+codes?\s+(?:is|are)\s+stable",
        re.IGNORECASE,
    )
    for source in PUBLIC_MARKDOWN:
        text = (ROOT / source).read_text(encoding="utf-8")
        assert unsupported_stability_claim.search(text) is None, source

    core_reference = CORE_REFERENCE.read_text(encoding="utf-8")
    assert "unreleased 0.2 development contract" in core_reference
    assert "may change before a release" in core_reference


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


def test_adapter_tree_requires_packaging_metadata() -> None:
    if not ADAPTER_SOURCE_PRESENT:
        return
    assert ADAPTER_PYPROJECT.is_file(), (
        "adapter tree requires adapters/pyproject.toml"
    )


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_adapter_readme_requires_smoke_before_activation() -> None:
    text = ADAPTER_README.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
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
    assert (
        "The adapter assumes that Codex Bash `PostToolUse` payloads"
    ) in normalized
    assert (
        "Check this assumption against the current official Codex hook "
        "documentation before activation."
    ) in normalized


def test_intended_public_markdown_links_resolve_inside_repository() -> None:
    for source in PUBLIC_MARKDOWN:
        path = ROOT / source
        assert path.is_file(), source
        text = path.read_text(encoding="utf-8")
        for raw_target in _link_targets(text):
            target = _local_target(source, raw_target)
            if target is not None:
                assert target.exists(), (source, raw_target)


def test_local_readme_images_have_nonempty_alt_text() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    for match in MARKDOWN_LINK.finditer(text):
        if match.group("image") and _local_target(
            Path("README.md"), match.group("target")
        ) is not None:
            assert match.group("label").strip(), match.group(0)

    for match in HTML_IMAGE.finditer(text):
        attributes = {
            attribute.group("name").casefold(): attribute.group("value")
            for attribute in HTML_ATTRIBUTE.finditer(match.group("attrs"))
        }
        source = attributes.get("src")
        if source and _local_target(Path("README.md"), source) is not None:
            assert attributes.get("alt", "").strip(), match.group(0)
