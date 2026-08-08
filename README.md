This is not an agent runtime.
This is not an autonomous router.
This is a preflight contract and validator for safely preparing tasks for AI workers.

![Agent Frontdoor](https://img.shields.io/badge/Agent%20Frontdoor-v0.2.0-111827)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![Safety](https://img.shields.io/badge/runtime-fail--closed-16a34a)

# Agent Frontdoor

<p align="center">
  <img src="assets/agent-frontdoor-logo.svg" alt="Agent Frontdoor logo" width="180">
</p>

<p align="center"><img src="assets/agent-frontdoor-pulse.svg" alt="Agent Frontdoor validation pulse" width="720"></p>

> Fail-closed preflight validation for bounded AI task cards.

## Why Intent Lock exists / なぜ必要か

Agent Frontdoor is the **front door before an AI worker**. It turns an informal
request into an explicit contract that a human can inspect before another system
acts. `intent-lock.v1` keeps a proposed tool action attached to the literal
command or error target that prompted it, so reasonable but unrelated procedures
cannot silently combine into a new task.

It does not run an agent, choose a model, call an API, or grant authority.

Agent Frontdoorは、依頼を文字どおりの要求に固定し、実行も権限付与もしない
読み取り専用OSSです。別システムが行動する前に人が確認できる境界付きタスク
カードへ変換します。

## 30-second demo / 30秒デモ

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

This compares strings only and executes neither command. Intent matching does
not grant authority.

## Two distributions, separate trust boundaries

| Distribution | Responsibility | Runtime effect |
|---|---|---|
| `agent-frontdoor` | Pure task-card validation, boundary-drift detection, and `intent-lock.v1` decisions | Reads local inputs and returns deterministic decisions; no task execution or state writes |
| `agent-frontdoor-hooks` | Optional Codex and Claude Code event adapter | Writes privacy-minimized session state only after the operator separately configures a hook |

Installing the adapter does not activate either example or edit live settings.
The core package remains read-only; runtime state and platform event handling
are kept in the separately installable, optional sibling distribution
`agent-frontdoor-hooks`. The Intent Lock contract is in
[`docs/INTENT_LOCK.md`](docs/INTENT_LOCK.md); adapter review, configuration, and
removal steps are in [`adapters/README.md`](adapters/README.md).

The Codex and Claude Code examples are inert files at
[`adapters/examples/codex-hooks.json`](adapters/examples/codex-hooks.json) and
[`adapters/examples/claude-settings.json`](adapters/examples/claude-settings.json).
After replacing their reviewed absolute virtual-environment placeholder, they
invoke `agent-frontdoor-hook --platform codex` and
`agent-frontdoor-hook --platform claude`, respectively.

## Safety model: identity is not authority

Intent matching does not grant authority. Independent permission, safety, and
human gates still apply. A failed or outcome-opaque matching action requires a
human-facing report before another tool call. Local hooks are a guardrail, not a
security boundary: hosted or specialized execution paths may be outside coverage.

The core distribution performs preflight only:

- no execution, subprocess, socket, network, worker invocation, or routing;
- no scheduler, hook, daemon, server, deployment, credential, or secret access;
- no repair fallback, retry, automatic publish, or authority promotion;
- no task-file writes or runtime, daemon, server, or hook integration in the
  core distribution.

This means no task execution, no network requests, no worker invocation, and no automatic routing.
Input files are read locally; results are deterministic stdout/stderr output.
`UNKNOWN` and high-risk expansion fail closed with `BLOCKING`.

The CLI reads local JSON files and writes deterministic results to standard
output or standard error. A task card describes boundaries for another system;
it does not grant that system permission to act. Current independent CC review
is recorded as `CC_UNAUDITED`; the label is disclosure rather than proof.

## Core quick start

Python 3.10 or newer is required. Supply the repository location explicitly;
the install procedure never infers a private checkout or operator path. The
standard installation may resolve `jsonschema>=4` and the `test` extra from
PyPI:

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

Agent Frontdoor itself requires no network access at runtime. Network access is
used only to retrieve dependencies during installation. For the frozen-contract
Gate 4 reproduction, create a fresh local bare repository from the reviewed
public commit and set `AGENT_FRONTDOOR_REPOSITORY_URL` to its explicitly
supplied `file://` URL. Use the same clone, install, full-test, `validate`, and
`card` sequence above.

## Optional runtime hooks

Installation and live configuration are separate operator actions. Review the
inert examples, configuration, and removal procedure in
[`adapters/README.md`](adapters/README.md); do not reproduce or mutate
operator-owned settings. Installing `agent-frontdoor-hooks` does not activate
a hook or alter live settings.

## Bounded task-card reference

The contract is versioned as `intake.v0` in
[`src/frontdoor/schema/intake.v0.json`](src/frontdoor/schema/intake.v0.json).
The public CLI and exit codes are stable; changing the schema version is an
explicit compatibility decision. The current contract is installed as package
data, uses JSON Schema Draft 2020-12, and has deterministic semantic checks in
the validator.

```text
request / 依頼
  -> schema + semantic validation / スキーマ・意味検証
  -> bounded task card / 境界付きカード
  -> card | explain / 人間が読める出力
  -> optional check-drift / 変更による権限拡張の検出
```

| Situation / 場面 | Frontdoor result / 出力 |
|---|---|
| A bounded implementation request / 境界付き実装依頼 | `IMPLEMENTATION` card |
| A design or security review / 設計・安全レビュー | `DESIGN_REVIEW` or `AUDIT` |
| An ambiguous or unsafe request / 曖昧・危険な依頼 | `UNKNOWN` + `BLOCKING` |
| A proposed expansion after review / レビュー後の拡張 | `check-drift` reports drift |

### CLI

The installed package exposes exactly four read-only preflight commands:

```bash
agent-frontdoor validate task.json
agent-frontdoor card task.json
agent-frontdoor explain task.json
agent-frontdoor check-drift before.json after.json
```

- `validate` prints a stable valid/invalid result.
- `card` prints the complete fixed-order task card only after validation succeeds.
- `explain` prints a self-contained explanation only after validation succeeds.
- `check-drift` validates both cards before comparing their boundaries.

Exit codes are part of the CLI contract:

- `0`: valid card or no drift
- `1`: loaded card is invalid
- `2`: input is unreadable or malformed JSON
- `3`: boundary drift detected

Output markers are equally strict: `INVALID` means a loaded card violated the
contract, `ERROR` means an input could not be read or decoded, and `DRIFT` means
a validated before/after pair crossed a named boundary. None of these results
executes or repairs the task. For `check-drift`, an unreadable or malformed
input takes exit-code precedence over a loaded-invalid card. Diagnostics go to
standard error; successful output and drift findings go to standard output.

### `intake.v0` task card

Every card contains all 14 core fields:

| Field | Purpose |
|---|---|
| `schema_version` | Fixed contract version: `intake.v0` |
| `request_id` | Stable request identifier |
| `human_request` | Original human request |
| `task_class` | One bounded task class |
| `risk_tags` | Explicit safety-relevant categories |
| `allowed_actions` | Actions inside the task boundary |
| `forbidden_actions` | Actions explicitly outside the boundary |
| `required_evidence` | Evidence needed to verify the outcome |
| `required_manifest` | Optional named manifest, otherwise null |
| `human_gate` | Required human decision state |
| `predicted_worker_capability` | Capability label, never a model name |
| `unknowns` | Unresolved facts that must remain visible |
| `assumptions` | Explicit bounded assumptions |
| `next_safe_step` | The next non-escalating step |

The task classes are deliberately small:

- `RESEARCH`
- `DESIGN_REVIEW`
- `IMPLEMENTATION`
- `CODE_REVIEW`
- `AUDIT`
- `CONTENT_DRAFT`
- `DATA_ANALYSIS`
- `INSTALLATION`
- `OPERATIONS`
- `UNKNOWN`

Specific model or vendor names are not valid worker capabilities.

### Human gates and fail-closed rules

The three gate values are:

- `NONE`: no additional confirmation is required by this card;
- `CONFIRM`: a human confirmation is requested before the bounded next step;
- `BLOCKING`: stop until a human explicitly resolves the gate.

`BLOCKING` is mandatory when risk tags or request/action text involve any of:

- `deploy`
- `production`
- `scheduler`
- `secret`
- `auth`
- `billing`
- `delete`
- `destructive cleanup`
- `SSOT mutation`
- `external publish`
- `authority promotion`

`UNKNOWN` also fails closed: it requires `BLOCKING`, the
`none-until-clarified` capability, at least one stated unknown, explicitly safe
allowed actions, and a non-mutating next step. The validator additionally
rejects schema errors, a normalized action that is both allowed and forbidden,
unsafe non-blocking work, and malformed or unreadable input. It returns typed
issues rather than permissive prose.

### Boundary drift

`check-drift` reports every matching named expansion. The required families are:

- read-only audit -> mutation recommendation
- design review -> implementation
- installation -> architecture migration
- draft -> external publish
- proposal-only -> authority promotion
- bounded files -> unrelated broad refactor

The comparator uses deterministic lexical heuristics over validated task
classes, risk-tag additions, allowed actions, and `next_safe_step`. It never
mutates either card. The split card examples can be passed directly to the CLI:

```bash
.venv/bin/agent-frontdoor check-drift examples/drift_before.json examples/drift_after.json
# exit 3: reports audit_to_mutation
.venv/bin/agent-frontdoor check-drift examples/safe_before.json examples/safe_after.json
# exit 0: prints NO DRIFT
```

### Fixtures and hard metrics

Synthetic fixtures live under:

- `fixtures/positive/` for complete valid cards;
- `fixtures/negative/` for named fail-closed cases;
- `fixtures/drift/` for labeled before/after envelopes and safe controls.

The `fixtures/drift/*.json` files are labeled test envelopes containing
`before`, `after`, `label`, and `expected_codes`; they are not direct CLI inputs.
Use the split cards under `examples/` for directly runnable CLI examples.

Run the hard corpus and source-safety contracts with:

```bash
.venv/bin/pytest tests/test_fixture_metrics.py tests/test_no_execution_paths.py -q
```

Run the complete local suite with:

```bash
.venv/bin/pytest -q
```

The hard contracts require schema validity `1.00`, negative blocking recall
`1.00`, fail-safe UNKNOWN behavior, boundary-drift recall of at least `0.95`,
and zero forbidden execution, network, worker, routing, or source-write paths.
These are test contracts, not claims about an unverified run.

## Offline acceptance

Do not reuse host or global packages for offline acceptance. Use only the
hash-verified, receiver-specific wheelhouse from the friend pack. The complete
attended procedure, detached verification order, controls, and receipt rules are
in [`docs/FRIEND_LAB.md`](docs/FRIEND_LAB.md).

```bash
export WHEELHOUSE='<VERIFIED_WHEELHOUSE>'
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links "$WHEELHOUSE" setuptools wheel
.venv/bin/python -m pip install --no-index --find-links "$WHEELHOUSE" --no-build-isolation -e ".[test]"
```

Missing or incompatible wheels are a hard stop. There is no index fallback,
source-build fallback, retry, or host-package fallback.

For a friend acceptance, first verify the ZIP and validation script SHA-256,
then follow [`docs/FRIEND_LAB.md`](docs/FRIEND_LAB.md) with the network
disconnected. Acceptance checks installation, fixtures, CLI, boundary guards,
privacy inspection, uninstall, and receipt; it never automatically changes the
recipient's existing hooks, settings, models, or secrets.

## Programmatic interfaces

The public local interfaces are:

```python
from frontdoor.boundary_drift import detect_boundary_drift
from frontdoor.formatter import format_card, format_explanation
from frontdoor.intent_lock import derive_lock, evaluate_action, record_result
from frontdoor.validator import load_card, validate_card
```

`load_card` reads one local JSON file and returns the loaded value plus a typed
validation result. `validate_card` and `detect_boundary_drift` are deterministic
and do not mutate their inputs. `derive_lock`, `evaluate_action`, and
`record_result` are pure intent-state operations; filesystem lifecycle support is
available only from the separate `agent-frontdoor-hooks` distribution.

## Uninstall

Remove the package from the active virtual environment without touching the
source checkout or any other environment:

```bash
.venv/bin/python -m pip uninstall -y agent-frontdoor
```

Confirm that `.venv/bin/agent-frontdoor` is no longer available. Deleting a
disposable test directory is a separate human action and is never performed by
Agent Frontdoor.

## Limits and audit status

Agent Frontdoor is not a replacement for human judgment, a policy engine with
authority, or a full agent harness. `CODEX_SELF_CONFIDENT_ADOPTED`,
`REPEATED_EXCESSIVE_DERAILMENT`,
`COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT`, and `CANDIDATE_ONLY` are
audit disclosures, not authority grants or proof of coverage.

Public repositories contain no secrets, real usernames, LAN addresses, personal
paths, local history, memory, or settings. Friend-specific configuration belongs
in adapters and this README, not in the core package.
