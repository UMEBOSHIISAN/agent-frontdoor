# Cross-Agent Intent Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a privacy-minimized deterministic intent lock to Agent Frontdoor and ship a separate optional hook adapter for Codex and Claude Code.

**Architecture:** The existing `frontdoor` distribution receives only immutable derivation, evaluation, transition, and schema-validation logic. A sibling `agent-frontdoor-hooks` distribution owns session-key hashing, atomic state storage, hook event normalization, and platform JSON output. The core never writes files or grants authority.

**Tech Stack:** Python 3.10+, dataclasses, standard-library hashing/JSON/path handling, JSON Schema Draft 2020-12, pytest.

## Global Constraints

- Preserve the core package's no execution, subprocess, socket, network, worker invocation, routing, or file-write guarantee.
- Store no raw prompt, raw session id, transcript path, raw command, tool response, credential, or OAuth material in adapter state.
- A same-intent decision never grants authority; allowed calls emit no permission decision.
- No retry, repair fallback, autonomous routing, or silent target widening.
- Keep the existing four-command `agent-frontdoor` CLI unchanged.
- Keep `CC_UNAUDITED` until a separate CC review artifact exists.

---

### Task 1: Pure intent-lock contract

**Files:**
- Create: `src/frontdoor/schema/intent-lock.v1.json`
- Create: `src/frontdoor/intent_lock.py`
- Create: `tests/test_intent_lock.py`
- Create: `fixtures/intent-lock/cloudflare_api_target.json`
- Create: `fixtures/intent-lock/exact_command.json`

**Interfaces:**
- Produces: `IntentLock`, `IntentDecision`, `derive_lock(prompt, previous=None)`, `evaluate_action(lock, action)`, `bind_tool_use(lock, tool_use_id)`, `matches_tool_use(lock, tool_use_id)`, `record_result(lock, action, failed)`, `lock_to_dict(lock)`, and `lock_from_dict(value)`.
- `IntentLock` fields match `intent-lock.v1`; all values are immutable tuples/scalars.

- [ ] **Step 1: Write failing derivation and privacy tests**

```python
lock = derive_lock(ERROR_PROMPT)
assert lock.mode == "LITERAL_TARGET"
assert lock.display_targets == ("cloudflare-api",)
assert "cloudflare-api" not in lock.source_prompt_sha256
assert "invalid_grant" not in json.dumps(lock_to_dict(lock))
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `../../.venv/bin/python -m pytest tests/test_intent_lock.py -q`
Expected: collection failure because `frontdoor.intent_lock` does not exist.

- [ ] **Step 3: Implement immutable contract, deterministic extraction, hashing, and schema validation**

```python
@dataclass(frozen=True)
class IntentLock:
    schema_version: str
    intent_epoch: int
    source_prompt_sha256: str
    phase: str
    mode: str
    exact_command_sha256: str | None
    target_token_sha256: tuple[str, ...]
    display_targets: tuple[str, ...]
    pending_tool_use_sha256: str | None

@dataclass(frozen=True)
class IntentDecision:
    allowed: bool
    code: str
    reason: str
```

- [ ] **Step 4: Add failing evaluation and transition tests**

```python
assert not evaluate_action(lock, "npx wrangler whoami").allowed
assert evaluate_action(lock, "codex mcp login cloudflare-api").allowed
failed = record_result(lock, "codex mcp login cloudflare-api", failed=True)
assert failed.phase == "REPORT_REQUIRED"
assert not evaluate_action(failed, "rg cloudflare-api .").allowed
```

- [ ] **Step 5: Implement minimal action evaluation and immutable transitions**

```python
def evaluate_action(lock: IntentLock, action: str) -> IntentDecision:
    if lock.phase == "REPORT_REQUIRED":
        return IntentDecision(False, "report_required", REPORT_REASON)
    if lock.phase == "RELEASED":
        return IntentDecision(True, "released", "Intent lock is released.")
    # EXACT_COMMAND compares normalized-command SHA-256.
    # LITERAL_TARGET requires every target-token digest in the action.
