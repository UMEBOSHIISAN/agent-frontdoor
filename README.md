This is not an agent runtime.
This is not an autonomous router.
This is a preflight contract and validator for safely preparing tasks for AI workers.

# Agent Frontdoor v0

Agent Frontdoor converts a messy human request into a bounded task card, validates
that card, and renders a human-readable explanation:

```text
messy human request
-> bounded task card
-> schema and semantic validation
-> human-readable explanation
```

The current contract is `schema/intake.v0.json`, a JSON Schema Draft 2020-12
document plus deterministic semantic checks in the validator.

## Safety boundary

Agent Frontdoor performs preflight only. The package has:

- no task execution;
- no network requests;
- no worker invocation;
- no automatic routing;
- no runtime, daemon, server, or hook integration;
- no deployment, scheduler mutation, secret access, or authority grant;
- no task-file writes or repair fallback.

The CLI reads local JSON files and writes deterministic results to standard output
or standard error. A task card describes boundaries for another system; it does
not grant that system permission to act.

## Installation

Python 3.10 or newer is required. The standard installation resolves
`jsonschema>=4` from PyPI, and the `test` extra installs pytest:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

Agent Frontdoor itself requires no network access at runtime. Network access is
used only to retrieve dependencies during installation.

### Offline installation

For an offline installation, Python 3.10 or newer, setuptools, and
`jsonschema>=4` must already be available locally. The following commands disable
dependency and build-isolation downloads:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

Pytest must also already be available locally to run the test suite offline.

## CLI

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

For `check-drift`, an unreadable or malformed input takes exit-code precedence
over a loaded-invalid card. Diagnostics go to standard error; successful output
and drift findings go to standard output.

## `intake.v0` task card

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

## Human gates and fail-closed rules

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
allowed actions, and a non-mutating next step.

The validator additionally rejects schema errors, a normalized action that is
both allowed and forbidden, unsafe non-blocking work, and malformed or unreadable
input. It returns typed issues rather than permissive prose.

## Boundary drift

`check-drift` reports every matching named expansion. The required families are:

- read-only audit -> mutation recommendation
- design review -> implementation
- installation -> architecture migration
- draft -> external publish
- proposal-only -> authority promotion
- bounded files -> unrelated broad refactor

The comparator uses deterministic lexical heuristics over validated task classes,
risk-tag additions, allowed actions, and `next_safe_step`. It never mutates either
card.

The split card examples can be passed directly to the CLI:

```bash
.venv/bin/agent-frontdoor check-drift examples/drift_before.json examples/drift_after.json
# exit 3: reports audit_to_mutation
.venv/bin/agent-frontdoor check-drift examples/safe_before.json examples/safe_after.json
# exit 0: prints NO DRIFT
```

## Fixtures and hard metrics

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
`1.00`, fail-safe UNKNOWN behavior, boundary-drift recall of at least `0.95`, and
zero forbidden execution, network, worker, routing, or source-write paths.
These are test contracts, not claims about an unverified run.

## Programmatic interfaces

The public local interfaces are:

```python
from frontdoor.boundary_drift import detect_boundary_drift
from frontdoor.formatter import format_card, format_explanation
from frontdoor.validator import load_card, validate_card
```

`load_card` reads one local JSON file and returns the loaded value plus a typed
validation result. `validate_card` and `detect_boundary_drift` are deterministic
and do not mutate their inputs.
