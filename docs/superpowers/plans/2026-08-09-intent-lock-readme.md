# Intent Lock-first README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the root README so a first-time OSS reader reaches the Intent Lock problem, reproducible pure-API demo, and core/adapter trust boundary before the long-form Agent Frontdoor reference.

**Architecture:** Keep one English-first public entrypoint with a concise Japanese summary, then move from problem to demo to distribution boundaries and finally the existing detailed contracts. Preserve the read-only core, optional unactivated adapter, and authority-separation claims as test-enforced public behavior; do not change runtime code or configuration.

**Tech Stack:** Markdown, Python 3.10+, pytest, the public `frontdoor.intent_lock` API, Git.

## Global Constraints

- Preserve the first three lines of `README.md` exactly as enforced by `tests/test_readme.py`.
- English is the primary reference language; keep one concise Japanese summary near the top instead of a duplicated full reference.
- Keep the core's four commands exactly: `validate`, `card`, `explain`, and `check-drift`.
- Keep `agent-frontdoor` read-only and side-effect free; describe `agent-frontdoor-hooks` as separately installable, optional, and inactive after installation.
- Intent matching does not grant authority; independent permission, safety, and human gates still apply.
- Keep `CC_UNAUDITED` as disclosure, not evidence.
- Do not claim a test count, external audit success, security boundary, live activation, publication, deployment, or authority grant.
- Do not add private paths, session identifiers, credentials, tokens, transcripts, or operator-owned configuration.
- Do not modify runtime code, adapter configuration examples, packaging metadata, live settings, or release state.
- Run each verification command once. An unexpected failure or review finding is
  visible to the human and stops this plan; do not add an automatic retry loop.

## File Map

- Modify `tests/test_readme.py`: enforce the new Intent Lock-first ordering, runnable demo markers, and removal of duplicated legacy framing without weakening existing safety assertions.
- Rewrite `README.md`: provide the approved reader flow and retain all tested public core and adapter contracts once each.
- Reference only: `docs/INTENT_LOCK.md`, `adapters/README.md`, `docs/FRIEND_LAB.md`, and `src/frontdoor/intent_lock.py` remain unchanged.

---

### Task 1: Reorganize and verify the public README

**Files:**
- Modify: `tests/test_readme.py:173-220`
- Modify: `README.md:1-418`

**Interfaces:**
- Consumes: `derive_lock(prompt: str, previous: IntentLock | None = None) -> IntentLock | None` and `evaluate_action(lock: IntentLock, action: str) -> IntentDecision` from `frontdoor.intent_lock`.
- Produces: one root README whose heading order, demo, install boundary, safety language, CLI contract, and reference material are enforced by `tests/test_readme.py`.

- [ ] **Step 1: Add the failing reader-flow contract**

Append this test without changing or deleting existing assertions:

```python
def test_readme_leads_with_intent_lock_reader_flow() -> None:
    text = _text()
    ordered_sections = (
        "## Why Intent Lock exists / なぜ必要か",
        "## 30-second demo / 30秒デモ",
        "## Two distributions, separate trust boundaries",
        "## Safety model: identity is not authority",
        "## Core quick start",
        "## Optional runtime hooks",
        "## Bounded task-card reference",
    )
    positions = [text.index(section) for section in ordered_sections]
    assert positions == sorted(positions)

    for marker in (
        'denied = evaluate_action(lock, "npx wrangler whoami")',
        'allowed = evaluate_action(lock, "codex mcp login cloudflare-api")',
        "False literal_target_mismatch",
        "True literal_target_match",
        "Installing the adapter does not activate",
    ):
        assert marker in text

    for duplicated_heading in (
        "# Agent Frontdoor v0",
        "## English documentation",
        "## 日本語ドキュメント",
    ):
        assert duplicated_heading not in text
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
../../.venv/bin/python -m pytest tests/test_readme.py::test_readme_leads_with_intent_lock_reader_flow -q
```

Expected: FAIL because the approved headings and demo are not yet present.

- [ ] **Step 3: Rewrite `README.md` around the approved reader flow**

Preserve the required opening lines, badge version `v0.2.0`, logo, and pulse. Use
this exact top-level section order after the hero:

```markdown
## Why Intent Lock exists / なぜ必要か
## 30-second demo / 30秒デモ
## Two distributions, separate trust boundaries
## Safety model: identity is not authority
## Core quick start
## Optional runtime hooks
## Bounded task-card reference
## Offline acceptance
## Programmatic interfaces
## Uninstall
## Limits and audit status
```

Use English for the canonical explanations and keep one Japanese paragraph below
the problem statement summarizing that Agent Frontdoor fixes an action to the
literal request, does not execute it, and does not grant authority.

The demo must be a pure string-evaluation example with this exact executable
body and expected output:

```python
from frontdoor.intent_lock import derive_lock, evaluate_action

error = """\
MCP client for `cloudflare-api` failed to start: OAuth refresh token rejected.
invalid_grant: Grant not found
"""
lock = derive_lock(error)
assert lock is not None

denied = evaluate_action(lock, "npx wrangler whoami")
allowed = evaluate_action(lock, "codex mcp login cloudflare-api")

print(denied.allowed, denied.code)
print(allowed.allowed, allowed.code)
# False literal_target_mismatch
# True literal_target_match
```

