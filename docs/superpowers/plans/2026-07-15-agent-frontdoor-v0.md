# Agent Frontdoor v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the existing schema-only Agent Frontdoor as a locally installable, read-only preflight validator with four CLI commands, 60 task-card fixtures, drift detection, worker comparison evidence, and no execution path.

**Architecture:** A fixed JSON Schema defines the card surface. Pure Python modules validate, render, and compare local JSON documents; the CLI is a thin read-only adapter. Fixtures and tests are the executable safety contract, while local-worker outputs remain evaluation evidence rather than runtime dependencies.

**Tech Stack:** Python 3.10+, JSON Schema 2020-12, `jsonschema`, `pytest`, `setuptools`.

## Global Constraints

- Existing target `Workspace/oss_staging/agent-frontdoor/` must be inherited; do not redesign it or create another target.
- This is not an agent runtime, autonomous router, dispatcher, daemon, MCP server, hook, or execution engine.
- Core task classes are exactly `RESEARCH`, `DESIGN_REVIEW`, `IMPLEMENTATION`, `CODE_REVIEW`, `AUDIT`, `CONTENT_DRAFT`, `DATA_ANALYSIS`, `INSTALLATION`, `OPERATIONS`, `UNKNOWN`.
- Human gates are exactly `NONE`, `CONFIRM`, `BLOCKING`.
- Deploy, production, scheduler, secret, auth, billing, delete, destructive cleanup, SSOT mutation, external publish, and authority promotion always require `BLOCKING`.
- Core schema stores worker capabilities, never model or vendor names.
- No source code may invoke workers, tools, subprocesses, network services, schedulers, or task actions.
- Do not modify `Workspace/RAG/`, Obsidian, Temporal Knowledge OS, settings, hooks, production routing, routing ledger sources, worker registry sources, schedulers, deploy systems, or files outside the target.
- Do not deploy, push, publish, or create a remote.
- Use TDD: every production behavior starts with a focused failing test and recorded RED/GREEN evidence.

---

### Task 1: Local Package Skeleton and Intake Schema

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/frontdoor/__init__.py`
- Create: `schema/intake.v0.json`
- Create: `tests/test_intake_schema.py`
- Preserve: `schema/agent-frontdoor.v0.1.json`

**Interfaces:**
- Consumes: the approved core field, task-class, gate, and safety vocabularies.
- Produces: `schema/intake.v0.json`; importable `frontdoor`; console script declaration `agent-frontdoor = frontdoor.cli:main`.

- [ ] **Step 1: Write the schema contract test**

```python
def test_intake_schema_has_exact_core_contract(schema):
    assert schema["properties"]["schema_version"]["const"] == "intake.v0"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == EXPECTED_CORE_FIELDS
    assert schema["properties"]["task_class"]["enum"] == EXPECTED_TASK_CLASSES
    assert schema["properties"]["human_gate"]["enum"] == ["NONE", "CONFIRM", "BLOCKING"]
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/pytest tests/test_intake_schema.py -q`

Expected: failure because `schema/intake.v0.json` does not exist.

- [ ] **Step 3: Add the minimal package and schema**

The schema must require the fourteen approved fields, use `additionalProperties: false`, require non-empty `request_id`, `human_request`, actions, and `next_safe_step`, and use these capability labels only:

```json
["research", "design-review", "implementation", "code-review", "audit", "content-draft", "data-analysis", "installation", "operations", "none-until-clarified"]
```

The risk-tag enum is limited to:

```json
["deploy", "production", "scheduler", "secret", "auth", "billing", "delete", "destructive_cleanup", "ssot_mutation", "external_publish", "authority_promotion", "cleanup_adjacent", "scope_drift", "unknown"]
```

`required_manifest` is either `null` or a non-empty human-readable string; `required_evidence`, `unknowns`, and `assumptions` are arrays of strings.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `.venv/bin/pytest tests/test_intake_schema.py -q`

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit the independently testable schema**

```bash
git add .gitignore pyproject.toml src/frontdoor/__init__.py schema/intake.v0.json tests/test_intake_schema.py
git commit -m "feat: define agent frontdoor v0 intake contract"
```

### Task 2: Fail-Closed Validator

**Files:**
- Create: `src/frontdoor/validator.py`
- Create: `tests/test_validator.py`

**Interfaces:**
- Consumes: `schema/intake.v0.json` and Python mappings.
- Produces: `ValidationIssue(code: str, message: str, path: str)`, `ValidationResult(valid: bool, issues: tuple[ValidationIssue, ...])`, `load_card(path)`, and `validate_card(card)`.

- [ ] **Step 1: Write failing tests for structure, blocking categories, unknown input, and conflicting boundaries**

```python
def test_deploy_request_without_blocking_gate_fails(valid_card):
    valid_card.update(human_request="Deploy to production", human_gate="NONE")
    result = validate_card(valid_card)
    assert not result.valid
    assert {issue.code for issue in result.issues} >= {"blocking_gate_required"}

