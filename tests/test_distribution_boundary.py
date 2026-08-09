from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import html
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
from urllib.parse import unquote, urlsplit

import pytest
from setuptools.config.pyprojecttoml import read_configuration

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
ADAPTER_SOURCE_PRESENT = ADAPTER_PYPROJECT.exists()

CORE_URLS = {
    "Homepage": "https://github.com/UMEBOSHIISAN/agent-frontdoor",
    "Documentation": (
        "https://github.com/UMEBOSHIISAN/agent-frontdoor/tree/main/docs"
    ),
    "Source": "https://github.com/UMEBOSHIISAN/agent-frontdoor",
    "Issues": "https://github.com/UMEBOSHIISAN/agent-frontdoor/issues",
    "Changelog": (
        "https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/CHANGELOG.md"
    ),
    "Security": (
        "https://github.com/UMEBOSHIISAN/agent-frontdoor/security/policy"
    ),
}
ADAPTER_URLS = {
    **CORE_URLS,
    "Documentation": (
        "https://github.com/UMEBOSHIISAN/agent-frontdoor/tree/main/adapters"
    ),
}

CORE_GENERATED_METADATA = {
    "PKG-INFO",
    "setup.cfg",
    "src/agent_frontdoor.egg-info/PKG-INFO",
    "src/agent_frontdoor.egg-info/SOURCES.txt",
    "src/agent_frontdoor.egg-info/dependency_links.txt",
    "src/agent_frontdoor.egg-info/entry_points.txt",
    "src/agent_frontdoor.egg-info/requires.txt",
    "src/agent_frontdoor.egg-info/top_level.txt",
}
ADAPTER_GENERATED_METADATA = {
    "PKG-INFO",
    "setup.cfg",
    "src/agent_frontdoor_hooks.egg-info/PKG-INFO",
    "src/agent_frontdoor_hooks.egg-info/SOURCES.txt",
    "src/agent_frontdoor_hooks.egg-info/dependency_links.txt",
    "src/agent_frontdoor_hooks.egg-info/entry_points.txt",
    "src/agent_frontdoor_hooks.egg-info/requires.txt",
    "src/agent_frontdoor_hooks.egg-info/top_level.txt",
}

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
HTML_LINK = re.compile(r"(?:src|href)\s*=\s*['\"]([^'\"]+)['\"]", re.I)

@dataclass(frozen=True)
class SdistSnapshot:
    name: str
    files: frozenset[str]
    markdown: dict[str, str]


def _sanitized_copy(source: Path, destination: Path) -> None:
    excluded_directories = {
        ".cache",
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".worktrees",
        "__pycache__",
        "build",
        "dist",
        "worktrees",
    }

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {
            name
            for name in names
            if name in excluded_directories
            or name.endswith(".egg-info")
            or name.endswith((".pyc", ".pyo"))
        }

    shutil.copytree(source, destination, ignore=ignore)


def _build_sdist(source: Path, workspace: Path, label: str) -> SdistSnapshot:
    project = workspace / f"{label}-source"
    distribution = workspace / f"{label}-dist"
    _sanitized_copy(source, project)
    distribution.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from setuptools.build_meta import build_sdist; "
                "import sys; build_sdist(sys.argv[1])"
            ),
            str(distribution),
        ],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    archives = list(distribution.glob("*.tar.gz"))
    assert len(archives) == 1, archives
    archive_path = archives[0]
    expected_root = archive_path.name.removesuffix(".tar.gz")

    files: set[str] = set()
    markdown: dict[str, str] = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            path = PurePosixPath(member.name)
            assert path.parts[0] == expected_root, member.name
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            files.add(relative)
            if relative.endswith(".md"):
                stream = archive.extractfile(member)
                assert stream is not None
                markdown[relative] = stream.read().decode("utf-8")

    return SdistSnapshot(
        name=archive_path.name,
        files=frozenset(files),
        markdown=markdown,
    )


@pytest.fixture(scope="module")
def core_sdist(tmp_path_factory: pytest.TempPathFactory) -> SdistSnapshot:
    workspace = tmp_path_factory.mktemp("clean-core-sdist")
    return _build_sdist(ROOT, workspace, "core")


