import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
COMMUNITY_FILES = (
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "CODE_OF_CONDUCT.md",
    ROOT / "SUPPORT.md",
    ROOT / ".github/ISSUE_TEMPLATE/bug.yml",
    ROOT / ".github/ISSUE_TEMPLATE/feature.yml",
    ROOT / ".github/ISSUE_TEMPLATE/config.yml",
    ROOT / ".github/pull_request_template.md",
)
PRIVATE_REPORT = (
    "https://github.com/UMEBOSHIISAN/agent-frontdoor/"
    "security/advisories/new"
)


def test_community_files_exist_and_are_placeholder_free() -> None:
    for path in COMMUNITY_FILES:
        text = path.read_text(encoding="utf-8")
        assert text.strip(), path
        for forbidden in (
            "TO" + "DO", "T" + "BD", "[INSERT", "example.com", "CC_UNAUDITED",
            "REPEATED_EXCESSIVE_DERAILMENT",
        ):
            assert forbidden not in text, (path, forbidden)
        assert "/" + "Users" + "/" not in text
        assert not re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\b", text)


def test_security_policy_uses_only_private_reporting() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "unreleased source" in text.casefold()
    assert PRIVATE_REPORT in text
    assert "Do not open a public issue" in text
    assert "not a security boundary" in text
    assert "response within" not in text.casefold()
    assert "discussions" not in text.casefold()


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        assert key not in result, f"duplicate JSON key: {key}"
        result[key] = value
    return result


def _github_form(filename: str) -> dict:
    path = ROOT / ".github" / "ISSUE_TEMPLATE" / filename
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
    )


def test_issue_forms_are_complete_json_compatible_yaml() -> None:
    expected_ids = {
        "bug.yml": {
            "area", "revision", "environment", "reproduction", "expected",
            "actual", "logs", "checks",
        },
        "feature.yml": {
            "area", "problem", "proposal", "alternatives", "boundaries",
            "evidence", "checks",
        },
    }
    expected_label = {"bug.yml": "bug", "feature.yml": "enhancement"}
    allowed_types = {"markdown", "input", "textarea", "dropdown", "checkboxes"}

    for filename, required_ids in expected_ids.items():
        form = _github_form(filename)
        assert isinstance(form.get("name"), str) and form["name"].strip()
        assert isinstance(form.get("description"), str) and form["description"].strip()
        assert isinstance(form.get("body"), list) and form["body"]
        labels = form.get("labels")
        assert isinstance(labels, list) and labels
        assert all(isinstance(label, str) and label.strip() for label in labels)
        assert expected_label[filename] in labels

        assert all(isinstance(item, dict) for item in form["body"])
        fields = [item for item in form["body"] if "id" in item]
        ids = [item["id"] for item in fields]
        assert len(ids) == len(set(ids))
        assert required_ids == set(ids)
        assert {item.get("type") for item in form["body"]} <= allowed_types
        for item in form["body"]:
            assert isinstance(item.get("attributes"), dict)


def test_issue_chooser_is_complete_json_compatible_yaml() -> None:
    config = _github_form("config.yml")
    assert config == {
        "blank_issues_enabled": True,
        "contact_links": [
            {
                "name": "Confidential security report",
                "url": PRIVATE_REPORT,
                "about": (
                    "Report suspected vulnerabilities privately; "
                    "do not open a public issue."
                ),
            },
            {
                "name": "Support and usage routes",
                "url": (
                    "https://github.com/UMEBOSHIISAN/agent-frontdoor/"
                    "blob/main/SUPPORT.md"
                ),
                "about": (
                    "Choose the appropriate support route before opening an issue."
                ),
            },
        ],
    }