def test_unknown_fails_closed(valid_card):
    valid_card.update(task_class="UNKNOWN", human_gate="CONFIRM")
    assert "unknown_requires_blocking" in {i.code for i in validate_card(valid_card).issues}

def test_model_name_is_not_a_capability(valid_card):
    valid_card["predicted_worker_capability"] = "qwen"
    assert not validate_card(valid_card).valid
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/pytest tests/test_validator.py -q`

Expected: import failure because `frontdoor.validator` does not exist.

- [ ] **Step 3: Implement the smallest pure validator**

Use `Draft202012Validator` for structural errors, then deterministic semantic checks:

1. any blocking risk tag requires `BLOCKING`;
2. case-insensitive unsafe request/action keywords require `BLOCKING`;
3. `UNKNOWN` requires `BLOCKING`, `none-until-clarified`, at least one unknown, and no mutation action;
4. the same normalized action cannot be both allowed and forbidden;
5. JSON/load failures return typed input errors and never fall back to permissive prose.

The module may read JSON and schema files. It must not write, execute, import worker tooling, or access the network.

- [ ] **Step 4: Run and verify GREEN**

Run: `.venv/bin/pytest tests/test_validator.py tests/test_intake_schema.py -q`

Expected: all validator and schema tests pass.

- [ ] **Step 5: Commit validator behavior**

```bash
git add src/frontdoor/validator.py tests/test_validator.py
git commit -m "feat: add fail-closed task card validation"
```

### Task 3: Boundary Drift Comparator

**Files:**
- Create: `src/frontdoor/boundary_drift.py`
- Create: `tests/test_boundary_drift.py`

**Interfaces:**
- Consumes: two already validated card mappings.
- Produces: `DriftFinding(code: str, message: str)`, `DriftReport(drifted: bool, findings: tuple[DriftFinding, ...])`, and `detect_boundary_drift(before, after)`.

- [ ] **Step 1: Write six failing transition tests and one safe-control test**

```python
@pytest.mark.parametrize("case,code", [
    ("audit_to_mutation", "audit_to_mutation"),
    ("design_to_implementation", "design_to_implementation"),
    ("install_to_architecture_migration", "install_to_architecture_migration"),
    ("draft_to_external_publish", "draft_to_external_publish"),
    ("proposal_to_authority_promotion", "proposal_to_authority_promotion"),
    ("bounded_files_to_broad_refactor", "bounded_files_to_broad_refactor"),
])
def test_required_drift_family(case, code, drift_cards):
    report = detect_boundary_drift(*drift_cards[case])
    assert report.drifted
    assert code in {finding.code for finding in report.findings}
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/pytest tests/test_boundary_drift.py -q`

Expected: import failure because `frontdoor.boundary_drift` does not exist.

- [ ] **Step 3: Implement named, deterministic heuristics**

Use task-class changes, risk-tag additions, normalized action text, `next_safe_step`, and explicit bounded/broad-scope phrases. Return every matching named finding. Never mutate either card.

- [ ] **Step 4: Run and verify GREEN**

Run: `.venv/bin/pytest tests/test_boundary_drift.py -q`

Expected: all seven transition/control tests pass.

- [ ] **Step 5: Commit comparator behavior**

```bash
git add src/frontdoor/boundary_drift.py tests/test_boundary_drift.py
git commit -m "feat: detect task boundary drift"
```

### Task 4: Human Formatter and Four-Command CLI

**Files:**
- Create: `src/frontdoor/formatter.py`
- Create: `src/frontdoor/cli.py`
- Create: `tests/test_formatter.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: validated cards and `DriftReport`.
- Produces: `format_card(card) -> str`, `format_explanation(card) -> str`, `build_parser()`, and `main(argv=None) -> int`.

