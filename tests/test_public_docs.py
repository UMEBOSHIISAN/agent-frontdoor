from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "EVIDENCE.md"
CORE_SOURCE = ROOT / "src" / "frontdoor"


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
