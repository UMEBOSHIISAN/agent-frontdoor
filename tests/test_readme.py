"""Contract tests for the public Agent Frontdoor README."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_presents_integrated_adoption_journey() -> None:
    text = _text()
    ordered = (
        "# Agent Frontdoor",
        "Stop AI coding agents from drifting beyond the task you approved.",
        "## See the boundary",
        "## Quick start",
        "## Choose a route",
        "## Evidence at a glance",
        "## Safety and limits",
        "## Documentation",
        "## Project status",
    )
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)
    for marker in (
        "https://github.com/UMEBOSHIISAN/agent-frontdoor.git",
        "examples/task-card.json",
        "VALID example-readme-audit",
        "Core CLI",
        "Intent Lock API",
        "Optional hooks",
    ):
        assert marker in text


def test_readme_uses_only_the_approved_public_sections() -> None:
    headings = [
        line
        for line in _text().splitlines()
        if line.startswith("#")
    ]
    assert headings == [
        "# Agent Frontdoor",
        "## See the boundary",
        "## How the gateway works",
        "## Quick start",
        "## Choose a route",
        "## Evidence at a glance",
        "## Safety and limits",
        "## Ecosystem",
        "## Documentation",
        "## Project status",
        "## License",
    ]


def test_readme_preserves_truthful_safety_and_unreleased_status() -> None:
    text = _text()
    normalized = " ".join(text.split())
    for marker in (
        "This is not an agent runtime.",
        "This is not an autonomous router.",
        "does not execute commands",
        "does not grant authority",
        "core is read-only",
        "not a security boundary",
        "Unreleased source preview",
        "No Git tag, GitHub release, or PyPI package exists",
        "No independent security audit has been completed",
    ):
        assert marker in normalized
    for stale in (
        "<PUBLIC_REPOSITORY_URL>",
        "CODEX_SELF_CONFIDENT_ADOPTED",
        "REPEATED_EXCESSIVE_DERAILMENT",
        "COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT",
        "CC_UNAUDITED",
        "public CLI and exit codes are stable",
        "img.shields.io",
    ):
        assert stale not in text


def test_readme_uses_integrated_accessible_visuals() -> None:
    text = _text()
    assert 'src="assets/agent-frontdoor-hero.svg"' in text
    assert 'src="assets/agent-frontdoor-architecture.svg"' in text
    assert "three independent read-only checks" in text
    assert "Task Card -> Validation -> Drift Detection" not in text
    for independent_route in (
        "Task Card -> Validation -> VALID / INVALID",
        "Baseline + revised card -> Drift Detection -> NO DRIFT / DRIFT",
        (
            "Prompt + proposed action -> Intent Lock -> "
            "IntentDecision (allowed, code, reason)"
        ),
    ):
        assert independent_route in text
    assert "CLEAR / DRIFT" not in text
    assert "ALLOW / DENY / HOLD" not in text
    assert "agent-frontdoor-pulse" not in text


def test_readme_distinguishes_invalid_cards_from_input_errors() -> None:
    text = _text()
    boundary_table = text.split("The same fail-closed rule", 1)[1].split(
        "## How the gateway works", 1
    )[0]
    normalized = boundary_table.casefold()
    assert "successfully loaded but contract-invalid or unsafe card" in normalized
    assert "`INVALID` (exit `1`)" in boundary_table
    assert "unreadable input or malformed json" in normalized
    assert "`ERROR` (exit `2`)" in boundary_table
    assert "unsafe or malformed card" not in normalized


def test_readme_routes_details_to_every_public_owner() -> None:
    text = _text()
    for target in (
        "docs/GETTING_STARTED.md",
        "docs/ARCHITECTURE.md",
        "docs/EVIDENCE.md",
        "docs/CORE_REFERENCE.md",
        "docs/INTENT_LOCK.md",
        "docs/TROUBLESHOOTING.md",
        "docs/FRIEND_LAB.md",
        "docs/mothership-suite.md",
        "examples/README.md",
        (
            "https://github.com/UMEBOSHIISAN/agent-frontdoor/"
            "blob/main/adapters/README.md"
        ),
        "CONTRIBUTING.md",
        "SECURITY.md",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
        "LICENSE",
        "CHANGELOG.md",
    ):
        assert f"]({target})" in text


def test_readme_uses_progressive_disclosure_for_detailed_contracts() -> None:
    headings = {
        line
        for line in _text().splitlines()
        if line.startswith("#")
    }
    for detailed_heading in (
        "### `intake.v0` task card",
        "## `intake.v0` schema",
        "### Human gates and fail-closed rules",
        "## Human gates and fail-closed rules",
        "### Boundary drift",
        "## Boundary-drift families",
        "### Fixtures and hard metrics",
        "## Fixtures and hard metrics",
        "## Offline acceptance",
    ):
        assert detailed_heading not in headings


def test_readme_publishes_exactly_five_stable_evidence_signals() -> None:
    evidence = _text().split("## Evidence at a glance", 1)[1].split(
        "## Safety and limits", 1
    )[0]
    for marker in (
        "Positive task-card fixtures",
        "Negative task-card fixtures",
        "Drift expectations",
        "Safe controls",
        "Core execution/network/worker/routing/source-write paths",
    ):
        assert marker in evidence
    table_rows = [line for line in evidence.splitlines() if line.startswith("|")]
    assert len(table_rows) == 7
    assert "836 passed" not in evidence


def test_readme_has_no_legacy_schema_references_or_stale_counts() -> None:
    text = _text()
    assert "agent-frontdoor.v0.1" not in text
    assert not re.search(r"\b\d+\s+tests?\s+pass(?:ed)?\b", text, re.IGNORECASE)
    assert "836 passed" not in text
    assert "READ_ONLY_AUDIT" not in text
    assert "predicted_worker`" not in text
