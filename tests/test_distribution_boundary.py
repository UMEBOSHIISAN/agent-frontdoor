from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re

import pytest

from frontdoor.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ROOT / ".gitattributes"
FRIEND_LAB = ROOT / "docs" / "FRIEND_LAB.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PYPROJECT = ROOT / "pyproject.toml"
ADAPTER_PYPROJECT = ROOT / "adapters" / "pyproject.toml"
ADAPTER_README = ROOT / "adapters" / "README.md"
INTENT_LOCK = ROOT / "docs" / "INTENT_LOCK.md"
ADAPTER_LICENSE = ROOT / "adapters" / "LICENSE"
MANIFEST = ROOT / "MANIFEST.in"
ADAPTER_SOURCE_PRESENT = ADAPTER_PYPROJECT.exists()


def test_export_ignore_contains_only_lab_orchestration_boundaries() -> None:
    assert ATTRIBUTES.exists(), f"missing export boundary: {ATTRIBUTES}"
    assert ATTRIBUTES.read_text(encoding="utf-8") == (
        "/tools/friend_lab export-ignore\n"
        "/tests/friend_lab export-ignore\n"
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
        'agent-frontdoor-friend-pack-0.2.0"'
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


def test_friend_lab_is_advanced_not_standard_installation() -> None:
    text = FRIEND_LAB.read_text(encoding="utf-8")
    assert "## Audience and prerequisites" in text
    assert "advanced offline receiver workflow" in text.casefold()
    assert "not the standard installation path" in text.casefold()
    assert "GETTING_STARTED.md" in text


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


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_hook_adapter_is_a_separate_optional_distribution() -> None:
    core = PYPROJECT.read_text(encoding="utf-8")
    adapter = ADAPTER_PYPROJECT.read_text(encoding="utf-8")

    assert 'name = "agent-frontdoor"' in core
    assert 'version = "0.2.0"' in core
    assert "agent-frontdoor-hook" not in core
    assert 'name = "agent-frontdoor-hooks"' in adapter
    assert 'version = "0.2.0"' in adapter
    assert 'dependencies = ["agent-frontdoor>=0.2.0,<0.3"]' in adapter
    assert 'agent-frontdoor-hook = "frontdoor_hooks.hook:main"' in adapter
    assert ADAPTER_README.exists()
    adapter_readme = ADAPTER_README.read_text(encoding="utf-8")
    assert "/ABSOLUTE/PATH/TO/REVIEWED/VENV/bin/agent-frontdoor-hook" in (
        adapter_readme
    )
    assert "replace the placeholder" in adapter_readme


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_hook_adapter_metadata_passes_source_privacy_scan() -> None:
    from tools.verify_handoff_archive import scan_forbidden_text

    assert scan_forbidden_text(
        PurePosixPath("adapters/pyproject.toml"),
        ADAPTER_PYPROJECT.read_bytes(),
    ) == ()


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_hook_adapter_distribution_includes_inert_configuration_examples() -> None:
    adapter = ADAPTER_PYPROJECT.read_text(encoding="utf-8")

    assert '[tool.setuptools.data-files]' in adapter
    assert '"share/agent-frontdoor-hooks/examples"' in adapter
    assert '"examples/codex-hooks.json"' in adapter
    assert '"examples/claude-settings.json"' in adapter
    assert "share/agent-frontdoor-hooks/examples" in ADAPTER_README.read_text(
        encoding="utf-8"
    )


def test_distributed_guides_use_canonical_cross_distribution_links() -> None:
    repository = "https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main"
    adapter = ADAPTER_README.read_text(encoding="utf-8")
    intent_lock = INTENT_LOCK.read_text(encoding="utf-8")

    assert f"[Intent Lock reference]({repository}/docs/INTENT_LOCK.md)" in adapter
    for label, target in (
        ("Architecture", "docs/ARCHITECTURE.md"),
        ("Evidence", "docs/EVIDENCE.md"),
        ("Troubleshooting", "docs/TROUBLESHOOTING.md"),
        ("public adapter guide", "adapters/README.md"),
    ):
        assert f"[{label}]({repository}/{target})" in intent_lock


def test_both_distributions_use_current_spdx_license_metadata() -> None:
    paths = (
        (PYPROJECT, ADAPTER_PYPROJECT)
        if ADAPTER_SOURCE_PRESENT
        else (PYPROJECT,)
    )
    for path in paths:
        pyproject = path.read_text(encoding="utf-8")
        assert 'requires = ["setuptools>=77"]' in pyproject
        assert 'license = "MIT"' in pyproject
        assert "license = {text" not in pyproject
    if ADAPTER_SOURCE_PRESENT:
        adapter = ADAPTER_PYPROJECT.read_text(encoding="utf-8")
        assert 'license-files = ["LICENSE"]' in adapter
        assert ADAPTER_LICENSE.read_bytes() == (ROOT / "LICENSE").read_bytes()


def test_root_pytest_configuration_loads_core_adapter_and_lab_sources() -> None:
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    assert 'pythonpath = [".", "src", "adapters/src"]' in pyproject


def test_core_sdist_excludes_tests_for_the_separate_adapter_distribution() -> None:
    assert MANIFEST.read_text(encoding="utf-8") == (
        "include .gitattributes\n"
        "include CHANGELOG.md\n"
        "include docs/FRIEND_LAB.md\n"
        "include docs/INTENT_LOCK.md\n"
        "recursive-include examples *.json\n"
        "recursive-include fixtures *.json\n"
        "recursive-include schemas *.json\n"
        "include tools/verify_handoff_archive.py\n"
        "exclude tests/test_adapter_safety.py\n"
        "exclude tests/test_hook_adapter.py\n"
        "exclude tests/test_hook_fixtures.py\n"
        "exclude tests/test_hook_state.py\n"
    )


def test_changelog_records_intent_lock_as_unreleased_and_unactivated() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "intent-lock.v1" in text
    assert "agent-frontdoor-hooks" in text
    assert "not activated in local agent settings" in text
