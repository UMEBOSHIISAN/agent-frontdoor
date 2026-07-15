# Agent Frontdoor v0 Design

**Status:** Human-approved by the `/goal` request dated 2026-07-15.

## Purpose

Agent Frontdoor v0 turns a bounded JSON task description into three things only:

```text
messy human request
-> bounded task card
-> schema and semantic validation
-> human-readable explanation
```

It is not an agent runtime, autonomous router, dispatcher, daemon, MCP server,
hook, or execution engine. It never invokes workers, tools, network services,
or task actions.

## Existing Design Reuse

The existing v0.1 schema-only skeleton is retained as historical reference.
Its useful design decisions remain binding:

- task boundaries are explicit and deny unknown fields;
- worker predictions are capability labels, never model or vendor names;
- human authority remains outside the schema;
- unknown or unsafe input fails closed;
- risk is separate from task class.

The working v0 contract is `schema/intake.v0.json`. Runtime behavior lives only
in `src/frontdoor/` and is limited to reading JSON, validating, formatting, and
comparing two cards for boundary drift.

## Card Contract

Every card requires these fields:

```yaml
schema_version:
request_id:
human_request:
task_class:
risk_tags:
allowed_actions:
forbidden_actions:
required_evidence:
required_manifest:
human_gate:
predicted_worker_capability:
unknowns:
assumptions:
next_safe_step:
```

`task_class` is exactly one of:

```text
RESEARCH
DESIGN_REVIEW
IMPLEMENTATION
CODE_REVIEW
AUDIT
CONTENT_DRAFT
DATA_ANALYSIS
INSTALLATION
OPERATIONS
UNKNOWN
```

`human_gate` is exactly `NONE`, `CONFIRM`, or `BLOCKING`.

The schema uses a small, explicit risk-tag vocabulary for the required unsafe
categories plus `cleanup_adjacent`, `scope_drift`, and `unknown`. Any request or
risk tag involving deploy, production, scheduler, secret, auth, billing,
delete, destructive cleanup, SSOT mutation, external publish, or authority
promotion requires `human_gate: BLOCKING`. `UNKNOWN` also requires
`human_gate: BLOCKING` and a no-action-until-clarified capability.

## Components

- `schema/intake.v0.json`: structural contract and fixed enums.
- `src/frontdoor/validator.py`: JSON Schema plus fail-closed semantic rules.
- `src/frontdoor/formatter.py`: deterministic task card and explanation text.
- `src/frontdoor/boundary_drift.py`: deterministic comparison of before/after
  cards for the six required drift families.
- `src/frontdoor/cli.py`: four read-only commands.
- `fixtures/positive/` and `fixtures/negative/`: at least 30 cases each.
- `tests/`: contract, CLI, drift, safety, and metric tests.
- `docs/worker_comparison_scorecard.yaml`: mismatches from the same 20 inputs.

## CLI Contract

```bash
agent-frontdoor validate task.json
agent-frontdoor card task.json
agent-frontdoor explain task.json
agent-frontdoor check-drift before.json after.json
```

All commands read local JSON only. `validate`, `card`, and `explain` fail closed
on structural or semantic errors. `check-drift` validates both cards before
comparison and returns a distinct non-zero exit status when drift is detected.

## Boundary Drift

The comparator must detect these minimum transitions:

```text
read-only audit -> mutation recommendation
design review -> implementation
installation -> architecture migration
draft -> external publish
proposal-only -> authority promotion
bounded files -> unrelated broad refactor
```

The comparator reports named reasons; it does not repair or execute anything.

## Verification

- package installs locally without dependency download;
- all four CLI commands run;
- schema validity is 1.00 across positive fixtures;
- negative blocking recall is 1.00;
- unknown input resolves to `UNKNOWN` or `BLOCKING`;
- boundary drift detection is at least 0.95 on labeled fixtures;
- source has no worker invocation, task execution, network, daemon, or write
  path outside console output;
- at least 30 positive and 30 negative fixtures cover all twelve requested
  categories;
- local workers classify the same 20 inputs; only mismatches against the
  deterministic validator are recorded as evaluation evidence.

## Fixed Boundaries

Do not modify or connect to `Workspace/RAG/`, Obsidian, Temporal Knowledge OS,
settings, hooks, production routing, routing ledgers, worker registry sources,
schedulers, deploy systems, or external publication. Do not push or publish.

## Asset Homes

- Contract decisions: schema and this design.
- User-facing guarantees: README.
- Procedures and exact build steps: implementation plan.
- Examples and failures: fixtures and tests.
- Worker observations: worker comparison scorecard.
- Final independent judgment: `docs/final_audit.md`.
- Session persistence: `docs/closeout_v0.md` and local Git commits.

