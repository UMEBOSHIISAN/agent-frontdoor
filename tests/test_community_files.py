from copy import deepcopy
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
EXPECTED_IDS = {
    "bug.yml": {
        "area", "revision", "environment", "reproduction", "expected",
        "actual", "logs", "checks",
    },
    "feature.yml": {
        "area", "problem", "proposal", "alternatives", "boundaries",
        "evidence", "checks",
    },
}
EXPECTED_LABEL = {"bug.yml": "bug", "feature.yml": "enhancement"}
ALLOWED_TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}


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


def test_code_of_conduct_matches_the_project_moderation_boundary() -> None:
    text = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    for marker in (
        "participation in this GitHub repository and its GitHub-hosted project spaces",
        "Maintainers moderate visible repository contributions",
        "GitHub's documented abuse-reporting tools",
        "use that venue's own moderation or safety route",
    ):
        assert marker in normalized
    for unsupported_scope in (
        "applies within all community spaces",
        "officially representing the community",
        "official e-mail address",
        "official social media account",
        "external channels like social media",
        "No public or private interaction",
        "separate private conduct inbox",
        "security-advisory",
    ):
        assert unsupported_scope not in text


def test_contributing_activates_venv_before_python_test_commands() -> None:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    activation = "source .venv/bin/activate"
    assert activation in text
    activation_position = text.index(activation)
    test_commands = [
        match.start() for match in re.finditer(r"^python3 -m pytest ", text, re.MULTILINE)
    ]
    assert test_commands
    assert all(activation_position < position for position in test_commands)


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


def _validate_issue_form(form: dict, filename: str) -> None:
    assert isinstance(form, dict)
    assert isinstance(form.get("name"), str) and form["name"].strip()
    assert isinstance(form.get("description"), str) and form["description"].strip()
    assert isinstance(form.get("body"), list) and form["body"]
    labels = form.get("labels")
    assert isinstance(labels, list) and labels
    assert all(isinstance(label, str) and label.strip() for label in labels)
    assert EXPECTED_LABEL[filename] in labels

    ids = []
    for item in form["body"]:
        assert isinstance(item, dict)
        item_type = item.get("type")
        assert isinstance(item_type, str) and item_type.strip()
        assert item_type in ALLOWED_TYPES
        attributes = item.get("attributes")
        assert isinstance(attributes, dict)

        if item_type == "markdown":
            value = attributes.get("value")
            assert isinstance(value, str) and value.strip()
            continue

        item_id = item.get("id")
        assert isinstance(item_id, str) and item_id.strip()
        ids.append(item_id)
        for key in ("label", "description"):
            value = attributes.get(key)
            assert isinstance(value, str) and value.strip()

        validations = item.get("validations")
        assert isinstance(validations, dict)
        assert type(validations.get("required")) is bool

        if item_type == "dropdown":
            options = attributes.get("options")
            assert isinstance(options, list) and options
            assert all(
                isinstance(option, str) and option.strip() for option in options
            )

        if item_type == "checkboxes":
            options = attributes.get("options")
            assert isinstance(options, list) and options
            for option in options:
                assert isinstance(option, dict)
                label = option.get("label")
                assert isinstance(label, str) and label.strip()
                assert type(option.get("required")) is bool

    assert len(ids) == len(set(ids))
    assert EXPECTED_IDS[filename] == set(ids)


def test_issue_forms_are_complete_json_compatible_yaml() -> None:
    for filename in EXPECTED_IDS:
        _validate_issue_form(_github_form(filename), filename)


def test_issue_form_validation_rejects_malformed_nested_values() -> None:
    malformed_forms = []

    invalid_validations = deepcopy(_github_form("bug.yml"))
    invalid_validations["body"][0]["validations"] = []
    malformed_forms.append(("validations is not a map", invalid_validations))

    invalid_required = deepcopy(_github_form("bug.yml"))
    invalid_required["body"][0]["validations"]["required"] = "yes"
    malformed_forms.append(("validation required is not a boolean", invalid_required))

    missing_dropdown_options = deepcopy(_github_form("bug.yml"))
    del missing_dropdown_options["body"][0]["attributes"]["options"]
    malformed_forms.append(("dropdown options are missing", missing_dropdown_options))

    empty_dropdown_option = deepcopy(_github_form("bug.yml"))
    empty_dropdown_option["body"][0]["attributes"]["options"][0] = ""
    malformed_forms.append(("dropdown option is empty", empty_dropdown_option))

    invalid_checkbox_options = deepcopy(_github_form("bug.yml"))
    invalid_checkbox_options["body"][-1]["attributes"]["options"] = {}
    malformed_forms.append(("checkbox options are not a list", invalid_checkbox_options))

    empty_checkbox_label = deepcopy(_github_form("bug.yml"))
    empty_checkbox_label["body"][-1]["attributes"]["options"][0]["label"] = ""
    malformed_forms.append(("checkbox option label is empty", empty_checkbox_label))

    invalid_checkbox_required = deepcopy(_github_form("bug.yml"))
    invalid_checkbox_required["body"][-1]["attributes"]["options"][0][
        "required"
    ] = "yes"
    malformed_forms.append(
        ("checkbox option required is not a boolean", invalid_checkbox_required)
    )

    accepted = []
    for description, form in malformed_forms:
        try:
            _validate_issue_form(form, "bug.yml")
        except AssertionError:
            continue
        accepted.append(description)
    assert not accepted, f"malformed forms accepted: {accepted}"


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
