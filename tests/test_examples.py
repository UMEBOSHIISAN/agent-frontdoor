from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from frontdoor.boundary_drift import detect_boundary_drift
from frontdoor.cli import main
from frontdoor.validator import validate_card


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_curated_task_card_is_valid_and_has_stable_cli_result(capsys) -> None:
    path = EXAMPLES / "task-card.json"
    card = json.loads(path.read_text(encoding="utf-8"))
    result = validate_card(card)
    assert result.valid, result.issues
    assert card["request_id"] == "example-readme-audit"
    assert main(["validate", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "VALID example-readme-audit\n"
    assert captured.err == ""


def test_intent_lock_demo_prints_only_decisions() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / "intent_lock_demo.py")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "False literal_target_mismatch\n"
        "True literal_target_match\n"
        "No command was executed; an intent match is not authority.\n"
    )
    assert result.stderr == ""


def test_public_drift_pairs_match_documented_results() -> None:
    drift_before = json.loads(
        (EXAMPLES / "drift_before.json").read_text(encoding="utf-8")
    )
    drift_after = json.loads(
        (EXAMPLES / "drift_after.json").read_text(encoding="utf-8")
    )
    safe_before = json.loads(
        (EXAMPLES / "safe_before.json").read_text(encoding="utf-8")
    )
    safe_after = json.loads(
        (EXAMPLES / "safe_after.json").read_text(encoding="utf-8")
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


def test_examples_index_owns_all_public_examples_and_cli_results(capsys) -> None:
    text = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    for filename in (
        "task-card.json",
        "intent_lock_demo.py",
        "drift_before.json",
        "drift_after.json",
        "safe_before.json",
        "safe_after.json",
    ):
        assert filename in text
    for outcome in (
        "VALID example-readme-audit",
        "False literal_target_mismatch",
        "True literal_target_match",
        "No command was executed; an intent match is not authority.",
        "exit `3`",
        "audit_to_mutation",
        "exit `0`",
        "NO DRIFT",
    ):
        assert outcome in text

    drift_before = EXAMPLES / "drift_before.json"
    drift_after = EXAMPLES / "drift_after.json"
    assert main(["check-drift", str(drift_before), str(drift_after)]) == 3
    captured = capsys.readouterr()
    assert captured.out.startswith("DRIFT\n")
    assert "audit_to_mutation" in captured.out
    assert captured.err == ""

    safe_before = EXAMPLES / "safe_before.json"
    safe_after = EXAMPLES / "safe_after.json"
    assert main(["check-drift", str(safe_before), str(safe_after)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "NO DRIFT\n"
    assert captured.err == ""
