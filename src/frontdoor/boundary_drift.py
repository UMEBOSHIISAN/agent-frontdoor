"""Pure, deterministic comparison of validated task-card boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DriftFinding:
    """One named boundary expansion between two task cards."""

    code: str
    message: str


@dataclass(frozen=True)
class DriftReport:
    """The immutable result of comparing two task cards."""

    drifted: bool
    findings: tuple[DriftFinding, ...]


_MUTATION_PATTERN = re.compile(
    r"\b(?:appl(?:y|ies|ied|ying)|chang(?:e|es|ed|ing)|"
    r"creat(?:e|es|ed|ing)|edit(?:s|ed|ing)?|"
    r"implement(?:s|ed|ing)?|modif(?:y|ies|ied|ying)|"
    r"mutat(?:e|es|ed|ing)|patch(?:es|ed|ing)?|"
    r"refactor(?:s|ed|ing)?|replac(?:e|es|ed|ing)|"
    r"updat(?:e|es|ed|ing)|writ(?:e|es|ing|ten)|wrote)\b"
)
_ARCHITECTURE_MIGRATION_PATTERN = re.compile(
    r"\b(?:architecture (?:migration|redesign|refactor)|"
    r"(?:migrate|redesign|rearchitect)(?: the)? architecture)\b"
)
_EXTERNAL_PUBLISH_PATTERN = re.compile(
    r"\b(?:external(?:ly)? publish|publish(?:ed|es|ing)?(?: externally)?|"
    r"external post(?:ing)?|post externally|go live)\b"
)
_PROPOSAL_ONLY_PATTERN = re.compile(
    r"\b(?:proposal only|propose only|proposal for review)\b"
)
_AUTHORITY_PROMOTION_PATTERN = re.compile(
    r"\b(?:authority promotion|approved authority|grant authority|"
    r"promote(?: the)? proposal|promote(?:d|s|ing)?(?: to)? authority|"
    r"elevate(?:d|s|ing)? permissions?)\b"
)
_BOUNDED_SCOPE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bbounded files?\b",
        r"\b(?:named|listed|requested|specified) files? only\b",
        r"\b(?:edit|modify|patch|read|review) only\b",
        r"\bonly [^,;]+\.(?:py|js|ts|json|md|toml|ya?ml)\b",
    )
)
_BROAD_SCOPE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bbroad refactor\b",
        r"\bunrelated (?:files?|modules?|projects?)\b",
        r"\b(?:entire|whole) (?:codebase|project|repository|repo)\b",
        r"\b(?:codebase|project|repository|repo) wide\b",
        r"\bacross (?:all|the) (?:codebase|project|repository|repo)\b",
        r"\ball files?\b",
    )
)


def _normalize_text(value: str) -> str:
    return " ".join(
        part for part in re.split(r"[^\w/.]+", value.casefold()) if part
    )


def _normalized_actions(card: Mapping[str, object]) -> tuple[str, ...]:
    actions = card.get("allowed_actions", ())
    if not isinstance(actions, (list, tuple)):
        return ()
    return tuple(
        _normalize_text(action) for action in actions if isinstance(action, str)
    )


def _normalized_next_step(card: Mapping[str, object]) -> str:
    step = card.get("next_safe_step", "")
    return _normalize_text(step) if isinstance(step, str) else ""


def _boundary_text(card: Mapping[str, object]) -> str:
    return " ".join((*_normalized_actions(card), _normalized_next_step(card)))


def _risk_tags(card: Mapping[str, object]) -> frozenset[str]:
    tags = card.get("risk_tags", ())
    if not isinstance(tags, (list, tuple)):
        return frozenset()
    return frozenset(tag for tag in tags if isinstance(tag, str))


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def detect_boundary_drift(
    before: Mapping[str, object], after: Mapping[str, object]
) -> DriftReport:
    """Return every named boundary expansion without mutating either card."""

    before_class = before.get("task_class")
    after_class = after.get("task_class")
    before_text = _boundary_text(before)
    after_text = _boundary_text(after)
    added_risks = _risk_tags(after) - _risk_tags(before)
    findings: list[DriftFinding] = []

    if (
        before_class == "AUDIT"
        and not _MUTATION_PATTERN.search(before_text)
        and (
            after_class == "IMPLEMENTATION"
            or _MUTATION_PATTERN.search(after_text)
        )
    ):
        findings.append(
            DriftFinding(
                code="audit_to_mutation",
                message="Read-only audit scope expanded to mutation work.",
            )
        )

    if before_class == "DESIGN_REVIEW" and after_class == "IMPLEMENTATION":
        findings.append(
            DriftFinding(
                code="design_to_implementation",
                message="Design review scope expanded to implementation.",
            )
        )

    if (
        before_class == "INSTALLATION"
        and _ARCHITECTURE_MIGRATION_PATTERN.search(after_text)
        and not _ARCHITECTURE_MIGRATION_PATTERN.search(before_text)
    ):
        findings.append(
            DriftFinding(
                code="install_to_architecture_migration",
                message="Installation-only scope expanded to architecture migration.",
            )
        )

    if (
        before_class == "CONTENT_DRAFT"
        and (
            "external_publish" in added_risks
            or _EXTERNAL_PUBLISH_PATTERN.search(after_text)
        )
        and not _EXTERNAL_PUBLISH_PATTERN.search(before_text)
    ):
        findings.append(
            DriftFinding(
                code="draft_to_external_publish",
                message="Local drafting scope expanded to external publishing.",
            )
        )

    if (
        _PROPOSAL_ONLY_PATTERN.search(before_text)
        and (
            "authority_promotion" in added_risks
            or _AUTHORITY_PROMOTION_PATTERN.search(after_text)
        )
        and not _AUTHORITY_PROMOTION_PATTERN.search(before_text)
    ):
        findings.append(
            DriftFinding(
                code="proposal_to_authority_promotion",
                message="Proposal-only scope expanded to authority promotion.",
            )
        )

    if (
        _matches_any(before_text, _BOUNDED_SCOPE_PATTERNS)
        and _matches_any(after_text, _BROAD_SCOPE_PATTERNS)
        and not _matches_any(before_text, _BROAD_SCOPE_PATTERNS)
    ):
        findings.append(
            DriftFinding(
                code="bounded_files_to_broad_refactor",
                message="Bounded file scope expanded to an unrelated broad refactor.",
            )
        )

    immutable_findings = tuple(findings)
    return DriftReport(bool(immutable_findings), immutable_findings)
