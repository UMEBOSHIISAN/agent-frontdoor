# Concepts

> Historical v0.1 reference only. The working v0 contract is defined by
> `schema/intake.v0.json` and the current `README.md`.

## What Agent Frontdoor is

Agent Frontdoor is a **preflight schema** — a structured contract that converts a raw human request into a bounded, reviewable task card before any AI worker acts on it.

It is not:

- An agent runtime
- A worker router or auto-dispatcher
- A task execution engine
- A replacement for human judgment

Think of it as the security check at an airport gate: it does not fly the plane, but it ensures that what boards is known, bounded, and authorized.

---

## The core problem it solves

When a human sends an AI agent a request like "clean up the old logs" or "update the config", the agent must decide:

- What class of work is this?
- What is the agent allowed to do?
- What must be prevented?
- Does a human need to approve before anything happens?
- Which worker capability is appropriate?

Without a structured preflight, these questions are answered implicitly — by the agent, in context, with no audit trail.

Agent Frontdoor makes these decisions **explicit, inspectable, and testable** before dispatch.

---

## Key fields and their purpose

### `task_class`

A coarse classification of the work being requested. The enum is intentionally small and stable.

| Value | Meaning |
|---|---|
| `READ_ONLY_AUDIT` | Inspect or report; no mutations |
| `STATUS_CLASSIFICATION` | Determine current state of something |
| `DESIGN_REVIEW` | Evaluate a proposal or architecture |
| `IMPLEMENTATION` | Write or change code/config |
| `TEST_VALIDATION` | Run or validate tests |
| `CLEANUP_PLANNING` | Plan a removal or reorganization (not execute) |
| `SSOT_MUTATION` | Modify a source-of-truth file or record |
| `DEPLOYMENT` | Carry a change to a live environment |
| `UNKNOWN` | Cannot be classified; escalate to human |

Scheduler changes are **not** a separate task class. A CI timer change is `SSOT_MUTATION` with `scheduler_risk` in `risk_tags`. This keeps the enum stable while still surfacing the risk.

### `risk_tags`

Zero or more tags that flag elevated-risk properties of this task. Used by human reviewers and gate logic to decide whether human approval is required.

Examples:
- `scheduler_risk` — the change touches timing or recurring job configuration
- `deletion_sensitive` — the task could result in data loss
- `ssot_mutation_risk` — a source-of-truth record will change
- `human_approval_required` — explicit flag that a gate is mandatory

Risk tags are additive. A task can have multiple.

### `predicted_worker`

The capability label(s) that describe what kind of worker should handle this task. One or more values from the allowed set.

**These are capability labels, not product names.** Do not use product or tool names here. The allowed set:

| Label | Meaning |
|---|---|
| `local-classifier-worker` | A local LLM or classifier doing read-only triage |
| `architect-review-worker` | A design or architecture review agent |
| `implementation-worker` | A coding agent making bounded file changes |
| `none-until-approval` | No worker should act until a human approves |

Using capability labels instead of product names keeps the schema portable and prevents vendor lock-in in audit logs.

### `human_gate`

Whether and how human approval is required before action.

| Value | Meaning |
|---|---|
| `none` | No gate. Worker may act. |
| `required` | Human must review and approve before dispatch. |
| `blocking` | Hard stop. No action may proceed until explicit human sign-off. |

When `risk_tags` contains `deletion_sensitive` or `human_approval_required`, `human_gate` must be `required` or `blocking`. This is enforced by the semantic validator.

### `required_manifest`

The type of evidence artifact that must exist before the task may proceed.

| Value | Meaning |
|---|---|
| `none` | No manifest required |
| `dedupe_manifest` | A deduplication plan or scope list |
| `diff_manifest` | A before/after diff showing the proposed change |
| `execution_manifest` | A step-by-step execution plan |
| `approval_manifest` | A documented human approval record |

### `allowed_actions` and `forbidden_actions`

Explicit lists of what the worker may and may not do. Both are required. `allowed_actions` must have at least one entry.

These are natural-language strings describing action types. They are not enforced by the schema at runtime — they are a written contract for auditors and reviewers.

---

## What human authority means

Agent Frontdoor records what a human *requested* and what a worker *is predicted to do*. It does not grant the worker permission to act.

**Human authority lives outside the schema.** The task card is an input to a human review step, not a bypass of it.

Fields like `human_gate: blocking` mean the consuming system must stop and wait. The schema cannot enforce this mechanically — it is a contract between the system and the human operating it.

---

## What the schema does not contain

The following were intentionally excluded from v0.1:

- **Routing logic** — which tool or service receives the task
- **Execution state** — whether the task ran, succeeded, or failed
- **Worker identity** — the specific model, version, or vendor that ran
- **Cost or latency estimates**
- **Retry policy**

These belong in the consuming system, not the preflight schema.