- [ ] **Step 1: Write failing formatter and subprocess-free CLI tests**

```python
def test_card_output_is_deterministic(valid_card):
    valid_card["human_gate"] = "BLOCKING"
    valid_card["predicted_worker_capability"] = "none-until-clarified"
    output = format_card(valid_card)
    assert "Request: case-001" in output
    assert "Human gate: BLOCKING" in output

def test_validate_command_returns_zero_for_valid_card(tmp_path, capsys, valid_card):
    path = write_json_fixture(tmp_path, valid_card)
    assert main(["validate", str(path)]) == 0
    assert "VALID case-001" in capsys.readouterr().out
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/pytest tests/test_formatter.py tests/test_cli.py -q`

Expected: import failures for missing formatter and CLI modules.

- [ ] **Step 3: Implement deterministic text and exact exits**

Commands and exits:

- `validate`: `0` valid, `1` invalid, `2` unreadable input;
- `card` and `explain`: same validation behavior, print only on valid input;
- `check-drift`: `0` no drift, `3` drift, `1` invalid card, `2` unreadable input.

Use direct function calls in tests. Do not spawn the CLI from the CLI or add any task-action verb.

- [ ] **Step 4: Run and verify GREEN**

Run: `.venv/bin/pytest tests/test_formatter.py tests/test_cli.py -q`

Expected: all formatter and CLI tests pass.

- [ ] **Step 5: Commit formatter and CLI**

```bash
git add src/frontdoor/formatter.py src/frontdoor/cli.py tests/test_formatter.py tests/test_cli.py pyproject.toml
git commit -m "feat: add read-only agent frontdoor CLI"
```

### Task 5: Fixture Corpus and Hard Safety Metrics

**Files:**
- Create: `fixtures/positive/*.json` (at least 30)
- Create: `fixtures/negative/*.json` (at least 30)
- Create: `fixtures/drift/*.json` (20 labeled pairs)
- Create: `tests/test_fixture_metrics.py`
- Create: `tests/test_no_execution_paths.py`

**Interfaces:**
- Consumes: public validator and drift interfaces.
- Produces: deterministic measurements for schema validity, blocking recall, unknown fail-safe, drift recall, source safety, and requested category coverage.

- [ ] **Step 1: Write failing count, category, recall, and AST safety tests**

```python
def test_fixture_counts():
    assert len(list(POSITIVE.glob("*.json"))) >= 30
    assert len(list(NEGATIVE.glob("*.json"))) >= 30

def test_negative_blocking_recall_is_one():
    outcomes = [not validate_card(load(path)).valid for path in blocking_negative_paths()]
    assert sum(outcomes) / len(outcomes) == 1.0

def test_drift_recall_is_at_least_point_nine_five():
    outcomes = [detect_boundary_drift(*load_pair(path)).drifted for path in DRIFT.glob("*.json")]
    assert sum(outcomes) / len(outcomes) >= 0.95
```

- [ ] **Step 2: Run and verify RED**

Run: `.venv/bin/pytest tests/test_fixture_metrics.py tests/test_no_execution_paths.py -q`

Expected: fixture-count and coverage failures because the new corpus does not exist.

- [ ] **Step 3: Add exactly scoped fixture cases**

