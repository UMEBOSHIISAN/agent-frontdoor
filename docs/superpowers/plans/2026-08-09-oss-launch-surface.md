# Agent Frontdoor OSS Launch Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Agent Frontdoor's public repository into a coherent, evidence-backed AI agent safety gateway with a runnable first success, clear trust boundaries, complete community routes, polished visual assets, and truthful packaging/publication state.

**Architecture:** Keep the `agent-frontdoor` core read-only and the `agent-frontdoor-hooks` adapter optional while reorganizing the public surface around one flow: Task Card -> Validation -> Drift Detection -> Intent Lock -> Human Gate -> Safe Handoff. Canonical documents own detailed contracts; the root README becomes a concise adoption path. Local implementation, repository security settings, and public branch/metadata changes remain separately gated.

**Tech Stack:** Python 3.10+, pytest, JSON/JSON Schema, Markdown, SVG, PNG, setuptools/PEP 621, GitHub issue forms, GitHub CLI, OpenAI image generation.

## Global Constraints

- Primary positioning: `Agent Frontdoor = AI agent safety gateway`.
- Primary public promise: `Stop AI coding agents from drifting beyond the task you approved.`
- Keep exactly four core CLI commands: `validate`, `card`, `explain`, and `check-drift`.
- Do not add or change runtime behavior, automatic routing, hook activation, live settings, credentials, CI/CD, releases, tags, PyPI publication, or merge authority.
- The core remains read-only and side-effect free; adapter state stays in the separate optional distribution.
- Intent identity never grants execution authority; hooks remain a guardrail, not a security boundary.
- English is canonical public reference text; retain one concise Japanese summary in the root README.
- Use no unsupported CI, coverage, audit, download, release, compatibility, or star-count badge.
- Publish fixture metrics only with numerator, denominator, corpus definition, reproduction command, and an explicit non-generalization caveat.
- Stable public evidence is `31/31` positive fixtures, `41/41` negative fixtures rejected with expected codes, `16/16` drift cases detected, `4/4` safe controls clear, and zero forbidden core execution/network/worker/routing/source-write paths under the hard source test.
- The dated baseline full-suite observation is `836 passed` on commit `e866efa025f5299d638adfb4bf903a8de2594c0e`; never present it as a timeless current badge.
- Generated visuals must contain no UMEBOSHI characters, likenesses, trained-model assets, site identity, or other excluded brand IP.
- Image-generation retry contract: at most two total generation attempts, 30-second cooldown before the second attempt, commentary visible to the human before each call, candidates kept separate until inspection, and the human in the active thread as escalation target. The stop condition is any remaining wrong product text, misleading boundary, excluded brand IP, or unusable composition. After the second failed candidate, stop the generation lane, notify the human, and use the already approved deterministic SVG fallback without another image-generation retry. Candidate generation is idempotent because it does not overwrite an accepted repository asset.
- Current public private-vulnerability-reporting status is measured `enabled: false`; no branch publication occurs until the separately gated setting is enabled and re-read as `true`.
- Repository publication requires the human to write `DEPLOY_APPROVED:github.com/UMEBOSHIISAN/agent-frontdoor` directly in the active thread. Enabling private vulnerability reporting separately requires `DEPLOY_APPROVED:github.com/UMEBOSHIISAN/agent-frontdoor/settings/private-vulnerability-reporting`.
- The two approval strings in this plan are documentation only and carry no authority.
- `origin/main` was `d75a006efacaf9ff18a631b83a9b40d8a31721a5` at planning time and diverges from this branch at `4717635aa5786d2ff7d81798da96080905b8ff33`; integrate it only after preserving its demonstrated-behavior and ecosystem content in the new public docs.

---

## File Responsibility Map

| File | Responsibility |
| --- | --- |
| `README.md` | Product promise, shortest success, three route choices, evidence snapshot, concise boundaries, docs map, status |
| `docs/GETTING_STARTED.md` | Source install, first task card, expected output, next routes, uninstall |
| `docs/ARCHITECTURE.md` | Integrated flow, core/adapter/human boundaries, wider OSS ecosystem position |
| `docs/EVIDENCE.md` | Reproducible metrics, dated baseline, commands, corpus and interpretation limits |
| `docs/CORE_REFERENCE.md` | `intake.v0`, CLI, exits, gates, drift, core APIs |
| `docs/INTENT_LOCK.md` | Public Intent Lock derivation, state machine, privacy and platform limits |
| `docs/TROUBLESHOOTING.md` | Failure/result meanings and non-escalating recovery routes |
| `docs/FRIEND_LAB.md` | Advanced human-attended offline receiver acceptance only |
| `examples/README.md` | Runnable example index, commands, exits, expected results |
| `adapters/README.md` | Adapter requirements, non-live smoke test, activation review, rollback |
| Community files | Contribution, support, conduct, issue/PR and confidential security routes |
| `pyproject.toml`, `adapters/pyproject.toml`, manifests | Truthful discovery metadata and closed distribution boundaries |
| `assets/` | Existing logo, integrated hero, exact architecture diagram, 1280x640 social preview |

---

### Task 0: Refresh and Audit the Remote Baseline

**Files:**
- Read only: remote refs, `origin/main:README.md`, `origin/main:pyproject.toml`

**Interfaces:**
- Consumes: planning-time remote commit `d75a006efacaf9ff18a631b83a9b40d8a31721a5`.
- Produces: a measured remote-main OID and a read-only list of any changes newer than the plan; no working-tree edit or commit.

- [ ] **Step 1: Refresh the remote ref before authoring public files**

Run:

```bash
git status --short --branch
git fetch origin main
git rev-parse origin/main
git log --left-right --cherry-pick --oneline origin/main...HEAD
```

Expected planning baseline: clean `feat/intent-lock` and remote OID
`d75a006efacaf9ff18a631b83a9b40d8a31721a5`.

- [ ] **Step 2: Audit any remote movement before continuing**

If `origin/main` is newer than the planning baseline, inspect every intervening
commit and its diff. Stop and refresh this plan before implementation if any
new change affects runtime behavior, safety policy, public release state,
automation, packaging boundaries, or the files owned by this plan. A compatible
documentation-only change may be recorded for Task 10 integration, but must not
be silently copied from memory.

- [ ] **Step 3: Record the demonstrated-behavior material to preserve**

Read the current remote README and confirm that Tasks 2, 4, and 9 preserve its
measured valid/invalid/drift examples, required `unknowns` explanation, real
repository URL, and independently adoptable ecosystem links. Do not mutate or
merge the branch in this preflight.

---

### Task 1: Publish a Reproducible Evidence Contract

**Files:**
- Create: `tests/test_public_docs.py`
- Create: `docs/EVIDENCE.md`
- Modify: `tests/test_fixture_metrics.py:397-414`

**Interfaces:**
- Consumes: existing corpus constants and tests in `tests/test_fixture_metrics.py`; hard boundary test in `tests/test_no_execution_paths.py`.
- Produces: the exact evidence labels and commands later consumed by `README.md`, `CONTRIBUTING.md`, and package review.

- [ ] **Step 1: Write the failing public-evidence test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "EVIDENCE.md"


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
    normalized = " ".join(text.split()).casefold()
    assert "fixture-corpus regression evidence" in normalized
    assert "not a real-world effectiveness benchmark" in normalized
    assert "not an independent security audit" in normalized