```

- [ ] **Step 6: Run focused tests and the core no-execution guard**

Run: `../../.venv/bin/python -m pytest tests/test_intent_lock.py tests/test_no_execution_paths.py -q`
Expected: all pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add src/frontdoor/intent_lock.py src/frontdoor/schema/intent-lock.v1.json tests/test_intent_lock.py fixtures/intent-lock
git commit -m "feat: add deterministic intent lock core"
```

### Task 2: Optional hook adapter distribution

**Files:**
- Create: `adapters/pyproject.toml`
- Create: `adapters/src/frontdoor_hooks/__init__.py`
- Create: `adapters/src/frontdoor_hooks/state.py`
- Create: `adapters/src/frontdoor_hooks/hook.py`
- Create: `tests/test_hook_state.py`
- Create: `tests/test_hook_adapter.py`

**Interfaces:**
- Consumes: Task 1 `IntentLock` serialization and decision functions.
- Produces: `state_path(state_root, session_id)`, `load_session_lock`, `save_session_lock`, `delete_session_lock`, `handle_user_prompt`, `handle_pre_tool`, `handle_tool_result`, `handle_session_end`, `handle_event(payload, state_root)`, and console `agent-frontdoor-hook`.

- [ ] **Step 1: Write failing state privacy and atomicity tests**

```python
path = save_session_lock(tmp_path, "raw-session-id", lock)
assert "raw-session-id" not in path.name
assert "raw-session-id" not in path.read_text()
assert stat.S_IMODE(path.stat().st_mode) == 0o600
```

- [ ] **Step 2: Run state tests and verify RED**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest tests/test_hook_state.py -q`
Expected: collection failure because `frontdoor_hooks` does not exist.

- [ ] **Step 3: Implement hashed filenames and atomic private state writes**

```python
def state_path(root: Path, session_id: str) -> Path:
    return root / f"{sha256(session_id.encode()).hexdigest()}.json"

def save_session_lock(root: Path, session_id: str, lock: IntentLock) -> Path:
    # mkdir mode 0700; write a sibling temporary file mode 0600; os.replace.
