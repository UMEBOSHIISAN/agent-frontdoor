"""Hard corpus metrics for the Agent Frontdoor safety contract."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import pytest

from frontdoor.boundary_drift import detect_boundary_drift
from frontdoor.validator import validate_card


ROOT = Path(__file__).resolve().parents[1]
POSITIVE = ROOT / "fixtures" / "positive"
NEGATIVE = ROOT / "fixtures" / "negative"
DRIFT = ROOT / "fixtures" / "drift"

REQUIRED_CATEGORIES = frozenset(
    {
        "install only",
        "read-only audit",
        "deploy request",
        "secret handling",
        "scheduler change",
        "cleanup adjacent",
        "external posting",
        "ambiguous request",
        "authority promotion",
        "code patch",
        "design review",
        "research task",
    }
)

CATEGORY_BY_POSITIVE_FILENAME = {
    "01_install_only.json": "install only",
    "02_install_only_dev_tool.json": "install only",
    "03_read_only_audit.json": "read-only audit",
    "04_read_only_audit_logs.json": "read-only audit",
    "05_deploy_request.json": "deploy request",
    "06_deploy_request_staging.json": "deploy request",
    "07_secret_handling.json": "secret handling",
    "08_secret_handling_rotation_plan.json": "secret handling",
    "09_scheduler_change.json": "scheduler change",
    "10_scheduler_change_review.json": "scheduler change",
    "11_cleanup_adjacent.json": "cleanup adjacent",
    "12_cleanup_adjacent_cache.json": "cleanup adjacent",
    "13_external_posting.json": "external posting",
    "14_external_posting_preview.json": "external posting",
    "15_ambiguous_request.json": "ambiguous request",
    "16_ambiguous_request_scope.json": "ambiguous request",
    "17_authority_promotion.json": "authority promotion",
    "18_authority_promotion_review.json": "authority promotion",
    "19_code_patch.json": "code patch",
    "20_code_patch_config.json": "code patch",
    "21_design_review.json": "design review",
    "22_design_review_api.json": "design review",
    "23_research_task.json": "research task",
    "24_research_task_comparison.json": "research task",
    "25_install_only_extension.json": "install only",
    "26_read_only_audit_scope.json": "read-only audit",
    "27_code_patch_test.json": "code patch",
    "28_design_review_dataflow.json": "design review",
    "29_research_task_feasibility.json": "research task",
    "30_cleanup_adjacent_artifacts.json": "cleanup adjacent",
    "31_data_analysis_production_logs.json": "deploy request",
}

CATEGORY_BY_NEGATIVE_FILENAME = {
    "neg_01_install_missing_manifest.json": "install only",
    "neg_02_install_empty_allowed.json": "install only",
    "neg_03_audit_action_conflict.json": "read-only audit",
    "neg_04_audit_delete_with_confirm.json": "read-only audit",
    "neg_05_deploy_tag_none.json": "deploy request",
    "neg_06_deploy_text_confirm.json": "deploy request",
    "neg_07_production_tag_none.json": "deploy request",
    "neg_08_production_action_confirm.json": "deploy request",
    "neg_09_secret_tag_none.json": "secret handling",
    "neg_10_secret_text_confirm.json": "secret handling",
    "neg_11_auth_tag_none.json": "secret handling",
    "neg_12_auth_action_confirm.json": "secret handling",
    "neg_13_scheduler_tag_none.json": "scheduler change",
    "neg_14_scheduler_text_confirm.json": "scheduler change",
    "neg_15_billing_tag_none.json": "ambiguous request",
    "neg_16_billing_text_confirm.json": "ambiguous request",
    "neg_17_delete_tag_none.json": "cleanup adjacent",
    "neg_18_delete_text_confirm.json": "cleanup adjacent",
    "neg_19_destructive_cleanup_tag_none.json": "cleanup adjacent",
    "neg_20_destructive_cleanup_text_confirm.json": "cleanup adjacent",
    "neg_21_ssot_tag_none.json": "code patch",
    "neg_22_ssot_text_confirm.json": "code patch",
    "neg_23_external_publish_tag_none.json": "external posting",
    "neg_24_external_post_text_confirm.json": "external posting",
    "neg_25_authority_tag_none.json": "authority promotion",
    "neg_26_authority_text_confirm.json": "authority promotion",
    "neg_27_unknown_gate_none.json": "ambiguous request",
    "neg_28_unknown_worker_selected.json": "ambiguous request",
    "neg_29_unknown_details_empty.json": "ambiguous request",
    "neg_30_unknown_allowed_mutation.json": "ambiguous request",
    "neg_31_unknown_next_step_mutation.json": "ambiguous request",
    "neg_32_unknown_tag_confirm.json": "ambiguous request",
    "neg_33_patch_invalid_task_class.json": "code patch",
    "neg_34_design_invalid_risk_tag.json": "design review",
    "neg_35_research_model_worker.json": "research task",
    "neg_36_install_extra_execute_field.json": "install only",
    "neg_37_audit_empty_request.json": "read-only audit",
    "neg_38_research_risks_not_array.json": "research task",
    "neg_39_design_missing_forbidden.json": "design review",
    "neg_40_patch_nonstring_action.json": "code patch",
    "neg_41_code_review_delete_tag_none.json": "cleanup adjacent",
}

EXPECTED_NEGATIVE_CODES = {
    "neg_01_install_missing_manifest.json": {"schema_error"},
    "neg_02_install_empty_allowed.json": {"schema_error"},
    "neg_03_audit_action_conflict.json": {"action_conflict"},
    "neg_04_audit_delete_with_confirm.json": {"blocking_gate_required"},
    "neg_05_deploy_tag_none.json": {"blocking_gate_required"},
    "neg_06_deploy_text_confirm.json": {"blocking_gate_required"},
    "neg_07_production_tag_none.json": {"blocking_gate_required"},
    "neg_08_production_action_confirm.json": {"blocking_gate_required"},
    "neg_09_secret_tag_none.json": {"blocking_gate_required"},
    "neg_10_secret_text_confirm.json": {"blocking_gate_required"},
    "neg_11_auth_tag_none.json": {"blocking_gate_required"},
    "neg_12_auth_action_confirm.json": {"blocking_gate_required"},
    "neg_13_scheduler_tag_none.json": {"blocking_gate_required"},
    "neg_14_scheduler_text_confirm.json": {"blocking_gate_required"},
    "neg_15_billing_tag_none.json": {
        "blocking_gate_required",
        "unknown_requires_blocking",
    },
    "neg_16_billing_text_confirm.json": {"blocking_gate_required"},
    "neg_17_delete_tag_none.json": {"blocking_gate_required"},
    "neg_18_delete_text_confirm.json": {"blocking_gate_required"},
    "neg_19_destructive_cleanup_tag_none.json": {
        "blocking_gate_required"
    },
    "neg_20_destructive_cleanup_text_confirm.json": {
        "blocking_gate_required"
    },
    "neg_21_ssot_tag_none.json": {"blocking_gate_required"},
    "neg_22_ssot_text_confirm.json": {"blocking_gate_required"},
    "neg_23_external_publish_tag_none.json": {"blocking_gate_required"},
    "neg_24_external_post_text_confirm.json": {"blocking_gate_required"},
    "neg_25_authority_tag_none.json": {"blocking_gate_required"},
    "neg_26_authority_text_confirm.json": {"blocking_gate_required"},
    "neg_27_unknown_gate_none.json": {"unknown_requires_blocking"},
    "neg_28_unknown_worker_selected.json": {"unknown_requires_no_worker"},
    "neg_29_unknown_details_empty.json": {"unknown_details_required"},
    "neg_30_unknown_allowed_mutation.json": {"unknown_mutation_forbidden"},
    "neg_31_unknown_next_step_mutation.json": {
        "unknown_mutation_forbidden"
    },
    "neg_32_unknown_tag_confirm.json": {
        "blocking_gate_required",
        "unknown_requires_blocking",
    },
    "neg_33_patch_invalid_task_class.json": {"schema_error"},
    "neg_34_design_invalid_risk_tag.json": {"schema_error"},
    "neg_35_research_model_worker.json": {"schema_error"},
    "neg_36_install_extra_execute_field.json": {"schema_error"},
    "neg_37_audit_empty_request.json": {"schema_error"},
    "neg_38_research_risks_not_array.json": {"schema_error"},
    "neg_39_design_missing_forbidden.json": {"schema_error"},
    "neg_40_patch_nonstring_action.json": {"schema_error"},
    "neg_41_code_review_delete_tag_none.json": {"blocking_gate_required"},
}

BLOCKING_GATE_EXPECTATIONS = {
    **{
        filename: {"blocking_gate_required"}
        for filename in (
            "neg_04_audit_delete_with_confirm.json",
            "neg_05_deploy_tag_none.json",
            "neg_06_deploy_text_confirm.json",
            "neg_07_production_tag_none.json",
            "neg_08_production_action_confirm.json",
            "neg_09_secret_tag_none.json",
            "neg_10_secret_text_confirm.json",
            "neg_11_auth_tag_none.json",
            "neg_12_auth_action_confirm.json",
            "neg_13_scheduler_tag_none.json",
            "neg_14_scheduler_text_confirm.json",
            "neg_16_billing_text_confirm.json",
            "neg_17_delete_tag_none.json",
            "neg_18_delete_text_confirm.json",
            "neg_19_destructive_cleanup_tag_none.json",
            "neg_20_destructive_cleanup_text_confirm.json",
            "neg_21_ssot_tag_none.json",
            "neg_22_ssot_text_confirm.json",
            "neg_23_external_publish_tag_none.json",
            "neg_24_external_post_text_confirm.json",
            "neg_25_authority_tag_none.json",
            "neg_26_authority_text_confirm.json",
            "neg_41_code_review_delete_tag_none.json",
        )
    },
    "neg_15_billing_tag_none.json": {
        "blocking_gate_required",
        "unknown_requires_blocking",
    },
    "neg_27_unknown_gate_none.json": {"unknown_requires_blocking"},
    "neg_32_unknown_tag_confirm.json": {
        "blocking_gate_required",
        "unknown_requires_blocking",
    },
}

UNKNOWN_FAIL_SAFE_EXPECTATIONS = {
    "neg_15_billing_tag_none.json": {"unknown_requires_blocking"},
    "neg_27_unknown_gate_none.json": {"unknown_requires_blocking"},
    "neg_28_unknown_worker_selected.json": {"unknown_requires_no_worker"},
    "neg_29_unknown_details_empty.json": {"unknown_details_required"},
    "neg_30_unknown_allowed_mutation.json": {"unknown_mutation_forbidden"},
    "neg_31_unknown_next_step_mutation.json": {
        "unknown_mutation_forbidden"
    },
    "neg_32_unknown_tag_confirm.json": {"unknown_requires_blocking"},
}

TASK_CLASSES = frozenset(
    {
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
    }
)

EXPECTED_DRIFT_CODES = {
    "drift_01_audit_class_to_impl.json": {"audit_to_mutation"},
    "drift_02_audit_add_change_action.json": {"audit_to_mutation"},
    "drift_03_audit_patch_next_step.json": {"audit_to_mutation"},
    "drift_04_design_class_to_impl.json": {"design_to_implementation"},
    "drift_05_design_patch_delivery.json": {"design_to_implementation"},
    "drift_06_design_write_module.json": {"design_to_implementation"},
    "drift_07_install_migrate_architecture.json": {
        "install_to_architecture_migration"
    },
    "drift_08_install_redesign_architecture.json": {
        "install_to_architecture_migration"
    },
    "drift_09_install_rearchitect.json": {
        "install_to_architecture_migration"
    },
    "drift_10_draft_publish_risk.json": {"draft_to_external_publish"},
    "drift_11_draft_publish_action.json": {"draft_to_external_publish"},
    "drift_12_draft_go_live.json": {"draft_to_external_publish"},
    "drift_13_proposal_authority_risk.json": {
        "proposal_to_authority_promotion"
    },
    "drift_14_proposal_grant_authority.json": {
        "proposal_to_authority_promotion"
    },
    "drift_15_named_files_broad_refactor.json": {
        "bounded_files_to_broad_refactor"
    },
    "drift_16_one_file_unrelated_modules.json": {
        "bounded_files_to_broad_refactor"
    },
    "drift_17_safe_audit_more_reads.json": set(),
    "drift_18_safe_design_revision.json": set(),
    "drift_19_safe_install_extra_package.json": set(),
    "drift_20_safe_internal_preview.json": set(),
}


def _fixture_names(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {path.name for path in directory.glob("*.json")}


def _load_json(path: Path) -> object:
    assert path.is_file(), f"missing fixture: {path.relative_to(ROOT)}"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        pytest.fail(f"unable to load {path.relative_to(ROOT)}: {error}")


def _issue_codes(card: object) -> set[str]:
    return {issue.code for issue in validate_card(card).issues}


def _matches_category_signal(card: object, category: str) -> bool:
    if not isinstance(card, dict):
        return False

    task_class = card.get("task_class")
    risk_value = card.get("risk_tags")
    risk_tags = {
        tag for tag in risk_value if isinstance(tag, str)
    } if isinstance(risk_value, list) else set()
    request = card.get("human_request")
    action_value = card.get("allowed_actions")
    actions = (
        [action for action in action_value if isinstance(action, str)]
        if isinstance(action_value, list)
        else []
    )
    text = " ".join(
        [request if isinstance(request, str) else "", *actions]
    ).casefold()

    if category == "install only":
        return task_class == "INSTALLATION" and "install" in text
    if category == "read-only audit":
        return task_class == "AUDIT" and any(
            signal in text for signal in ("audit", "inspect", "read")
        )
    if category == "deploy request":
        return bool(risk_tags & {"deploy", "production"}) or any(
            signal in text for signal in ("deploy", "production")
        )
    if category == "secret handling":
        return bool(risk_tags & {"secret", "auth"}) or any(
            signal in text
            for signal in (
                "api key",
                "auth",
                "credential",
                "permission",
                "secret",
            )
        )
    if category == "scheduler change":
        return "scheduler" in risk_tags or any(
            signal in text
            for signal in ("cron", "schedule", "scheduled", "scheduler")
        )
    if category == "cleanup adjacent":
        return bool(
            risk_tags & {"cleanup_adjacent", "delete", "destructive_cleanup"}
        ) or any(
            signal in text
            for signal in ("cleanup", "delete", "destructive", "remove")
        )
    if category == "external posting":
        return "external_publish" in risk_tags or any(
            signal in text
            for signal in ("external", "post", "publication", "publish")
        )
    if category == "ambiguous request":
        return (
            task_class == "UNKNOWN"
            or bool(risk_tags & {"billing", "unknown"})
            or any(
                signal in text
                for signal in (
                    "account discrepancy",
                    "ambiguous",
                    "charges",
                    "invoice",
                    "unclear",
                )
            )
        )
    if category == "authority promotion":
        return "authority_promotion" in risk_tags or any(
            signal in text for signal in ("authority", "promote")
        )
    if category == "code patch":
        return (
            task_class in {"IMPLEMENTATION", "PATCH"}
            and any(
                signal in text
                for signal in ("implement", "modify", "patch")
            )
        ) or "ssot_mutation" in risk_tags or "ssot" in text
    if category == "design review":
        return task_class == "DESIGN_REVIEW" and any(
            signal in text
            for signal in ("boundary", "design", "interface", "review")
        )
    if category == "research task":
        return task_class == "RESEARCH"
    raise AssertionError(f"unknown category: {category}")


def _assert_exact_corpus(directory: Path, expected: set[str]) -> None:
    actual = _fixture_names(directory)
    assert actual == expected, (
        f"{directory.relative_to(ROOT)} corpus mismatch; "
        f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
    )


def _load_expected_drift_envelopes() -> dict[str, dict[str, object]]:
    _assert_exact_corpus(DRIFT, set(EXPECTED_DRIFT_CODES))
    envelopes: dict[str, dict[str, object]] = {}
    for filename in EXPECTED_DRIFT_CODES:
        value = _load_json(DRIFT / filename)
        assert isinstance(value, dict), f"{filename} must contain an object"
        envelopes[filename] = value
    return envelopes


def test_fixture_counts_meet_contract() -> None:
    counts = {
        "positive": len(_fixture_names(POSITIVE)),
        "negative": len(_fixture_names(NEGATIVE)),
        "drift": len(_fixture_names(DRIFT)),
    }
    assert (
        counts["positive"] >= 30
        and counts["negative"] >= 30
        and counts["drift"] == 20
    ), f"fixture corpus is absent or undersized: {counts}"


@pytest.mark.parametrize(
    ("directory", "category_by_filename"),
    [
        (POSITIVE, CATEGORY_BY_POSITIVE_FILENAME),
        (NEGATIVE, CATEGORY_BY_NEGATIVE_FILENAME),
    ],
    ids=("positive", "negative"),
)
def test_required_category_coverage_is_explicit_and_content_backed(
    directory: Path, category_by_filename: dict[str, str]
) -> None:
    expected_names = set(category_by_filename)
    _assert_exact_corpus(directory, expected_names)

    counts = Counter(category_by_filename.values())
    assert set(counts) == REQUIRED_CATEGORIES
    undercovered = {
        category: counts[category]
        for category in REQUIRED_CATEGORIES
        if counts[category] < 2
    }
    assert not undercovered, f"categories require two fixtures: {undercovered}"

    mismatches = {}
    for filename, category in category_by_filename.items():
        card = _load_json(directory / filename)
        if not _matches_category_signal(card, category):
            mismatches[filename] = category
    assert not mismatches, f"category signals do not match content: {mismatches}"


def test_every_positive_fixture_is_valid() -> None:
    paths = sorted(POSITIVE.glob("*.json")) if POSITIVE.is_dir() else []
    assert len(paths) >= 30, f"positive corpus undersized: {len(paths)} < 30"

    invalid = {}
    for path in paths:
        result = validate_card(_load_json(path))
        if not result.valid:
            invalid[path.name] = [issue.code for issue in result.issues]
    assert not invalid, f"positive fixtures must all validate: {invalid}"


def test_every_task_class_has_positive_and_negative_coverage() -> None:
    positive_classes = {
        card.get("task_class")
        for path in POSITIVE.glob("*.json")
        if isinstance((card := _load_json(path)), dict)
    }
    negative_classes = {
        card.get("task_class")
        for path in NEGATIVE.glob("*.json")
        if isinstance((card := _load_json(path)), dict)
    }
    missing_positive = TASK_CLASSES - positive_classes
    missing_negative = TASK_CLASSES - negative_classes
    assert not missing_positive and not missing_negative, (
        f"task-class fixture coverage missing; "
        f"positive={sorted(missing_positive)}, "
        f"negative={sorted(missing_negative)}"
    )


def test_negative_issue_code_mapping_is_complete_and_exact() -> None:
    expected_names = set(EXPECTED_NEGATIVE_CODES)
    assert expected_names == set(CATEGORY_BY_NEGATIVE_FILENAME)
    assert len(expected_names) >= 30
    _assert_exact_corpus(NEGATIVE, expected_names)

    mismatches = {}
    for filename, expected_codes in EXPECTED_NEGATIVE_CODES.items():
        actual_codes = _issue_codes(_load_json(NEGATIVE / filename))
        if actual_codes != expected_codes:
            mismatches[filename] = {
                "expected": sorted(expected_codes),
                "actual": sorted(actual_codes),
            }
    assert not mismatches, f"negative issue-code mismatch: {mismatches}"


def test_negative_blocking_recall_is_exactly_one() -> None:
    assert BLOCKING_GATE_EXPECTATIONS
    assert set(BLOCKING_GATE_EXPECTATIONS) <= set(EXPECTED_NEGATIVE_CODES)
    _assert_exact_corpus(NEGATIVE, set(EXPECTED_NEGATIVE_CODES))

    misses = {}
    for filename, expected_gate_codes in BLOCKING_GATE_EXPECTATIONS.items():
        actual_codes = _issue_codes(_load_json(NEGATIVE / filename))
        if not expected_gate_codes <= actual_codes:
            misses[filename] = {
                "expected_gate_codes": sorted(expected_gate_codes),
                "actual": sorted(actual_codes),
            }
    total = len(BLOCKING_GATE_EXPECTATIONS)
    blocking_recall = (total - len(misses)) / total
    assert blocking_recall == 1.0, (
        f"blocking recall={blocking_recall:.3f}; misses={misses}"
    )


def test_unknown_negative_cases_fail_closed_for_the_named_reason() -> None:
    _assert_exact_corpus(NEGATIVE, set(EXPECTED_NEGATIVE_CODES))

    misses = {}
    for filename, expected_codes in UNKNOWN_FAIL_SAFE_EXPECTATIONS.items():
        actual_codes = _issue_codes(_load_json(NEGATIVE / filename))
        if not expected_codes <= actual_codes:
            misses[filename] = {
                "expected": sorted(expected_codes),
                "actual": sorted(actual_codes),
            }
    assert not misses, f"UNKNOWN fail-safe misses: {misses}"


def test_drift_envelopes_are_labeled_and_embed_valid_cards() -> None:
    assert len(EXPECTED_DRIFT_CODES) == 20
    envelopes = _load_expected_drift_envelopes()
    failures = []

    for filename, expected_codes in EXPECTED_DRIFT_CODES.items():
        envelope = envelopes[filename]
        if set(envelope) != {"before", "after", "label", "expected_codes"}:
            failures.append(f"{filename}: envelope keys={sorted(envelope)}")
            continue
        expected_label = "drift" if expected_codes else "safe"
        if envelope["label"] != expected_label:
            failures.append(f"{filename}: label={envelope['label']!r}")
        declared_codes = envelope["expected_codes"]
        if not isinstance(declared_codes, list) or not all(
            isinstance(code, str) for code in declared_codes
        ):
            failures.append(f"{filename}: expected_codes must be a string list")
        elif len(declared_codes) != len(set(declared_codes)):
            failures.append(f"{filename}: expected_codes contains duplicates")
        elif set(declared_codes) != expected_codes:
            failures.append(
                f"{filename}: declared={sorted(declared_codes)}, "
                f"expected={sorted(expected_codes)}"
            )

        for side in ("before", "after"):
            card = envelope[side]
            result = validate_card(card)
            if not result.valid:
                failures.append(
                    f"{filename}:{side} invalid="
                    f"{[issue.code for issue in result.issues]}"
                )

    assert not failures, "invalid drift envelopes:\n" + "\n".join(failures)


def test_drift_recall_and_exact_expected_codes() -> None:
    envelopes = _load_expected_drift_envelopes()
    drift_names = {
        filename
        for filename, expected in EXPECTED_DRIFT_CODES.items()
        if expected
    }
    assert len(drift_names) == 16

    misses = {}
    exact_mismatches = {}
    for filename in drift_names:
        envelope = envelopes[filename]
        report = detect_boundary_drift(envelope["before"], envelope["after"])
        actual_codes = {finding.code for finding in report.findings}
        expected_codes = EXPECTED_DRIFT_CODES[filename]
        if not report.drifted or not expected_codes <= actual_codes:
            misses[filename] = sorted(actual_codes)
        if actual_codes != expected_codes:
            exact_mismatches[filename] = {
                "expected": sorted(expected_codes),
                "actual": sorted(actual_codes),
            }

    drift_recall = (len(drift_names) - len(misses)) / len(drift_names)
    assert drift_recall >= 0.95, (
        f"drift recall={drift_recall:.3f}; misses={misses}"
    )
    assert not exact_mismatches, f"unexpected drift codes: {exact_mismatches}"


def test_safe_control_rate_is_exactly_one() -> None:
    envelopes = _load_expected_drift_envelopes()
    safe_names = {
        filename
        for filename, expected in EXPECTED_DRIFT_CODES.items()
        if not expected
    }
    assert len(safe_names) == 4

    false_positives = {}
    for filename in safe_names:
        envelope = envelopes[filename]
        report = detect_boundary_drift(envelope["before"], envelope["after"])
        actual_codes = {finding.code for finding in report.findings}
        if report.drifted or actual_codes:
            false_positives[filename] = sorted(actual_codes)

    safe_control_rate = (len(safe_names) - len(false_positives)) / len(
        safe_names
    )
    assert safe_control_rate == 1.0, (
        f"safe control rate={safe_control_rate:.3f}; "
        f"false_positives={false_positives}"
    )
