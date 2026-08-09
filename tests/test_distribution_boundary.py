from __future__ import annotations

import argparse
from pathlib import Path
import re

from frontdoor.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ROOT / ".gitattributes"
FRIEND_LAB = ROOT / "docs" / "FRIEND_LAB.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PYPROJECT = ROOT / "pyproject.toml"


def test_export_ignore_contains_only_lab_orchestration_boundaries() -> None:
    assert ATTRIBUTES.exists(), f"missing export boundary: {ATTRIBUTES}"
    assert ATTRIBUTES.read_text(encoding="utf-8") == (
        "/tools/friend_lab export-ignore\n"
        "/tests/friend_lab export-ignore\n"
        "/.github export-ignore\n"
    )


def test_friend_lab_manual_has_ordered_attended_acceptance_phases() -> None:
    assert FRIEND_LAB.exists(), f"missing friend-lab manual: {FRIEND_LAB}"
    text = FRIEND_LAB.read_text(encoding="utf-8")
    ordered = (
        "## 1. Record out-of-band digests",
        "## 2. Verify before extraction",
        "## 3. Create a disposable root",
        "## 4. Run positive controls",
        "## 5. Confirm physical network disconnect",
        "## 6. Verify source and wheel environments",
        "## 7. Run tests and samples",
        "## 8. Run negative fixtures",
        "## 9. Check deterministic repetition",
        "## 10. Scan privacy and writes",
        "## 11. Uninstall and write the receipt",
    )
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)
    assert "--no-index" in text
    assert "--no-build-isolation" in text
    assert "--system-site-packages" not in text
    assert "--upgrade-deps" not in text
    assert (
        'export FRIEND_PACK_ROOT="$FRIEND_TEMP_ROOT/'
        'agent-frontdoor-friend-pack-0.1.0"'
    ) in text
    assert '"$FRIEND_PACK_ROOT/lab/acceptance_runner.py"' in text
    assert '--pack-root "$FRIEND_PACK_ROOT"' in text
    assert '--run-root "$FRIEND_RUN_ROOT"' in text
    assert "$FRIEND_TEMP_ROOT/wheelhouse" not in text
    assert "$FRIEND_TEMP_ROOT/source" not in text


def test_friend_lab_manual_has_no_real_receiver_or_private_location() -> None:
    assert FRIEND_LAB.exists(), f"missing friend-lab manual: {FRIEND_LAB}"
    text = FRIEND_LAB.read_text(encoding="utf-8")
    private_home = "/" + "Users" + "/"
    assert private_home not in text
    assert not re.search(r"\b[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\b", text)
    assert not re.search(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", text)
    assert "<FRIEND_TEMP_ROOT>" in text
    assert "remote SSH" in text
    assert "PRIVATE_HANDOFF_READY_WITH_GAPS" in text


def test_distribution_keeps_exact_four_runtime_commands_and_no_lab_entrypoint() -> None:
    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(subparsers) == 1
    assert set(subparsers[0].choices) == {
        "validate",
        "card",
        "explain",
        "check-drift",
    }

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    assert 'agent-frontdoor = "frontdoor.cli:main"' in pyproject
    assert "tools.friend_lab" not in pyproject
    assert "friend-lab" not in pyproject
    assert 'frontdoor = ["schema/*.json"]' in pyproject
    assert not (ROOT / "src" / "frontdoor" / "friend_lab").exists()


def test_changelog_records_unreleased_release_hardening() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "## Unreleased" in text
    for item in (
        "standalone archive verifier",
        "deterministic friend pack",
        "guarded friend-lab acceptance",
        "offline installation instructions",
    ):
        assert item in text
    assert "## 0.1.0" in text