Cover every requested category at least twice and distribute remaining cases without adding task classes. Positive unsafe cards use `BLOCKING`; negative unsafe cards deliberately omit it. Drift fixtures include all six families plus safe controls. AST/source safety rejects imports or calls associated with subprocess, sockets, HTTP clients, worker launchers, file writes, `exec`, and `eval` under `src/frontdoor/`.

- [ ] **Step 4: Run and verify GREEN**

Run: `.venv/bin/pytest tests/test_fixture_metrics.py tests/test_no_execution_paths.py -q`

Expected: positive schema validity `1.00`, negative blocking recall `1.00`, drift recall `>=0.95`, and no forbidden source path findings.

- [ ] **Step 5: Run the complete suite and commit fixtures**

Run: `.venv/bin/pytest -q`

Expected: zero failures, including the inherited v0.1 tests.

```bash
git add fixtures/positive fixtures/negative fixtures/drift tests/test_fixture_metrics.py tests/test_no_execution_paths.py
git commit -m "test: add frontdoor safety fixture corpus"
```

### Task 6: README, Worker Comparison, and Audit Assets

**Files:**
- Modify: `README.md`
- Create: `docs/worker_eval_inputs.json`
- Create: `docs/worker_comparison_scorecard.yaml`
- Create: `docs/final_audit.md`
- Create: `docs/closeout_v0.md`

**Interfaces:**
- Consumes: verified CLI, fixture metrics, the same 20 labeled human requests, and read-only worker outputs.
- Produces: install/use documentation, mismatch-only worker evidence, independent audit, and factual closeout.

- [ ] **Step 1: Add a README contract test before editing README**

```python
def test_readme_starts_with_required_contract():
    lines = README.read_text().splitlines()
    assert lines[:3] == [
        "This is not an agent runtime.",
        "This is not an autonomous router.",
        "This is a preflight contract and validator for safely preparing tasks for AI workers.",
    ]
```

- [ ] **Step 2: Run and verify RED, then write README and verify GREEN**

Run before: `.venv/bin/pytest tests/test_readme.py -q`

Expected before: failure on the opening lines.

Run after: `.venv/bin/pytest tests/test_readme.py -q`

Expected after: pass, with local install and all four CLI examples documented.

- [ ] **Step 3: Run worker evaluations once per approved alias**

Use the home worker registry and explicit alias approval. Send the identical 20 requests to the approved Qwen and Gemma aliases. Do not retry. Record raw outputs under `docs/worker_outputs/`, then compare each row against the deterministic expected card labels. The scorecard records:

```yaml
worker:
task_class_accuracy:
risk_tag_recall:
blocking_recall:
format_validity:
correction_count:
latency:
verified_outcome:
```

Only mismatches and measurements become conclusions; worker prose does not change the validator.

- [ ] **Step 4: Run independent mechanical and Codex audits**

Luna generates/adjudicates negative cases and verifies the hard metrics. A fresh Codex reviewer performs a read-only full-scope audit against this plan and the user contract. Important findings are fixed under TDD and re-audited.

- [ ] **Step 5: Run fresh final verification**

```bash
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/pytest -q
.venv/bin/agent-frontdoor validate fixtures/positive/01_install_only.json
.venv/bin/agent-frontdoor card fixtures/positive/01_install_only.json
.venv/bin/agent-frontdoor explain fixtures/positive/01_install_only.json
.venv/bin/agent-frontdoor check-drift fixtures/drift/01_audit_to_mutation.json fixtures/drift/01_audit_to_mutation.json
git status --short
git remote -v
```

The final drift smoke may instead use extracted `before`/`after` temporary JSON files because drift fixtures store labeled pairs. Confirm the command exits `3` and names the expected drift.

- [ ] **Step 6: Commit final documentation without pushing**

```bash
git add README.md docs tests/test_readme.py
git commit -m "docs: complete agent frontdoor v0 contract"
```

Verify the commit exists locally, `git remote -v` has no configured push target, and no push was performed.