@pytest.fixture(scope="module")
def adapter_sdist(tmp_path_factory: pytest.TempPathFactory) -> SdistSnapshot:
    if not ADAPTER_SOURCE_PRESENT:
        pytest.skip("optional adapter source is not part of the core sdist")
    workspace = tmp_path_factory.mktemp("clean-adapter-sdist")
    return _build_sdist(ROOT / "adapters", workspace, "adapter")


def _relative_files(
    root: Path,
    relative_directory: str,
    suffixes: tuple[str, ...],
) -> set[str]:
    directory = root / relative_directory
    return {
        path.relative_to(root).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.suffix in suffixes
    }


def _expected_core_files() -> set[str]:
    explicit = {
        ".gitattributes",
        ".github/ISSUE_TEMPLATE/bug.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/feature.yml",
        ".github/pull_request_template.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "MANIFEST.in",
        "README.md",
        "SECURITY.md",
        "SUPPORT.md",
        "docs/ARCHITECTURE.md",
        "docs/CORE_REFERENCE.md",
        "docs/EVIDENCE.md",
        "docs/FRIEND_LAB.md",
        "docs/GETTING_STARTED.md",
        "docs/INTENT_LOCK.md",
        "docs/TROUBLESHOOTING.md",
        "pyproject.toml",
        "tools/verify_handoff_archive.py",
    }
    public_trees = set().union(
        _relative_files(ROOT, "assets", (".png", ".svg")),
        _relative_files(ROOT, "examples", (".json", ".md", ".py")),
        _relative_files(ROOT, "fixtures", (".json",)),
        _relative_files(ROOT, "schemas", (".json",)),
        _relative_files(ROOT, "src/frontdoor", (".json", ".py")),
    )
    adapter_tests = {
        "tests/test_adapter_safety.py",
        "tests/test_hook_adapter.py",
        "tests/test_hook_fixtures.py",
        "tests/test_hook_state.py",
    }
    core_tests = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests").glob("test_*.py")
    } - adapter_tests
    return explicit | public_trees | core_tests | CORE_GENERATED_METADATA


def _expected_adapter_files() -> set[str]:
    return {
        "LICENSE",
        "MANIFEST.in",
        "README.md",
        "examples/claude-settings.json",
        "examples/codex-hooks.json",
        "pyproject.toml",
        "src/frontdoor_hooks/__init__.py",
        "src/frontdoor_hooks/hook.py",
        "src/frontdoor_hooks/state.py",
    } | ADAPTER_GENERATED_METADATA


def _relative_target(source: str, raw_target: str) -> str | None:
    target = html.unescape(raw_target).strip().strip("<>")
    if not target or target.startswith(("#", "//")):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    assert not parsed.path.startswith("/"), (source, raw_target)

    parts = list(PurePosixPath(source).parent.parts)
    for part in PurePosixPath(unquote(parsed.path)).parts:
        if part in ("", "."):
            continue
        if part == "..":
            assert parts, (source, raw_target)
            parts.pop()
            continue
        parts.append(part)
    assert parts, (source, raw_target)
    return PurePosixPath(*parts).as_posix()


def _unresolved_links(snapshot: SdistSnapshot) -> Counter[tuple[str, str]]:
    unresolved: Counter[tuple[str, str]] = Counter()
    for source, text in snapshot.markdown.items():
        raw_targets = MARKDOWN_LINK.findall(text) + HTML_LINK.findall(text)
        for raw_target in raw_targets:
            target = _relative_target(source, raw_target)
            if target is not None and target not in snapshot.files:
                unresolved[(source, target)] += 1
    return unresolved


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


def test_changelog_keeps_both_development_lines_unreleased() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert text.count("## Unreleased") == 1
    assert "### Planned 0.2.0" in text
    assert "### Earlier 0.1 development candidate" in text
    assert "No Git tag or GitHub release represents either subsection." in text
    for item in (
        "standalone archive verifier",
        "deterministic friend pack",
        "guarded friend-lab acceptance",
        "offline installation instructions",
    ):
        assert item in text
    assert not re.search(r"^## 0\.\d", text, re.MULTILINE)
    assert not re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    assert "pypi.org" not in text.casefold()
    for published_claim in (
        "0.2 is published",
        "0.2.0 is published",
        "0.2 has been published",
        "0.2.0 has been published",
        "0.2 is released",
        "0.2.0 is released",
    ):
        assert published_claim not in text.casefold()


