"""Behavior tests for deterministic task-card boundary drift detection."""

from copy import deepcopy

import pytest

from frontdoor.boundary_drift import DriftReport, detect_boundary_drift


def _card(**overrides):
    card = {
        "schema_version": "intake.v0",
        "request_id": "drift-case",
        "human_request": "Review the requested work",
        "task_class": "AUDIT",
        "risk_tags": [],
        "allowed_actions": ["read files", "report findings"],
        "forbidden_actions": ["write files", "publish externally"],
        "required_evidence": ["review report"],
        "required_manifest": None,
        "human_gate": "NONE",
        "predicted_worker_capability": "audit",
        "unknowns": [],
        "assumptions": [],
        "next_safe_step": "Inspect the requested files",
    }
    card.update(overrides)
    return card


@pytest.fixture
def drift_cards():
    return {
        "audit_to_mutation": (
            _card(),
            _card(
                allowed_actions=["modify source files"],
                next_safe_step="Edit the reviewed source files",
            ),
        ),
        "design_to_implementation": (
            _card(
                task_class="DESIGN_REVIEW",
                predicted_worker_capability="design-review",
                allowed_actions=["review the proposed design"],
                next_safe_step="Report design findings",
            ),
            _card(
                task_class="IMPLEMENTATION",
                predicted_worker_capability="implementation",
                allowed_actions=["implement the proposed design"],
                next_safe_step="Write the implementation",
            ),
        ),
        "install_to_architecture_migration": (
            _card(
                task_class="INSTALLATION",
                predicted_worker_capability="installation",
                allowed_actions=["install the named package only"],
                next_safe_step="Install the named package only",
            ),
            _card(
                task_class="IMPLEMENTATION",
                predicted_worker_capability="implementation",
                risk_tags=["scope_drift"],
                allowed_actions=["migrate the application architecture"],
                next_safe_step="Begin the architecture migration",
            ),
        ),
        "draft_to_external_publish": (
            _card(
                task_class="CONTENT_DRAFT",
                predicted_worker_capability="content-draft",
                allowed_actions=["draft the announcement"],
                next_safe_step="Prepare a local draft",
            ),
            _card(
                task_class="CONTENT_DRAFT",
                predicted_worker_capability="content-draft",
                risk_tags=["external_publish"],
                allowed_actions=["publish the announcement externally"],
                human_gate="BLOCKING",
                next_safe_step="Publish the draft externally",
            ),
        ),
        "proposal_to_authority_promotion": (
            _card(
                task_class="DESIGN_REVIEW",
                predicted_worker_capability="design-review",
                allowed_actions=["prepare a proposal only"],
                next_safe_step="Present the proposal for review",
            ),
            _card(
                task_class="DESIGN_REVIEW",
                predicted_worker_capability="design-review",
                risk_tags=["authority_promotion"],
                allowed_actions=["promote the proposal to approved authority"],
                human_gate="BLOCKING",
                next_safe_step="Grant authority from the proposal",
            ),
        ),
        "bounded_files_to_broad_refactor": (
            _card(
                task_class="IMPLEMENTATION",
                predicted_worker_capability="implementation",
                allowed_actions=["edit only src/frontdoor/cli.py"],
                next_safe_step="Patch only src/frontdoor/cli.py",
            ),
            _card(
                task_class="IMPLEMENTATION",
                predicted_worker_capability="implementation",
                risk_tags=["scope_drift"],
                allowed_actions=[
                    "perform a broad refactor across unrelated files"
                ],
                next_safe_step="Refactor the entire repository",
            ),
        ),
    }


@pytest.mark.parametrize(
    "case,code",
    [
        ("audit_to_mutation", "audit_to_mutation"),
        ("design_to_implementation", "design_to_implementation"),
        (
            "install_to_architecture_migration",
            "install_to_architecture_migration",
        ),
        ("draft_to_external_publish", "draft_to_external_publish"),
        (
            "proposal_to_authority_promotion",
            "proposal_to_authority_promotion",
        ),
        (
            "bounded_files_to_broad_refactor",
            "bounded_files_to_broad_refactor",
        ),
    ],
)
def test_required_drift_family(case, code, drift_cards):
    report = detect_boundary_drift(*drift_cards[case])
    assert report.drifted
    assert code in {finding.code for finding in report.findings}


def test_safe_expansion_has_no_drift_and_inputs_are_not_mutated():
    before = _card()
    after = _card(
        allowed_actions=["read files", "report findings", "summarize findings"],
        next_safe_step="Summarize the review findings",
    )
    original_before = deepcopy(before)
    original_after = deepcopy(after)

    assert detect_boundary_drift(before, after) == DriftReport(False, ())
    assert before == original_before
    assert after == original_after


@pytest.mark.parametrize(
    "action",
    [
        "recommend that source files be edited",
        "recommend that the design be implemented",
        "recommend that the module be patched",
        "recommend that the configuration be modified",
        "recommend that the report be written",
    ],
)
def test_audit_to_mutation_detects_recommendation_inflections(action):
    before = _card(allowed_actions=["read source files"])
    after = _card(allowed_actions=[action])

    report = detect_boundary_drift(before, after)

    assert report.drifted
    assert "audit_to_mutation" in {
        finding.code for finding in report.findings
    }


def test_bounded_path_to_broad_refactor_survives_normalization():
    before = _card(
        task_class="IMPLEMENTATION",
        predicted_worker_capability="implementation",
        allowed_actions=["only src/frontdoor/cli.py"],
        next_safe_step="Inspect the requested scope",
    )
    after = _card(
        task_class="IMPLEMENTATION",
        predicted_worker_capability="implementation",
        allowed_actions=["perform a broad refactor"],
        next_safe_step="Review the requested expansion",
    )

    report = detect_boundary_drift(before, after)

    assert report.drifted
    assert "bounded_files_to_broad_refactor" in {
        finding.code for finding in report.findings
    }