```

- [ ] **Step 4: Write failing event-normalization and output tests**

```python
deny = handle_event(pre_tool_payload("npx wrangler whoami"), tmp_path)
assert deny["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
assert deny["hookSpecificOutput"]["permissionDecision"] == "deny"
assert "literal target" in deny["hookSpecificOutput"]["permissionDecisionReason"]
```

- [ ] **Step 5: Implement UserPromptSubmit, PreToolUse, result, failure, and SessionEnd handlers**

```python
def handle_event(payload: Mapping[str, object], state_root: Path) -> dict[str, object] | None:
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        return handle_user_prompt(payload, state_root)
    if event == "PreToolUse":
        return handle_pre_tool(payload, state_root)
    if event in {"PostToolUse", "PostToolUseFailure"}:
        return handle_tool_result(payload, state_root)
    if event == "SessionEnd":
        return handle_session_end(payload, state_root)
    return None
```

- [ ] **Step 6: Run adapter tests**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest tests/test_hook_state.py tests/test_hook_adapter.py -q`
Expected: all pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add adapters tests/test_hook_state.py tests/test_hook_adapter.py
git commit -m "feat: add optional cross-agent hook adapter"
```

### Task 3: Cross-platform fixtures and safety boundaries

**Files:**
- Create: `adapters/examples/codex-hooks.json`
- Create: `adapters/examples/claude-settings.json`
- Create: `fixtures/intent-lock/codex_failure_sequence.json`
- Create: `fixtures/intent-lock/claude_failure_sequence.json`
- Create: `tests/test_hook_fixtures.py`
- Create: `tests/test_adapter_safety.py`

**Interfaces:**
- Consumes: Task 2 console hook and state-root environment contract.
- Produces: executable end-to-end fixtures proving equivalent decisions for Codex `PostToolUse` and Claude Code `PostToolUseFailure`.

- [ ] **Step 1: Write failing subprocess fixture tests**

```python
result = run_hook(sequence[0], state_root)
assert result.returncode == 0
assert json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
```

- [ ] **Step 2: Run fixture tests and verify RED**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest tests/test_hook_fixtures.py tests/test_adapter_safety.py -q`
Expected: failures because examples and sequence fixtures are absent.

- [ ] **Step 3: Add exact Codex and Claude Code hook configurations and failure sequences**

The Codex example registers `UserPromptSubmit`, all local `PreToolUse` and
`PostToolUse` events, and `SessionEnd`. The Claude Code example additionally
registers `PostToolUseFailure`. Neither example edits live user configuration.

- [ ] **Step 4: Add adapter AST safety checks**

Reject imports or calls for network libraries, subprocess execution, worker launch,
retry loops, transcript reads, or writes outside the supplied state root.

- [ ] **Step 5: Run focused fixtures and full core safety tests**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest tests/test_hook_fixtures.py tests/test_adapter_safety.py tests/test_no_execution_paths.py tests/test_distribution_boundary.py -q`
Expected: all pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add adapters/examples fixtures/intent-lock tests/test_hook_fixtures.py tests/test_adapter_safety.py
git commit -m "test: lock cross-agent derailment regressions"
```

### Task 4: OSS documentation and release readiness

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Create: `adapters/README.md`
- Modify: `tests/test_readme.py`
- Modify: `tests/test_distribution_boundary.py`
- Create: `tests/test_intent_lock_schema.py`

**Interfaces:**
- Documents: core versus optional-adapter trust boundaries, installation, dry-run
  fixture replay, live-install boundary, uninstall, privacy, and platform limits.

- [ ] **Step 1: Write failing documentation and packaging contract tests**

Assert that the core wheel contains `intent-lock.v1.json`, the core still exposes
exactly four read-only commands, adapter metadata is independent, and both platforms
have documented install/uninstall steps without private paths.

- [ ] **Step 2: Run documentation tests and verify RED**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest tests/test_readme.py tests/test_distribution_boundary.py tests/test_intent_lock_schema.py -q`
Expected: fail until metadata and documentation are updated.

- [ ] **Step 3: Update public documentation, package data, and changelog**

Keep the core safety promise explicit: hook code ships from the separate adapter
distribution and must be independently reviewed and trusted by the operator.

- [ ] **Step 4: Run documentation and schema tests**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest tests/test_readme.py tests/test_distribution_boundary.py tests/test_intent_lock_schema.py -q`
Expected: all pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add README.md CHANGELOG.md pyproject.toml docs adapters/README.md tests/test_readme.py tests/test_distribution_boundary.py tests/test_intent_lock_schema.py
git commit -m "docs: prepare intent lock OSS integration"
```

### Task 5: Full verification and review

**Files:**
- Review only: all branch changes.

**Interfaces:**
- Produces: fresh test, build, privacy-scan, and diff evidence without publishing.

- [ ] **Step 1: Run all tests on a supported interpreter**

Run: `PYTHONPATH=src:adapters/src ../../.venv/bin/python -m pytest -q`
Expected: all pass, zero failures.

- [ ] **Step 2: Build both distributions without network access**

Run: `../../.venv/bin/python -m build --no-isolation .`
Run: `../../.venv/bin/python -m build --no-isolation adapters`
Expected: wheel and sdist for each distribution.

- [ ] **Step 3: Run privacy and boundary scans**

Run: `rg -n '(^|[^A-Za-z])/(Users|home)/|cloudflare account|OAuth token|refresh token' README.md CHANGELOG.md docs adapters src fixtures tests`
Expected: no private identity, path, account, or token material; the generic regression term `refresh token` may appear only in explanatory fixture text without values.

- [ ] **Step 4: Review branch diff and repository state**

Run: `git diff main...HEAD --check`
Run: `git status --short`
Expected: no whitespace errors and only intentional build artifacts, which remain ignored.

- [ ] **Step 5: Run Codex review**

Run: `codex review --base main`
Expected: no unresolved critical or high findings.

- [ ] **Step 6: Stop before live installation or external publication**

Report the exact branch, commits, tests, build evidence, remaining CC audit label,
and the separate operator gates for live hook configuration and GitHub publication.