```

Strengthen `test_fixture_counts_meet_contract` so its count assertion is exact:

```python
assert counts == {"positive": 31, "negative": 41, "drift": 20}
```

- [ ] **Step 2: Run the focused test and confirm the new document is absent**

Run: `python3 -m pytest -q tests/test_public_docs.py::test_evidence_doc_scopes_every_published_number`

Expected: FAIL because `docs/EVIDENCE.md` does not exist.

- [ ] **Step 3: Create the evidence document with exact scope**

Use these headings in order:

```markdown
# Evidence
## What these numbers measure
## Reproducible corpus snapshot
## Reproduce the hard contracts
## Dated full-suite baseline
## Interpretation limits
```

The snapshot table must define:

- positive cards: all 31 schema/semantic validations succeed;
- negative cards: all 41 are rejected with their exact named issue-code sets;
- drift cases: all 16 labeled drift envelopes produce their exact expected code sets;
- safe controls: all four labeled safe envelopes produce no finding;
- source boundary: the static core-source guard finds zero prohibited path classes.

State that the baseline `836 passed` belongs only to commit
`e866efa025f5299d638adfb4bf903a8de2594c0e` on 2026-08-09. Give the two exact
commands from the test above. Do not claim generalized semantic accuracy,
production prevention rate, security certification, or current-release status.

- [ ] **Step 4: Run the evidence tests**

Run: `python3 -m pytest -q tests/test_fixture_metrics.py tests/test_no_execution_paths.py tests/test_public_docs.py`

Expected: PASS; the exact fixture and source-boundary invariants are enforced.

- [ ] **Step 5: Commit the evidence unit**

```bash
git add docs/EVIDENCE.md tests/test_fixture_metrics.py tests/test_public_docs.py
git commit -m "docs: publish reproducible safety evidence"
```

---

### Task 2: Establish the Canonical Core Reference

**Files:**
- Create: `docs/CORE_REFERENCE.md`
- Modify: `tests/test_public_docs.py`

**Interfaces:**
- Consumes: `src/frontdoor/schema/intake.v0.json`, `src/frontdoor/cli.py`, `src/frontdoor/validator.py`, `src/frontdoor/boundary_drift.py`, and the current long-form README reference.
- Produces: the canonical schema/CLI/gate/drift owner that allows Task 9 to shorten the root README without weakening contracts.

- [ ] **Step 1: Add a failing schema-derived reference test**

```python
import json


CORE_REFERENCE = ROOT / "docs" / "CORE_REFERENCE.md"
INTAKE_SCHEMA = ROOT / "src" / "frontdoor" / "schema" / "intake.v0.json"