State immediately below the demo that it compares strings only and executes
neither command.

Use this two-distribution table, preserving the distinction between package
installation and hook activation:

```markdown
| Distribution | Responsibility | Runtime effect |
|---|---|---|
| `agent-frontdoor` | Pure task-card validation, boundary-drift detection, and `intent-lock.v1` decisions | Reads local inputs and returns deterministic decisions; no task execution or state writes |
| `agent-frontdoor-hooks` | Optional Codex and Claude Code event adapter | Writes privacy-minimized session state only after the operator separately configures a hook |
```

Follow the table with the exact boundary sentence: "Installing the adapter does
not activate either example or edit live settings." Link the contract to
`docs/INTENT_LOCK.md`, adapter review and removal steps to `adapters/README.md`,
and show the inert files at `adapters/examples/codex-hooks.json` and
`adapters/examples/claude-settings.json` plus both
`agent-frontdoor-hook --platform ...` invocations.

Also retain the exact tested phrases "core package remains read-only" and
"optional sibling distribution". The safety summary must explicitly include
"no task execution", "no network requests", "no worker invocation", and "no
automatic routing".

Under `Safety model`, retain these facts once, in this order:

1. Intent matching does not grant authority.
2. Independent permission, safety, and human gates still apply.
3. A failed or outcome-opaque matching action requires a human-facing report
   before another tool call.
4. Local hooks are a guardrail, not a security boundary; hosted or specialized
   paths may be outside coverage.

Combine the two existing installation snippets into one `Core quick start` using
the tested commands:

```bash
export AGENT_FRONTDOOR_REPOSITORY_URL='<PUBLIC_REPOSITORY_URL>'
git clone "$AGENT_FRONTDOOR_REPOSITORY_URL" agent-frontdoor
cd agent-frontdoor
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/pytest -q
.venv/bin/agent-frontdoor validate fixtures/positive/01_install_only.json
.venv/bin/agent-frontdoor card fixtures/positive/01_install_only.json
```

Under `Optional runtime hooks`, explain that installation and live configuration
are separate operator actions and link to `adapters/README.md`; do not reproduce
or mutate operator-owned settings.

Under `Bounded task-card reference`, retain exactly once all existing tested
material:

- the `intake.v0` flow and `src/frontdoor/schema/intake.v0.json` path;
- all four CLI commands and exit codes `0` through `3`;
- the `INVALID`, `ERROR`, and `DRIFT` meanings;
- all 14 task-card fields and all 10 task classes;
- gates `NONE`, `CONFIRM`, and `BLOCKING`;
- every blocking category and all six boundary-drift families;
- runnable drift and safe examples;
- fixture locations, hard metric contracts, and both pytest commands.

Move the existing no-index wheelhouse instructions and `docs/FRIEND_LAB.md`
link under `Offline acceptance`. Keep the existing programmatic imports,
core uninstall command, platform limits, `CODEX_SELF_CONFIDENT_ADOPTED`,
`REPEATED_EXCESSIVE_DERAILMENT`,
`COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT`, `CC_UNAUDITED`, and
`CANDIDATE_ONLY` disclosure in their named final sections. Remove only the
duplicated `English documentation`, full `日本語ドキュメント`, and second
`Agent Frontdoor v0` framing.

- [ ] **Step 4: Execute the documented pure API demo**

Run:

```bash
env PYTHONPATH=src ../../.venv/bin/python -c 'from frontdoor.intent_lock import derive_lock,evaluate_action; prompt="MCP client for `cloudflare-api` failed to start: OAuth refresh token rejected.\ninvalid_grant: Grant not found\n"; lock=derive_lock(prompt); denied=evaluate_action(lock,"npx wrangler whoami"); allowed=evaluate_action(lock,"codex mcp login cloudflare-api"); print(denied.allowed,denied.code); print(allowed.allowed,allowed.code)'
```

Expected:

```text
False literal_target_mismatch
True literal_target_match
```

- [ ] **Step 5: Run the focused documentation contracts**

Run:

```bash
../../.venv/bin/python -m pytest tests/test_readme.py tests/test_distribution_boundary.py -q
```

Expected: PASS with no weakened existing assertion.

- [ ] **Step 6: Run the complete suite**

Run:

```bash
../../.venv/bin/python -m pytest -q
```

Expected: all tests pass; report the measured result rather than copying a stale
count into the README.

- [ ] **Step 7: Audit the final diff and public boundary**

Run:

```bash
git diff --check
rg -n '/Users/umeboshi|PRIVATE_HANDOFF_READY_WITH_GAPS|CC_AUDITED|security boundary$' README.md tests/test_readme.py
git diff -- README.md tests/test_readme.py
```

Expected: `git diff --check` succeeds; the scan prints no private path, false CC
audit, or false security-boundary claim; every diff hunk belongs to this README
task.

- [ ] **Step 8: Run Codex review on the uncommitted README change**

Run:

```bash
codex review --uncommitted
```

Expected: no actionable defect. If the review returns an actionable finding,
stop and report it; correction and re-verification require an explicit visible
continuation rather than an automatic retry.

- [ ] **Step 9: Commit the verified README change**

```bash
git add README.md tests/test_readme.py
git diff --cached --check
git commit -m "docs: lead README with Intent Lock"
```
