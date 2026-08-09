# Core Reference

This document is the canonical reference for the `intake.v0` task-card
contract, its read-only CLI, fail-closed gates, boundary-drift comparison, and
local programmatic interfaces. Reproducible fixture-corpus and source-boundary
measurements live in [EVIDENCE.md](EVIDENCE.md).

## Trust boundary

Agent Frontdoor is a preflight contract and validator for safely preparing
tasks for AI workers. It is not an agent runtime or an autonomous router. The
core package remains read-only: it performs no task execution, network
requests, worker invocation, or automatic routing. Validation, formatting, and
drift comparison are deterministic local operations and do not repair, execute,
or mutate a task card.

```text
request / 依頼
  -> schema + semantic validation / スキーマ・意味検証
  -> bounded task card / 境界付きカード
  -> card | explain / 人間が読める出力
  -> optional check-drift / 変更による権限拡張の検出
```

## Four-command CLI

The installed package exposes exactly four read-only preflight commands:

```bash
agent-frontdoor validate task.json
agent-frontdoor card task.json
agent-frontdoor explain task.json
agent-frontdoor check-drift before.json after.json
```

- `validate` prints a deterministic valid or invalid result for the current
  source contract.
- `card` prints the complete fixed-order task card only after validation
  succeeds.
- `explain` prints a self-contained explanation only after validation
  succeeds.
- `check-drift` validates both cards before comparing their boundaries.

## Exit and output contract

Exit codes are part of the CLI contract:

- `0`: valid card or no drift
- `1`: loaded card is invalid
- `2`: input is unreadable or malformed JSON
- `3`: boundary drift detected

`VALID <request_id>` is the successful `validate` result. `card` and `explain`
write their respective formatted results only for a valid card. `NO DRIFT` is
the successful `check-drift` result, while `DRIFT` heads each detected
boundary-expansion report.

The failure markers are strict: `INVALID` means a loaded card violated the
contract; `ERROR` means an input could not be read or decoded; and `DRIFT`
means a validated before/after pair crossed a named boundary. Diagnostics go to
standard error; successful output and drift findings go to standard output. For
`check-drift`, unreadable or malformed input takes exit-code precedence over a
loaded-invalid card.

## `intake.v0` schema

The versioned contract is
[`src/frontdoor/schema/intake.v0.json`](../src/frontdoor/schema/intake.v0.json).
It is installed as package data, uses JSON Schema Draft 2020-12, disallows
additional properties, and is followed by deterministic semantic validation.

Every card contains all 14 core fields:

| Field | Purpose |
| --- | --- |
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

The `unknowns` field prevents silent resolution: unresolved facts stay explicit
in the card instead of being guessed away by a worker or an author. The
validator rejects a normalized action that appears in both `allowed_actions`
and `forbidden_actions`.

## Task classes

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

`predicted_worker_capability` is one of `research`, `design-review`,
`implementation`, `code-review`, `audit`, `content-draft`, `data-analysis`,
`installation`, `operations`, or `none-until-clarified`; specific model or
vendor names are not valid capabilities.

## Human gates and fail-closed rules

The three gate values are:

- `NONE`: no additional confirmation is required by this card.
- `CONFIRM`: a human confirmation is requested before the bounded next step.
- `BLOCKING`: stop until a human explicitly resolves the gate.

`BLOCKING` is mandatory when risk tags or request/action text involve any of:

- `deploy`
- `production`
- `scheduler`
- `secret`
- `auth`
- `billing`
- `delete`
- `destructive cleanup` (`destructive_cleanup`)
- `SSOT mutation` (`ssot_mutation`)
- `external publish` (`external_publish`)
- `authority promotion` (`authority_promotion`)

The schema also recognizes `cleanup_adjacent`, `scope_drift`, and `unknown`
risk tags. `UNKNOWN` fails closed: it requires `BLOCKING`, the
`none-until-clarified` capability, at least one stated `unknowns` entry,
explicitly safe allowed actions, and a non-mutating `next_safe_step`. The
validator also rejects unsafe non-blocking work and malformed or unreadable
input, returning typed issues rather than permissive prose.

## Boundary-drift families

`check-drift` reports every matching named expansion. Its required families
are:

- read-only audit -> mutation recommendation
- design review -> implementation
- installation -> architecture migration
- draft -> external publish
- proposal-only -> authority promotion
- bounded files -> unrelated broad refactor

The comparator uses deterministic lexical heuristics over validated task
classes, risk-tag additions, `allowed_actions`, and `next_safe_step`. It never
mutates either card. Split cards under `examples/` can be passed directly to the
CLI:

```bash
.venv/bin/agent-frontdoor check-drift examples/drift_before.json examples/drift_after.json
# exit 3: reports audit_to_mutation
.venv/bin/agent-frontdoor check-drift examples/safe_before.json examples/safe_after.json
# exit 0: prints NO DRIFT
```

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
and do not mutate their inputs. `format_card` and `format_explanation` render
only validated cards. `derive_lock`, `evaluate_action`, and `record_result` are
pure intent-state operations; filesystem lifecycle support is available only
from the separate `agent-frontdoor-hooks` distribution.

## Contract evolution

This is an unreleased 0.2 development contract. The command names, exit
meanings, output markers, schema fields, gate behavior, and named drift families
document the current source revision; they may change before a release, with no
compatibility guarantee. Changing `schema_version` remains an explicit contract
decision. Keep the core read-only when evolving the contract. Use
[EVIDENCE.md](EVIDENCE.md) for reproducible corpus and source-boundary evidence
rather than duplicating measured fixture results here.
