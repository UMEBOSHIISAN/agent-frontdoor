# Closeout Memo — agent-frontdoor v0.1 Skeleton

Date: 2026-06-29
Status: **INTERNAL READY — not public-release-ready**

---

## Summary

This memo closes the parallel OS improvement / OSS extraction workplan (4-task session).
It records what was built, what was deliberately excluded, and what remains before any public release.

---

## Task Status

### Task 1: Boundary Decision — CLOSED

**Objective:** Identify which files from the internal routing system are extractable without leaking private context.

**CONFIRMED:**
- `routing_classifier.py` uses stdlib only (re, dataclasses, typing). No internal dependencies.
- `routing_intake.v0.2/schema/routing_intake.v0.2.json` is clean; uses capability labels.
- Original fixtures contained contamination: 2 business-specific scenarios, 6 fixtures with internal worker names.
- `routing_runner.py` is heavily UMEBOSHI-specific. Excluded from OSS v0.
- `learning_ledger_v0.md` contains internal path references. Excluded from OSS v0.

**Decisions (all HUMAN_APPROVED):**
- OSS staging location: `~/Workspace/oss_staging/agent-frontdoor/` (not inside RAG)
- Public examples: synthetic only. No EC/order/shipment/coupon/SKU scenarios.
- `task_class` enum: OSS SSOT. `SCHEDULER_PROCESS` excluded; use `SSOT_MUTATION + risk_tags: [scheduler_risk]`.
- `classifier.py` extraction: HOLD for v0. Not included.
- Language: English only for v0.

**CO Audit result:** PASS (after correction of 2 bugs in initial boundary mapping)

---

### Task 2: Lane A (Internal OS Design) — DONE

**Objective:** Record OS-level design decisions that informed the OSS extraction but stay internal.

**CONFIRMED:**
- Fixture `predicted_worker` mapping from internal names to capability labels was finalized:
  - `local-llm-audit` → `local-classifier-worker`
  - `CC-review`, `CC-advisory`, `CC-design` → `architect-review-worker`
  - `Codex` → `implementation-worker`
  - `none-until-approval` → `none-until-approval`
- Confirmed per-fixture `predicted_worker` values (8 fixtures, all corrected).
- Q-new decisions locked: classifier extraction hold, English-only v0, scheduler as risk_tag.

**Status:** Design decisions recorded and applied. No further Lane A deliverables required for v0.1.

---

### Task 3: Lane B (agent-frontdoor v0.1 Skeleton) — DONE

**Objective:** Create a clean, private-term-free OSS skeleton from the extractable components.

**CONFIRMED — files created:**

```
agent-frontdoor/
├── schema/
│   └── agent-frontdoor.v0.1.json     JSON Schema (Draft 7)
├── fixtures/
│   ├── valid_cleanup_planning.json
│   ├── valid_delete_archive_request.json
│   ├── valid_design_review.json
│   ├── valid_implementation.json
│   ├── valid_read_only_audit.json
│   ├── valid_ssot_mutation.json
│   ├── valid_status_classification.json
│   └── valid_unknown_escalation.json
├── docs/
│   ├── concepts.md
│   └── examples.md
├── README.md
└── tests/
    ├── test_schema_validation.py
    └── test_negative_cases.py
```

**Test result:** `pytest 44/44 PASS`

**Private-term scan result:** `0 hits`
- Scan covered: all `.json`, `.py`, `.md` files
- Terms checked: xops, UMEBOSHI, WooCommerce, Discord, internal paths, CC-review, Codex, local-llm-audit, and 30+ others

**Key design choices:**
- `predicted_worker` validated via **allowlist** (not denylist). Unknown names are rejected.
  `ALLOWED_WORKERS = {local-classifier-worker, architect-review-worker, implementation-worker, none-until-approval}`
- `semantic_validate()` enforces 3 rules JSON Schema cannot express: allowlist, deletion gate, scheduler risk.
- Semantic validator is separate from JSON Schema validator. Schema and policy are not mixed.

**Explicit exclusions (v0.1 scope boundary):**
- No `classifier.py`
- No CLI
- No runner or dispatcher
- No worker execution
- No routing logic
- No external integrations (GitHub, Discord, messaging)
- No vendor or product-specific worker names in any file

---

### Task 4: Lane C (Research Study Design) — DONE (scope closed by human decision)

Human decision: Lane C = routing_trial measurement only at this phase. No separate research deliverable required for v0.1 skeleton closeout.

---

## What agent-frontdoor v0.1 Is

A **preflight schema** — not an agent runtime, not a worker router, not an execution engine.

It converts a raw human request into a bounded, reviewable task card **before any worker acts**.

The schema is the deliverable. Nothing executes.

---

## What it is NOT (scope protection record)

These were explicitly not built and must not be added without a new design gate:

| Not built | Reason |
|---|---|
| Classifier | Excluded from v0 by HUMAN_APPROVED decision |
| CLI | Not in scope. v0.1 = schema only |
| Worker runner | Execution lives in the consuming system, not here |
| Auto-router | Routing is the consuming system's responsibility |
| Agent runtime | Would destroy the "preflight" positioning |
| Vendor integrations | Premature; adds coupling before the schema is stable |

---

## Remaining Blockers Before Public Release

### CONFIRMED blockers

1. **LICENSE** — no license file exists yet. Required before any public repo.
2. **Package metadata** — no `pyproject.toml`. Needed if distributed as a Python package (optional for schema-only use).
3. **README external clarity** — not yet reviewed by someone unfamiliar with the project. "3-minute clarity" unverified.
4. **Final scrub audit** — scan term list may have gaps. An independent scrub is needed.
5. **Repo naming decision** — `agent-frontdoor` is a working name. Final public name not decided.

### UNKNOWN (judgment required before release)

- Whether the README communicates the schema-only value proposition clearly to external readers
- Whether the `docs/examples.md` scenarios are neutral enough (no implied industry or domain)
- Whether v0.1 needs a CHANGELOG or CONTRIBUTING guide before public release
- Whether a `pyproject.toml` is needed for schema-only distribution

### NOT a blocker (resolved)

- Private terms: 0 hits ✅
- Internal paths: 0 hits ✅
- Test coverage: 44/44 PASS ✅
- Allowlist enforcement: in place ✅
- Fixture contamination: all corrected ✅

---

## Current State

```text
agent-frontdoor v0.1 skeleton: INTERNAL READY
public release: NOT YET

Next recommended task:
  Release readiness audit (README 3-min review, LICENSE, final scrub, repo naming)
  → private local git repo first
  → public GitHub only after release readiness PASS
```

---

## What Not To Do Next

Adding features before release readiness is confirmed:
- No classifier
- No CLI
- No runner
- No auto-routing
- No GitHub Actions CI (premature)
- No package publishing

Premature feature addition would turn a clean schema OSS into a re-implementation of the internal system.