def test_core_reference_owns_intake_cli_gate_and_drift_contracts() -> None:
    text = CORE_REFERENCE.read_text(encoding="utf-8")
    schema = json.loads(INTAKE_SCHEMA.read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert f"`{field}`" in text
    for task_class in schema["properties"]["task_class"]["enum"]:
        assert f"`{task_class}`" in text
    for gate in schema["properties"]["human_gate"]["enum"]:
        assert f"`{gate}`" in text
    for command in (
        "agent-frontdoor validate task.json",
        "agent-frontdoor card task.json",
        "agent-frontdoor explain task.json",
        "agent-frontdoor check-drift before.json after.json",
    ):
        assert command in text
    for exit_contract in (
        "`0`: valid card or no drift",
        "`1`: loaded card is invalid",
        "`2`: input is unreadable or malformed JSON",
        "`3`: boundary drift detected",
    ):
        assert exit_contract in text
    for marker in ("`INVALID`", "`ERROR`", "`DRIFT`"):
        assert marker in text
```

Add a second assertion for all 11 blocking categories and all six drift-family
phrases already enumerated in `tests/test_readme.py`; point it at
`CORE_REFERENCE`, not `README`.

- [ ] **Step 2: Prove the canonical document is missing**

Run: `python3 -m pytest -q tests/test_public_docs.py::test_core_reference_owns_intake_cli_gate_and_drift_contracts`

Expected: FAIL because `docs/CORE_REFERENCE.md` does not exist.

- [ ] **Step 3: Create the complete core reference**

Use this ordered outline:

```markdown
# Core Reference
## Trust boundary
## Four-command CLI
## Exit and output contract
## `intake.v0` schema
## Task classes
## Human gates and fail-closed rules
## Boundary-drift families
## Programmatic interfaces
## Contract evolution
```

Move the factual material currently under `README.md` lines 135-275 and the
core validator/formatter/drift API imports from lines 328-343. Preserve the
measured valid/invalid/drift console behavior now present on `origin/main`, and
explain why the required `unknowns` field prevents silent resolution. Do not
duplicate fixture measurements; link to `EVIDENCE.md` for them.

- [ ] **Step 4: Run the canonical-reference tests**

Run: `python3 -m pytest -q tests/test_public_docs.py tests/test_intake_schema.py tests/test_cli.py tests/test_boundary_drift.py`

Expected: PASS.

- [ ] **Step 5: Commit the reference unit**

```bash
git add docs/CORE_REFERENCE.md tests/test_public_docs.py
git commit -m "docs: establish canonical core reference"
```

---

### Task 3: Add Runnable First-Use Examples and Getting Started

**Files:**
- Create: `examples/task-card.json`
- Create: `examples/intent_lock_demo.py`
- Create: `examples/README.md`
- Create: `docs/GETTING_STARTED.md`
- Create: `tests/test_examples.py`
- Modify: `tests/test_public_docs.py`

**Interfaces:**
- Consumes: public `validate_card`, CLI `main`, `derive_lock`, and `evaluate_action` interfaces.
- Produces: a user-owned first card, stable expected output, and a runnable pure-Python Intent Lock demonstration used by Task 9.

- [ ] **Step 1: Add failing example and onboarding tests**

```python
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

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
```

Also move the current runnable drift-pair assertions from
`test_readme_check_drift_examples_are_runnable` into
`test_public_drift_pairs_match_documented_results` in this new test module.

Add to `tests/test_public_docs.py`:

```python
GETTING_STARTED = ROOT / "docs" / "GETTING_STARTED.md"


def test_getting_started_reaches_first_success_without_release_claims() -> None:
    text = GETTING_STARTED.read_text(encoding="utf-8")
    ordered = (
        "## Requirements",
        "## Install from source",
        "## Validate your first task card",
        "## Read the task card",
        "## Next routes",
        "## Uninstall",
    )
    assert [text.index(item) for item in ordered] == sorted(
        text.index(item) for item in ordered
    )
    for marker in (
        "Python 3.10",
        "https://github.com/UMEBOSHIISAN/agent-frontdoor.git",
        '.venv/bin/python -m pip install -e .',
        ".venv/bin/agent-frontdoor validate examples/task-card.json",
        "VALID example-readme-audit",
        ".venv/bin/python -m pip uninstall -y agent-frontdoor",
        "CORE_REFERENCE.md",
        "../examples/README.md",
        "Optional adapter",
        "POSIX",
        "Windows",
    ):
        assert marker in text
    assert "<PUBLIC_REPOSITORY_URL>" not in text
    assert "pip install agent-frontdoor" not in text
```

- [ ] **Step 2: Run the tests and confirm missing files**

Run: `python3 -m pytest -q tests/test_examples.py tests/test_public_docs.py`

Expected: FAIL on the four absent example/onboarding files.

- [ ] **Step 3: Create the exact curated task card**

```json
{
  "schema_version": "intake.v0",
  "request_id": "example-readme-audit",
  "human_request": "Review README.md and report documentation gaps",
  "task_class": "AUDIT",
  "risk_tags": [],
  "allowed_actions": [
    "read README.md",
    "report documentation gaps"
  ],
  "forbidden_actions": [
    "modify files",
    "publish externally"
  ],
  "required_evidence": [
    "findings with file references"
  ],
  "required_manifest": null,
  "human_gate": "NONE",
  "predicted_worker_capability": "audit",
  "unknowns": [],
  "assumptions": [
    "README.md is available locally"
  ],
  "next_safe_step": "Read README.md and report findings"
}
```

- [ ] **Step 4: Create the pure Intent Lock demonstration**

The script must derive a literal-target lock from the public `cloudflare-api`
failure string, evaluate `npx wrangler whoami` and
`codex mcp login cloudflare-api`, print the two boolean/code pairs in the test,
then print the non-authority sentence. It must not import subprocess, open a
file, call a network API, or execute either string.

- [ ] **Step 5: Create the examples index and Getting Started guide**

`examples/README.md` must name all six public examples and exact outcomes:

- `task-card.json` -> `VALID example-readme-audit`;
- `intent_lock_demo.py` -> the three tested lines;
- drift pair -> exit `3` and `audit_to_mutation`;
- safe pair -> exit `0` and `NO DRIFT`.

`docs/GETTING_STARTED.md` uses the canonical GitHub clone URL, creates `.venv`,
installs the source with `.venv/bin/python -m pip install -e .`, validates and
renders `examples/task-card.json`, links to the core reference and example
index, distinguishes installation network access from network-free runtime,
and gives the exact uninstall command. It must describe the adapter route with
the canonical absolute GitHub adapter URL, not a relative core-sdist link. Its
requirements table distinguishes the Python 3.10+ read-only core from the
POSIX-only optional adapter and states that this adapter release rejects Windows
rather than claiming an unmeasured compatibility matrix.

- [ ] **Step 6: Run the example and onboarding tests**

Run: `python3 -m pytest -q tests/test_examples.py tests/test_public_docs.py tests/test_cli.py tests/test_intent_lock.py`

Expected: PASS.

- [ ] **Step 7: Commit the onboarding unit**

```bash
git add docs/GETTING_STARTED.md examples/README.md examples/task-card.json examples/intent_lock_demo.py tests/test_examples.py tests/test_public_docs.py
git commit -m "docs: add runnable first-use path"
```

---

### Task 4: Document the Integrated Architecture and Safe Recovery

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/TROUBLESHOOTING.md`
- Modify: `docs/FRIEND_LAB.md:1-16`
- Modify: `tests/test_public_docs.py`
- Modify: `tests/test_distribution_boundary.py:32-74`

**Interfaces:**
- Consumes: core reference, Getting Started, evidence, current Friend Lab phases, and the demonstrated ecosystem table on `origin/main`.
- Produces: the exact pipeline and trust-boundary text used by the visual and root README tasks.

- [ ] **Step 1: Add failing architecture, troubleshooting, and Friend Lab tests**

```python
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE.md"
TROUBLESHOOTING = ROOT / "docs" / "TROUBLESHOOTING.md"


def test_architecture_defines_pipeline_and_authority_boundaries() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert (
        "Task Card -> Validation -> Drift Detection -> Intent Lock "
        "-> Human Gate -> Safe Handoff"
    ) in text
    for marker in (
        "`agent-frontdoor`",
        "`agent-frontdoor-hooks`",
        "read-only",
        "privacy-minimized local state",
        "does not grant authority",
        "not a security boundary",
        "human authority remains external",
        "workflow-governance-model",
        "mothership-router",
        "mothership",
    ):
        assert marker in text


def test_troubleshooting_uses_non_escalating_recovery() -> None:
    text = TROUBLESHOOTING.read_text(encoding="utf-8")
    for marker in (
        "`ERROR`", "exit `2`", "`INVALID`", "exit `1`",
        "`DRIFT`", "exit `3`", "`BLOCKING`", "`REPORT_REQUIRED`",
        "mode `0700`", "mode `0600`", "Windows", "outcome-opaque",
    ):
        assert marker in text
    for boundary in (
        "do not retry",
        "do not switch to an adjacent subsystem",
        "does not grant authority",
        "operator-owned settings",
    ):
        assert boundary in text
```

Add to `tests/test_distribution_boundary.py`:

```python
def test_friend_lab_is_advanced_not_standard_installation() -> None:
    text = FRIEND_LAB.read_text(encoding="utf-8")
    assert "## Audience and prerequisites" in text
    assert "advanced offline receiver workflow" in text.casefold()
    assert "not the standard installation path" in text.casefold()
    assert "GETTING_STARTED.md" in text
```

- [ ] **Step 2: Run the new contracts and confirm failure**

Run: `python3 -m pytest -q tests/test_public_docs.py tests/test_distribution_boundary.py::test_friend_lab_is_advanced_not_standard_installation`

Expected: FAIL because the two new docs and Friend Lab audience section are absent.

- [ ] **Step 3: Create the architecture document**

Use these headings:

```markdown
# Architecture
## One gateway, three adoption routes
## End-to-end flow
## Distribution and write boundaries
## Identity versus authority
## Data and privacy
## Ecosystem position
## Limits
```

Include the exact one-line pipeline from the test. Explain that the core owns
pure task-card, drift, and Intent Lock decisions; the adapter only maps local
Codex/Claude lifecycle events and privacy-minimized state; the human/host owns
authority and execution. Preserve the factual independently-adoptable links
from current `origin/main` to `workflow-governance-model`, `mothership-router`,
and `mothership`, without claiming that Frontdoor installs or invokes them.
Defer the architecture-image link until Task 7 creates the asset.

- [ ] **Step 4: Create the troubleshooting document**

Cover unreadable JSON, invalid cards, drift, `UNKNOWN`/`BLOCKING`, invalid hook
state permissions, silent same-intent adapter output, opaque Codex results,
Windows adapter rejection, missing offline wheels, and paths outside hook
coverage. Every recovery must stop, report, inspect, or return to the human; it
must not propose a retry, adjacent subsystem, settings overwrite, or authority
promotion. Link to existing canonical docs with distribution-safe targets.

- [ ] **Step 5: Add the Friend Lab audience block without renumbering phases**

Immediately after the opening boundary paragraph, add `## Audience and
prerequisites`, call it an advanced offline receiver workflow and not the
standard installation path, link to `GETTING_STARTED.md` and `EVIDENCE.md`, and
retain all three out-of-band digest prerequisites. Do not reorder or rename the
11 phase headings.

- [ ] **Step 6: Run the focused public-doc and Friend Lab tests**

Run: `python3 -m pytest -q tests/test_public_docs.py tests/test_distribution_boundary.py tests/friend_lab`

Expected: PASS.

- [ ] **Step 7: Commit the architecture/recovery unit**

```bash
git add docs/ARCHITECTURE.md docs/TROUBLESHOOTING.md docs/FRIEND_LAB.md tests/test_public_docs.py tests/test_distribution_boundary.py
git commit -m "docs: define gateway architecture and recovery"
```

---

### Task 5: Convert Intent Lock and the Adapter into Public Operational Guides

**Files:**
- Modify: `docs/INTENT_LOCK.md:1-24,185-197`
- Modify: `adapters/README.md:1-155`
- Modify: `tests/test_public_docs.py`
- Modify: `tests/test_hook_fixtures.py`

**Interfaces:**
- Consumes: `intent-lock.v1`, the tested hook CLI stdin/stdout contract, existing failure-sequence fixtures, and troubleshooting routes.
- Produces: a public reference without internal incident labels and a verified non-live adapter smoke sequence.

- [ ] **Step 1: Add the failing public-reference assertions**

```python
INTENT_LOCK = ROOT / "docs" / "INTENT_LOCK.md"
INTENT_LOCK_SCHEMA = ROOT / "src" / "frontdoor" / "schema" / "intent-lock.v1.json"
ADAPTER_README = ROOT / "adapters" / "README.md"


def test_intent_lock_reference_has_no_internal_labels() -> None:
    text = INTENT_LOCK.read_text(encoding="utf-8")
    schema = json.loads(INTENT_LOCK_SCHEMA.read_text(encoding="utf-8"))
    assert text.startswith("# Intent Lock Reference\n")
    for phase in schema["properties"]["phase"]["enum"]:
        assert f"`{phase}`" in text
    for mode in schema["properties"]["mode"]["enum"]:
        assert f"`{mode}`" in text
    for internal in (
        "CODEX_SELF_CONFIDENT_ADOPTED",
        "REPEATED_EXCESSIVE_DERAILMENT",
        "COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT",
        "CC_UNAUDITED",
        "implementation requested by the human",
    ):
        assert internal not in text
    assert "No independent security audit has been completed" in text


def test_adapter_readme_requires_smoke_before_activation() -> None:
    text = ADAPTER_README.read_text(encoding="utf-8")
    ordered = (
        "## Install in an isolated environment",
        "## Non-live smoke test",
        "## Codex example",
        "## Claude Code example",
        "## Uninstall or deactivate",
    )
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)
    for marker in (
        "--state-dir", "UserPromptSubmit", "PreToolUse",
        "permissionDecision", "INTENT_LOCK_REPORT_REQUIRED",
        "does not modify operator-owned settings",
        "mode `0700`", "mode `0600`", "Windows is rejected",
    ):
        assert marker in text
```

- [ ] **Step 2: Add a failing executable test for the documented Codex sequence**

In `tests/test_hook_fixtures.py`, isolate the Markdown between
`## Non-live smoke test` and `## Codex example`, extract exactly six single-line
JSON objects from the documented `printf '%s\n' '{...}'` pipelines, parse them,
and replay them through `_run_hook` with one `tmp_path`. Assert this sequence:

```python
assert [payload["hook_event_name"] for payload in payloads] == [
    "UserPromptSubmit",
    "PreToolUse",
    "PreToolUse",
    "PostToolUse",
    "PreToolUse",
    "SessionEnd",
]
assert all(result.returncode == 0 for result in results)
assert "INTENT_LOCK_ACTIVE" in results[0].stdout
assert '"permissionDecision": "deny"' in results[1].stdout
assert results[2].stdout == ""
assert "INTENT_LOCK_REPORT_REQUIRED" in results[3].stdout
assert '"permissionDecision": "deny"' in results[4].stdout
assert results[5].stdout == ""
assert load_session_lock(tmp_path, "adapter-smoke-codex") is None
```

- [ ] **Step 3: Run the new tests and confirm stale docs fail**

Run: `python3 -m pytest -q tests/test_public_docs.py::test_intent_lock_reference_has_no_internal_labels tests/test_public_docs.py::test_adapter_readme_requires_smoke_before_activation tests/test_hook_fixtures.py`

Expected: FAIL on the old title/internal labels and missing smoke section.

- [ ] **Step 4: Rewrite the Intent Lock opening and closeout as public reference**

Replace the date/status/incident-label block with a generic failure model and
retain the deterministic derivation, state machine, adapter boundary, privacy,
and platform-limit details. Link to `ARCHITECTURE.md`, `EVIDENCE.md`,
`TROUBLESHOOTING.md`, and the absolute GitHub adapter guide. End with the exact
disclosure `No independent security audit has been completed.` Preserve the
official Codex and Claude hook references but phrase current payload behavior as
adapter assumptions that must be checked before activation.

- [ ] **Step 5: Add the exact non-live adapter smoke path**

Use an explicit disposable state directory:

```bash
adapter_state_dir="$(mktemp -d)"
chmod 700 "$adapter_state_dir"
hook_bin=".venv/bin/agent-frontdoor-hook"
test -x "$hook_bin"
```

Document six one-object stdin invocations using the tested payloads:

1. `UserPromptSubmit` creates the `cloudflare-api` literal-target lock.
2. `PreToolUse` for `npx wrangler whoami` returns a deny decision.
3. Matching `codex mcp login cloudflare-api` returns empty stdout.
4. Status-less Codex `PostToolUse` returns `INTENT_LOCK_REPORT_REQUIRED`.
5. A later `rg cloudflare-api .` call is denied pending a human report.
6. `SessionEnd` removes only the synthetic session state.

Explain that each deny still exits `0`, silence means same intent rather than
authority, the outer `fixtures/intent-lock/*_sequence.json` wrappers are not
valid one-shot stdin, and the procedure never modifies live settings or runs
any `tool_input.command`. Include optional privacy inspection for raw session,
prompt, command, and tool-use strings. Leave physical deletion of the disposable
directory as a separate operator decision.

- [ ] **Step 6: Remove the stale adapter audit block and consolidate duplication**

Replace `## Audit status` with the ordinary no-independent-audit disclosure.
Keep install, platform requirements, state/privacy, Codex/Claude config review,
and uninstall. Summarize Intent Lock semantics and link to the canonical
reference instead of duplicating the full state machine. Change `matching 0.2
release line` to `matching unreleased 0.2 source line`.

- [ ] **Step 7: Run adapter and public-doc verification**

Run: `python3 -m pytest -q tests/test_public_docs.py tests/test_hook_fixtures.py tests/test_hook_adapter.py tests/test_hook_state.py tests/test_adapter_safety.py`

Expected: PASS.

- [ ] **Step 8: Commit the operational-guide unit**

```bash
git add docs/INTENT_LOCK.md adapters/README.md tests/test_public_docs.py tests/test_hook_fixtures.py
git commit -m "docs: add safe adapter evaluation path"
```

---

### Task 6: Complete the Community and Maintainer Surface

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SUPPORT.md`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/feature.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/pull_request_template.md`
- Create: `tests/test_community_files.py`

**Interfaces:**
- Consumes: existing GitHub labels `bug`, `enhancement`, and `question`; source install/test commands; private-reporting URL; public safety boundaries.
- Produces: locally complete community files and forms. They become active only after a separately authorized default-branch merge.

- [ ] **Step 1: Add standard-library-only failing community tests**

Create `tests/test_community_files.py` with:

```python
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
```

Write all three `.yml` files in JSON syntax, which is valid YAML 1.2, so the
standard-library `json.loads` checks above validate complete syntax and nested
structure without expanding the offline `[test]` wheelhouse. Require:

- bug IDs: `area`, `revision`, `environment`, `reproduction`, `expected`,
  `actual`, `logs`, `checks`;
- feature IDs: `area`, `problem`, `proposal`, `alternatives`, `boundaries`,
  `evidence`, `checks`.

The bug form uses label `bug`, the feature form uses `enhancement`, and
`config.yml` has `blank_issues_enabled: true` plus the exact private-report and
support URLs. A syntax error, duplicate JSON key, wrong container type, or
missing nested object must fail locally before GitHub sees the form.

- [ ] **Step 2: Run the community tests and confirm the eight files are absent**

Run: `python3 -m pytest -q tests/test_community_files.py`

Expected: FAIL on missing files.

- [ ] **Step 3: Write the four community guides**

`CONTRIBUTING.md` headings:

```markdown
# Contributing
## Before you start
## Trust boundaries
## Source setup
## Test-first workflow
## Focused verification
## Full verification
## Documentation and packaging checks
## Pull requests
```

Use the real clone URL and source install. List focused commands for core,
adapter, docs/examples, and full `python3 -m pytest -q`. Require no live hook
activation and route security/conduct reports away from ordinary issues.

`SECURITY.md` must say there is no published release, define the unreleased core
and optional adapter scope, distinguish task identity from authorization, state
that hooks are not a security boundary, link only to the private report form,
request redacted reproduction/impact/commit data, and promise no response SLA.

`CODE_OF_CONDUCT.md` uses the Contributor Covenant 2.1 text from
`https://www.contributor-covenant.org/version/2/1/code_of_conduct/`, including
its CC BY 4.0 attribution. Replace its contact placeholder with GitHub's
documented abuse-reporting route and transparently state that GitHub handles
that report; the project advertises no separate private conduct inbox. Do not
repurpose the security-advisory form for non-security conduct reports.

`SUPPORT.md` separates usage questions, reproducible bugs, feature/design
proposals, and confidential vulnerabilities. Discussions are disabled: route a
question to a blank issue, a bug to `?template=bug.yml`, a proposal to
`?template=feature.yml`, and vulnerabilities to the private report URL.

- [ ] **Step 4: Write focused GitHub issue forms and configuration**

The bug form requests area, exact revision, Python/OS, minimal reproduction,
expected and actual behavior, optional redacted logs, and acknowledgments for
issue search, secret removal, security rerouting, and the Code of Conduct.

The feature form requests area, problem, bounded proposal, alternatives,
evidence, and explicit impact on core execution/network/source-write
boundaries, adapter state, human gates, and hook activation.

Use this exact JSON-compatible YAML chooser configuration:

```json
{
  "blank_issues_enabled": true,
  "contact_links": [
    {
      "name": "Confidential security report",
      "url": "https://github.com/UMEBOSHIISAN/agent-frontdoor/security/advisories/new",
      "about": "Report suspected vulnerabilities privately; do not open a public issue."
    },
    {
      "name": "Support and usage routes",
      "url": "https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/SUPPORT.md",
      "about": "Choose the appropriate support route before opening an issue."
    }
  ]
}
```

The PR template headings are Summary, Scope, Verification, Safety boundary,
Documentation and packaging, Release truth, and Related issue. Its checklist
must cover focused/full tests, private-data scan, docs/examples, manifests, and
no release/activation implication.

- [ ] **Step 5: Run community and existing metadata tests**

Run: `python3 -m pytest -q tests/test_community_files.py tests/test_distribution_boundary.py`

Expected: PASS.

- [ ] **Step 6: Commit the community unit**

```bash
git add CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md SUPPORT.md .github tests/test_community_files.py
git commit -m "docs: complete community contribution surface"
```

---

### Task 7: Build and Inspect the Visual System

**Files:**
- Create: `assets/agent-frontdoor-hero.svg`
- Create: `assets/agent-frontdoor-architecture.svg`
- Create: `assets/agent-frontdoor-social-preview.png`
- Create: `tests/test_visual_assets.py`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: existing logo palette and the exact architecture flow from Task 4.
- Produces: the deterministic image paths consumed by the root README and GitHub social-preview publication.

- [ ] **Step 1: Write failing standard-library asset tests**

```python
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_social_preview_has_exact_github_dimensions_and_budget() -> None:
    path = ASSETS / "agent-frontdoor-social-preview.png"
    assert _png_dimensions(path) == (1280, 640)
    assert path.stat().st_size < 1_000_000


def test_architecture_svg_is_accessible_static_and_exact() -> None:
    path = ASSETS / "agent-frontdoor-architecture.svg"
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.attrib["role"] == "img"
    label_ids = root.attrib["aria-labelledby"].split()
    nodes_by_id = {
        node.attrib["id"]: node
        for node in root.iter()
        if node.attrib.get("id")
    }
    assert label_ids
    assert set(label_ids) <= set(nodes_by_id)
    for label_id in label_ids:
        node = nodes_by_id[label_id]
        assert node.tag.endswith(("title", "desc"))
        assert "".join(node.itertext()).strip()
    for node in root.iter():
        for name, value in node.attrib.items():
            if name.endswith("href"):
                assert value.startswith("#"), (name, value)
    for marker in (
        "Task Card", "Validation", "Drift Detection", "Intent Lock",
        "Human Gate", "Safe Handoff", "Read-only core",
        "Optional adapter", "Human authority remains external",
    ):
        assert marker in text
    for forbidden in ("<script", "<foreignObject", "<animate"):
        assert forbidden not in text
```

Add equivalent accessibility/static checks for `agent-frontdoor-hero.svg`, and
assert `docs/ARCHITECTURE.md` embeds `../assets/agent-frontdoor-architecture.svg`
with nonempty alt text.

- [ ] **Step 2: Run the visual contract and confirm the assets are absent**

Run: `python3 -m pytest -q tests/test_visual_assets.py`

Expected: FAIL on missing assets.

- [ ] **Step 3: Generate one polished illustrative candidate with image generation**

Use the image-generation tool with this production prompt:

```text
Use case: stylized-concept
Asset type: GitHub repository social preview, exact 2:1 composition
Primary request: a restrained infrastructure illustration of one bounded task path passing through a clear review gateway before reaching an AI coding agent
Scene/background: deep navy technical space with subtle grid and layered doorway geometry
Subject: one indigo input path, a crisp green human-review gate, and contained output; no robots or people
Style/medium: premium flat vector-inspired editorial illustration, serious developer infrastructure, minimal
Composition/framing: 1280 x 640 landscape, strong safe margins, gateway centered-right, clean negative space left
Lighting/mood: calm, trustworthy, precise
Color palette: #0b1020, #111827, indigo, restrained emerald green, off-white
Text (verbatim): "Agent Frontdoor"
Constraints: exact product spelling; one constrained path; no claims, metrics, logos, code, badges, watermark, character art, or external brand marks
Avoid: neon cyberpunk, stock AI imagery, shields, locks, mascots, lens flare, clutter, gradients that reduce text legibility
```

Keep the candidate outside the accepted asset path until inspection. Use no
more than the two attempts defined in Global Constraints. If image generation
cannot preserve exact text and 2:1 composition after the second attempt, use
its illustration only as a visual reference and create the final social preview
as a deterministic 1280x640 vector composition rendered to PNG.

- [ ] **Step 4: Create deterministic hero and architecture SVGs**

Both use the existing navy/indigo/green palette, `role="img"`, `aria-labelledby`,
nonempty `title` and `desc`, no animation, no external resources, no script, and
no `foreignObject`. The hero says `Agent Frontdoor` and visually represents the
whole gateway. The architecture diagram contains the exact tested labels,
visually encloses Task Card through Intent Lock in the read-only core, shows the
optional adapter as a separate state-writing boundary, and leaves Human Gate
and Safe Handoff under external human/host authority.

- [ ] **Step 5: Inspect every final image manually**

Use image viewing for the PNG and rendered previews of both SVGs. Verify exact
product spelling, legibility at thumbnail scale, truthful arrows, clear
core/adapter/human separation, contrast, no excluded brand IP, and no misleading
security symbolism. Record any second image-generation attempt in commentary
under the retry contract.

- [ ] **Step 6: Run visual tests**

Run: `python3 -m pytest -q tests/test_visual_assets.py tests/test_public_docs.py`

Expected: PASS.

- [ ] **Step 7: Commit the visual unit**

```bash
git add assets/agent-frontdoor-hero.svg assets/agent-frontdoor-architecture.svg assets/agent-frontdoor-social-preview.png docs/ARCHITECTURE.md tests/test_visual_assets.py
git commit -m "docs: add integrated gateway visuals"
```

---

### Task 8: Close Package Metadata, Release Truth, and Distribution Boundaries

**Files:**
- Modify: `pyproject.toml:1-27`
- Modify: `adapters/pyproject.toml:1-24`
- Modify: `CHANGELOG.md:1-34`
- Modify: `MANIFEST.in:1-15`
- Create: `adapters/MANIFEST.in`
- Modify: `tests/test_distribution_boundary.py`

**Interfaces:**
- Consumes: every public doc/community/example/asset created in Tasks 1-7.
- Produces: verified PEP 621 discovery metadata and two clean, separately inspectable source distributions.

- [ ] **Step 1: Add failing metadata and release-truth tests**

Parse both TOML files through the already required setuptools build backend,
without adding a test dependency or expanding the offline wheelhouse:

```python
from setuptools.config.pyprojecttoml import read_configuration

core = read_configuration(PYPROJECT, expand=False)
adapter = read_configuration(ADAPTER_PYPROJECT, expand=False)
```

Assert:

```python
assert core["project"]["description"] == (
    "Read-only preflight gateway for bounded AI coding-agent tasks and drift detection"
)
assert core["project"]["license-files"] == ["LICENSE"]
assert core["project"]["urls"] == {
    "Homepage": "https://github.com/UMEBOSHIISAN/agent-frontdoor",
    "Documentation": "https://github.com/UMEBOSHIISAN/agent-frontdoor/tree/main/docs",
    "Source": "https://github.com/UMEBOSHIISAN/agent-frontdoor",
    "Issues": "https://github.com/UMEBOSHIISAN/agent-frontdoor/issues",
    "Changelog": "https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/CHANGELOG.md",
    "Security": "https://github.com/UMEBOSHIISAN/agent-frontdoor/security/policy",
}
assert adapter["project"]["description"] == (
    "Optional local Codex and Claude Code hooks for Agent Frontdoor Intent Lock"
)
assert adapter["project"]["dependencies"] == ["agent-frontdoor>=0.2.0,<0.3"]
```

Require core keywords `ai-agents`, `developer-tools`, `drift-detection`, and
`task-validation`; adapter keywords `ai-agents`, `claude-code`, `codex`, and
`intent-lock`. Add no platform or Python-minor classifiers.

Release tests require `## Unreleased`, `### Planned 0.2.0`, and a never-tagged
0.1 development-history subsection. Reject a version-level `## 0.x` release
heading, PyPI URL, release date, or statement that 0.2 is published.

- [ ] **Step 2: Add failing clean-sdist behavior tests**

In a `tmp_path` sanitized copy excluding `.git`, worktrees, `build`, `dist`,
caches, and every `*.egg-info`, invoke `setuptools.build_meta.build_sdist` in a
subprocess. Inspect tar members without extraction.

Core requirements:

- README, license, changelog, four community files, four GitHub templates;
- seven canonical docs, public examples, all final assets, fixtures, schemas,
  core source, and archive verifier;
- no `adapters/`, `docs/superpowers/`, `tools/friend_lab/`,
  `tests/friend_lab/`, hook source, or four adapter tests.

Adapter requirements:

- adapter README, license, pyproject, three hook source files, and two inert JSON
  configuration examples;
- no root core source, fixtures, schemas, root docs, tests, tools, or community
  files.

Resolve every relative Markdown link and HTML `src`/`href` against members of
its own archive. Absolute `https://github.com/...` links are skipped. Never
extract either archive during the test.

- [ ] **Step 3: Run the new tests and confirm metadata/manifest failures**

Run: `python3 -m pytest -q tests/test_distribution_boundary.py`

Expected: FAIL on missing URLs, release truth, public manifest entries, and clean-sdist closure.

- [ ] **Step 4: Update exact package metadata**

Keep both versions at `0.2.0`, both licenses MIT, core build backend
`setuptools>=77`, Python `>=3.10`, core runtime dependency only
`jsonschema>=4`, adapter dependency exactly `agent-frontdoor>=0.2.0,<0.3`, and
the existing two scripts. Add the descriptions, keywords, license-files, and
project URLs asserted above. Adapter documentation points to `/tree/main/adapters`.

- [ ] **Step 5: Make release state truthful**

Keep every 0.2 change and earlier 0.1 candidate fact under `## Unreleased`.
Use `### Planned 0.2.0` and `### Earlier 0.1 development candidate`; explicitly
state that no Git tag or GitHub release represents either subsection. Preserve
the statement that adapter installation does not activate local settings.

- [ ] **Step 6: Apply explicit public allowlists**

Use this root manifest:

```text
include .gitattributes
include CHANGELOG.md
include CODE_OF_CONDUCT.md
include CONTRIBUTING.md
include LICENSE
include README.md
include SECURITY.md
include SUPPORT.md
include .github/ISSUE_TEMPLATE/bug.yml
include .github/ISSUE_TEMPLATE/config.yml
include .github/ISSUE_TEMPLATE/feature.yml
include .github/pull_request_template.md
recursive-include assets *.png *.svg
include docs/ARCHITECTURE.md
include docs/CORE_REFERENCE.md
include docs/EVIDENCE.md
include docs/FRIEND_LAB.md
include docs/GETTING_STARTED.md
include docs/INTENT_LOCK.md
include docs/TROUBLESHOOTING.md
recursive-include examples *.json *.md *.py
recursive-include fixtures *.json
recursive-include schemas *.json
include tools/verify_handoff_archive.py
prune adapters
prune docs/superpowers
prune tests/friend_lab
prune tools/friend_lab
exclude tests/test_adapter_safety.py
exclude tests/test_hook_adapter.py
exclude tests/test_hook_fixtures.py
exclude tests/test_hook_state.py
```

Create `adapters/MANIFEST.in` containing only its README, license, and
`recursive-include examples *.json`; setuptools continues to discover the hook
package from `src`.

- [ ] **Step 7: Run distribution, privacy, and source-boundary tests**

Run: `python3 -m pytest -q tests/test_distribution_boundary.py tests/test_handoff_archive.py tests/test_adapter_safety.py tests/test_no_execution_paths.py`

Expected: PASS with both clean sdists closed and separate.

- [ ] **Step 8: Commit the packaging unit**

```bash
git add pyproject.toml adapters/pyproject.toml CHANGELOG.md MANIFEST.in adapters/MANIFEST.in tests/test_distribution_boundary.py
git commit -m "build: close public distribution metadata"
```

---

### Task 9: Rewrite the Root README as the Integrated Launch Surface

**Files:**
- Modify: `README.md:1-368`
- Modify: `tests/test_readme.py:1-251`
- Modify: `tests/test_public_docs.py`
- Delete: `assets/agent-frontdoor-pulse.svg`

**Interfaces:**
- Consumes: every canonical doc, example, community file, metadata statement, metric label, and visual asset from Tasks 1-8.
- Produces: the final public reader journey and distribution-safe link graph.

- [ ] **Step 1: Replace the old root-forcing tests with a failing landing-page contract**

Keep the legacy-schema and stale-full-test-count negative assertions. Replace
the exact first-three-lines and Intent-Lock-first order tests with:

```python
def test_readme_presents_integrated_adoption_journey() -> None:
    text = _text()
    ordered = (
        "# Agent Frontdoor",
        "Stop AI coding agents from drifting beyond the task you approved.",
        "## See the boundary",
        "## Quick start",
        "## Choose a route",
        "## Evidence at a glance",
        "## Safety and limits",
        "## Documentation",
        "## Project status",
    )
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)
    for marker in (
        "https://github.com/UMEBOSHIISAN/agent-frontdoor.git",
        "examples/task-card.json",
        "VALID example-readme-audit",
        "Core CLI",
        "Intent Lock API",
        "Optional hooks",
    ):
        assert marker in text


def test_readme_preserves_truthful_safety_and_unreleased_status() -> None:
    text = _text()
    normalized = " ".join(text.split())
    for marker in (
        "This is not an agent runtime.",
        "This is not an autonomous router.",
        "does not execute commands",
        "does not grant authority",
        "core is read-only",
        "not a security boundary",
        "Unreleased source preview",
        "No independent security audit has been completed",
    ):
        assert marker in normalized
    for stale in (
        "<PUBLIC_REPOSITORY_URL>",
        "CODEX_SELF_CONFIDENT_ADOPTED",
        "REPEATED_EXCESSIVE_DERAILMENT",
        "COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT",
        "CC_UNAUDITED",
        "public CLI and exit codes are stable",
        "img.shields.io",
    ):
        assert stale not in text


def test_readme_uses_integrated_accessible_visuals() -> None:
    text = _text()
    assert 'src="assets/agent-frontdoor-hero.svg"' in text
    assert 'src="assets/agent-frontdoor-architecture.svg"' in text
    assert "agent-frontdoor-pulse" not in text
```

Add route assertions for all seven canonical docs, examples index, absolute
adapter guide, four community files, license, and changelog. Add a progressive
disclosure assertion that the root no longer owns headings for the 14-field
schema, full gate list, full drift list, fixture manual, or offline procedure.

- [ ] **Step 2: Add a failing public-link resolver**

Enumerate only the intended public Markdown files; do not glob
`docs/superpowers/**`. Parse Markdown links/images and HTML `src`/`href`, ignore
absolute URLs and anchors, reject targets escaping the repository, and require
every local target to exist. Also require every local README image to have
nonempty alt text. The new landing-page and integrated-visual tests provide the
intentional red state even if every old README link still resolves.

- [ ] **Step 3: Run the new landing-page tests and confirm failure**

Run: `python3 -m pytest -q tests/test_readme.py tests/test_public_docs.py tests/test_examples.py tests/test_visual_assets.py`

Expected: FAIL on the old README order/content.

- [ ] **Step 4: Rewrite the README in the approved order**

Use these sections:

```markdown
# Agent Frontdoor
## See the boundary
## How the gateway works
## Quick start
## Choose a route
## Evidence at a glance
## Safety and limits
## Ecosystem
## Documentation
## Project status
## License
```

Start with the logo, integrated hero, exact English promise, and concise
Japanese summary. Keep the two original non-goal sentences verbatim immediately
below the hero instead of before the product name. Show the Cloudflare adjacent
action as evaluated/denied text only, not as an executed command.

Quick start uses the public clone URL, `.venv`, source install without the test
extra, `examples/task-card.json`, and expected `VALID example-readme-audit`.
The three-route table links Core CLI to `CORE_REFERENCE`, Intent Lock API to the
runnable script/reference, and Optional hooks to the absolute GitHub adapter
guide with a non-activation warning.

The evidence table contains exactly the five stable scoped signals from Global
Constraints and links to `docs/EVIDENCE.md`; no full-suite count appears in the
README. Preserve `origin/main`'s concrete valid/invalid/drift intuition and
ecosystem links, but keep the long console/reference details in canonical docs.

Status must say `Unreleased source preview`, no tag/release/PyPI package exists,
and no independent security audit has been completed. Remove every static shield
badge and unsupported stability claim.

- [ ] **Step 5: Remove the obsolete pulse asset explicitly**

After confirming
`rg -n "agent-frontdoor-pulse" README.md docs/*.md examples/README.md adapters/README.md`
finds no public reference, delete only `assets/agent-frontdoor-pulse.svg` with
an explicit patch. Retain the existing logo and all three new assets.

- [ ] **Step 6: Run landing-page, link, example, visual, and packaging tests**

Run: `python3 -m pytest -q tests/test_readme.py tests/test_public_docs.py tests/test_examples.py tests/test_visual_assets.py tests/test_distribution_boundary.py`

Expected: PASS.

- [ ] **Step 7: Commit the integrated README unit**

```bash
git add README.md assets/agent-frontdoor-pulse.svg tests/test_readme.py tests/test_public_docs.py
git commit -m "docs: present integrated agent safety gateway"
```

---

### Task 10: Reconcile Main and Verify the Complete Local Tree

**Files:**
- Modify on merge only if conflicted: `README.md`, `pyproject.toml`

**Interfaces:**
- Consumes: final local public surface, the Task 0 remote audit, and all test suites.
- Produces: a main-integrated, public-safe, fully reviewed branch ready for gated cleanup and publication. The active implementation plan remains tracked until publication prerequisites exist.

- [ ] **Step 1: Verify the branch is clean and refresh remote main read-only**

Run:

```bash
git status --short --branch
git fetch origin main
git log --left-right --cherry-pick --oneline origin/main...HEAD
```

Expected planning baseline: `origin/main` contains `d75a006`. Compare this result
with the Task 0 audit. If a newer commit appeared after Task 0, inspect every new
commit and refresh this integration step before merging; do not silently absorb
an unknown runtime, policy, release, or automation change.

- [ ] **Step 2: Merge current main without rewriting feature history**

Run: `git merge --no-ff --no-commit origin/main`

Expected on the planning baseline: conflicts may occur in `README.md` and
`pyproject.toml`. Resolve them only with explicit patches. Preserve the final
Task 9 README, version `0.2.0`, `setuptools>=77`, SPDX MIT metadata, full root
pytest path, project URLs, and adapter source path. Do not use checkout/reset to
discard either side. Confirm `git diff --check` and no conflict markers, then:

```bash
git add README.md pyproject.toml
git commit -m "merge: reconcile current public main"
```

If the merge applies without conflict, stage only the actual merge result and
use the same commit message.

- [ ] **Step 3: Run all focused suites and the complete suite**

Run:

```bash
python3 -m pytest -q tests/test_readme.py tests/test_public_docs.py tests/test_examples.py tests/test_visual_assets.py tests/test_community_files.py tests/test_distribution_boundary.py tests/test_fixture_metrics.py tests/test_no_execution_paths.py tests/test_hook_fixtures.py tests/test_hook_adapter.py tests/test_hook_state.py tests/test_adapter_safety.py
python3 -m pytest -q
git diff --check
```

Expected: every command PASS. Record the fresh full-suite count in the handoff,
not as a timeless README badge.

- [ ] **Step 4: Run privacy, internal-label, and unsupported-claim scans**

Use `rg` to scan tracked public files for private home paths, email addresses,
credential/token prefixes, old internal labels, release/PyPI claims, broken
placeholders and live settings mutation language. Internal planning files are
still intentionally present at this step; confirm that public docs and package
manifests neither link to nor include them. Review every other match rather than
trusting count zero blindly.

- [ ] **Step 5: Obtain independent review while the active plan remains available**

Invoke `superpowers:requesting-code-review` for the complete branch, run Codex
review as required by project policy, address all Critical/Important findings,
commit each resulting test-first correction with a scoped message, rerun affected
focused tests and the full suite, then invoke
`superpowers:verification-before-completion` and verify a clean worktree.

---

### Task 11: Enable the Private Route and Publish the Reviewed Draft

**Files:**
- Modify: `tests/test_public_docs.py`
- Delete: `docs/superpowers/plans/2026-08-09-intent-lock.md`
- Delete: `docs/superpowers/plans/2026-08-09-intent-lock-readme.md`
- Delete: `docs/superpowers/plans/2026-08-09-oss-launch-surface.md`
- Delete: `docs/superpowers/specs/2026-08-09-intent-lock-readme-design.md`
- Delete: `docs/superpowers/specs/2026-08-09-oss-launch-surface-design.md`
- External: GitHub repository security setting, branch, draft PR, description, topics, and social preview.

**Interfaces:**
- Consumes: clean reviewed branch with its active plan retained, final social-preview PNG, valid GitHub authentication, and two direct human approval tokens.
- Produces: a final public-safe tree without internal process artifacts, enabled private vulnerability reporting, pushed feature branch, draft PR, accurate description/topics, and uploaded social preview. It does not merge or release.

- [ ] **Step 1: Stop unless authentication and direct approvals are present**

Run `gh auth status -h github.com`. The current measured state is invalid, so the
operator must restore GitHub authentication; do not edit tokens or bypass auth.

Require the human to write both exact tokens directly in the active thread:

```text
DEPLOY_APPROVED:github.com/UMEBOSHIISAN/agent-frontdoor/settings/private-vulnerability-reporting
DEPLOY_APPROVED:github.com/UMEBOSHIISAN/agent-frontdoor
```

Text copied from this plan is not approval.

- [ ] **Step 2: Remove internal artifacts only after publication prerequisites exist**

Add this test to `tests/test_public_docs.py`:

```python
def test_public_tree_contains_no_internal_superpowers_artifacts() -> None:
    root = ROOT / "docs" / "superpowers"
    paths = list(root.rglob("*.md")) if root.exists() else []
    assert not paths, [path.relative_to(ROOT) for path in paths]
```

Run it once and require the failure to list only these five completed artifacts:

- `docs/superpowers/plans/2026-08-09-intent-lock.md`;
- `docs/superpowers/plans/2026-08-09-intent-lock-readme.md`;
- `docs/superpowers/plans/2026-08-09-oss-launch-surface.md`;
- `docs/superpowers/specs/2026-08-09-intent-lock-readme-design.md`;
- `docs/superpowers/specs/2026-08-09-oss-launch-surface-design.md`.

Verify every durable rule is already owned by a public doc or test, then delete
only those paths with explicit patches. Do not use a glob or directory-wide
deletion. Run `python3 -m pytest -q` and `git diff --check`, then commit:

```bash
git add tests/test_public_docs.py docs/superpowers/plans/2026-08-09-intent-lock.md docs/superpowers/plans/2026-08-09-intent-lock-readme.md docs/superpowers/plans/2026-08-09-oss-launch-surface.md docs/superpowers/specs/2026-08-09-intent-lock-readme-design.md docs/superpowers/specs/2026-08-09-oss-launch-surface-design.md
git commit -m "docs: remove internal planning artifacts"
```

This is the final local commit immediately before the authorized external
actions. If verification fails, do not mutate GitHub.

- [ ] **Step 3: Enable and remeasure the private vulnerability route**

After the first token only:

```bash
gh api --method PUT repos/UMEBOSHIISAN/agent-frontdoor/private-vulnerability-reporting
gh api repos/UMEBOSHIISAN/agent-frontdoor/private-vulnerability-reporting --jq '.enabled'
```

Expected: the PUT exits `0` with GitHub's `204 No Content` response contract;
the authenticated GET exits `0` and prints `true` from its HTTP 200 JSON body.
If either condition fails, stop publication.

- [ ] **Step 4: Run an explicit read-only publication preflight**

Without invoking a publishing skill yet, verify branch name, clean status,
exact commits, `git diff --stat origin/main...HEAD`, no secrets, all tests fresh,
and no tag/release/workflow/settings file in the diff. Confirm the second token
applies to this exact repository and only the reviewed
branch/draft/metadata/social-preview scope.

- [ ] **Step 5: Use `github:yeet` as the sole branch/PR publication step**

Invoke `github:yeet` once, configured to push only `feat/intent-lock`, target
`main`, and create a draft PR titled:

```text
Add Intent Lock and integrated Agent Frontdoor OSS surface
```

The PR body summarizes the integrated gateway, core/adapter boundary, metrics
with caveats, new examples/community/visuals, packaging closure, fresh test
count, no live activation, and no release. It must remain draft.
Do not run a separate `git push` or `gh pr create` before or after this skill.

- [ ] **Step 6: Set accurate repository discovery metadata**

Set this exact description:

```text
Stop AI coding agents from drifting beyond approved tasks with a fail-closed, read-only preflight gateway.
```

Set exactly these topics:

```text
agent-safety
ai-agents
claude-code
codex
developer-tools
drift-detection
python
task-validation
```

Upload `assets/agent-frontdoor-social-preview.png` through the authenticated
GitHub repository settings UI using the browser-control capability. Do not edit
any other setting.

- [ ] **Step 7: Measure remote persistence and report exclusions**

Verify:

- `origin/feat/intent-lock` resolves to the local HEAD;
- the PR is draft, targets `main`, and reports the same head OID;
- repository description and topic array match exactly;
- private vulnerability reporting still returns `enabled: true`;
- the uploaded social preview is visible in settings/share preview.

Do not claim Community Profile improvement because templates are not active on
the default branch until a separately authorized merge. Do not create a merge,
tag, release, package upload, CI workflow, deployment, or live hook activation.