def _assert_classifier_metadata_is_public(project: dict[str, object]) -> None:
    classifier_separator = " :" + ": "
    for classifier in project.get("classifiers", []):
        parts = classifier.split(classifier_separator)
        assert parts[0] != "Operating System"
        assert not (
            len(parts) == 3
            and parts[:2] == ["Programming Language", "Python"]
            and re.fullmatch(r"3\.\d+", parts[2])
        )


def test_core_pep621_metadata_describes_unreleased_package() -> None:
    core = read_configuration(PYPROJECT, expand=False)["project"]

    assert core["name"] == "agent-frontdoor"
    assert core["version"] == "0.2.0"
    assert core["description"] == (
        "Read-only preflight gateway for bounded AI coding-agent tasks and "
        "drift detection"
    )
    assert core["license"] == "MIT"
    assert core["license-files"] == ["LICENSE"]
    assert core["requires-python"] == ">=3.10"
    assert core["dependencies"] == ["jsonschema>=4"]
    assert core["optional-dependencies"]["test"] == [
        "pytest",
        "setuptools>=77",
    ]
    assert set(core["keywords"]) == {
        "ai-agents",
        "developer-tools",
        "drift-detection",
        "task-validation",
    }
    assert core["urls"] == CORE_URLS
    assert core["scripts"] == {"agent-frontdoor": "frontdoor.cli:main"}
    _assert_classifier_metadata_is_public(core)


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_adapter_pep621_metadata_describes_unreleased_package() -> None:
    adapter = read_configuration(ADAPTER_PYPROJECT, expand=False)["project"]

    assert adapter["name"] == "agent-frontdoor-hooks"
    assert adapter["version"] == "0.2.0"
    assert adapter["description"] == (
        "Optional local Codex and Claude Code hooks for Agent Frontdoor "
        "Intent Lock"
    )
    assert adapter["license"] == "MIT"
    assert adapter["license-files"] == ["LICENSE"]
    assert adapter["requires-python"] == ">=3.10"
    assert adapter["dependencies"] == ["agent-frontdoor>=0.2.0,<0.3"]
    assert set(adapter["keywords"]) == {
        "ai-agents",
        "claude-code",
        "codex",
        "intent-lock",
    }
    assert adapter["urls"] == ADAPTER_URLS
    assert adapter["scripts"] == {
        "agent-frontdoor-hook": "frontdoor_hooks.hook:main"
    }
    _assert_classifier_metadata_is_public(adapter)

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


def test_core_guide_uses_canonical_cross_distribution_links() -> None:
    repository = "https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main"
    intent_lock = INTENT_LOCK.read_text(encoding="utf-8")

    for label, target in (
        ("Architecture", "docs/ARCHITECTURE.md"),
        ("Evidence", "docs/EVIDENCE.md"),
        ("Troubleshooting", "docs/TROUBLESHOOTING.md"),
        ("public adapter guide", "adapters/README.md"),
    ):
        assert f"[{label}]({repository}/{target})" in intent_lock


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_adapter_guide_uses_canonical_cross_distribution_links() -> None:
    repository = "https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main"
    adapter = ADAPTER_README.read_text(encoding="utf-8")

    assert f"[Intent Lock reference]({repository}/docs/INTENT_LOCK.md)" in adapter


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


def test_clean_core_sdist_has_exact_closed_member_set(
    core_sdist: SdistSnapshot,
) -> None:
    assert core_sdist.name == "agent_frontdoor-0.2.0.tar.gz"
    assert core_sdist.files == _expected_core_files()


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_clean_adapter_sdist_has_exact_closed_member_set(
    adapter_sdist: SdistSnapshot,
) -> None:
    assert adapter_sdist.name == "agent_frontdoor_hooks-0.2.0.tar.gz"
    assert adapter_sdist.files == _expected_adapter_files()


def test_clean_core_sdist_closes_every_relative_document_link(
    core_sdist: SdistSnapshot,
) -> None:
    assert _unresolved_links(core_sdist) == Counter()


@pytest.mark.skipif(
    not ADAPTER_SOURCE_PRESENT,
    reason="optional adapter source is not part of the core sdist",
)
def test_clean_adapter_sdist_closes_every_relative_document_link(
    adapter_sdist: SdistSnapshot,
) -> None:
    assert _unresolved_links(adapter_sdist) == Counter()


def test_changelog_records_intent_lock_as_unreleased_and_unactivated() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "intent-lock.v1" in text
    assert "agent-frontdoor-hooks" in text
    assert "not activated in local agent settings" in text
