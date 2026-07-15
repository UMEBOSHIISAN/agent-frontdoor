# Examples

> Historical v0.1 reference only. These examples do not conform to the working
> v0 schema. Use `fixtures/positive/` for current examples.

All examples use synthetic scenarios. No real product names, internal paths, or organization-specific terms appear in this file.

---

## Example 1: Read-only audit

**Request:** "Check the log directory and report any files older than 30 days."

This is read-only. No changes, no deletions — just inspection and reporting.

```json
{
  "schema": "agent-frontdoor.v0.1",
  "task_id": "20260101_example_audit",
  "timestamp": "2026-01-01T09:00:00Z",
  "input_summary": "Check the log directory and report any files older than 30 days",
  "task_class": "READ_ONLY_AUDIT",
  "risk_tags": [],
  "predicted_worker": ["local-classifier-worker"],
  "predicted_confidence": "high",
  "allowed_actions": ["read_directory_listing", "read_file_metadata", "produce_report"],
  "forbidden_actions": ["delete_files", "move_files", "write_files"],
  "required_evidence": [],
  "required_manifest": "none",
  "human_gate": "none",
  "actual_worker": null,
  "routing_deviation": false,
  "boundary_drift": false,
  "boundary_drift_reason": null,
  "unknowns": [],
  "assumptions": ["log directory path is known by the consuming system"],
  "next_safe_step": "Read directory listing and produce age report",
  "ledger_note": "Read-only. No gate required."
}
```

**Why `human_gate: none`?** The task cannot mutate anything. The `forbidden_actions` list is the first line of defense. A human reviewer does not need to pre-approve a read.

---

## Example 2: Deletion request with blocking gate

**Request:** "Delete the archived files from the backlog folder."

Deletion is irreversible. Even if the request is clear, a preflight should halt before execution.

```json
{
  "schema": "agent-frontdoor.v0.1",
  "task_id": "20260101_example_delete",
  "timestamp": "2026-01-01T09:15:00Z",
  "input_summary": "Delete the archived files from the backlog folder",
  "task_class": "CLEANUP_PLANNING",
  "risk_tags": ["deletion_sensitive", "human_approval_required"],
  "predicted_worker": ["architect-review-worker"],
  "predicted_confidence": "medium",
  "allowed_actions": ["read_directory_listing", "produce_deletion_candidate_list"],
  "forbidden_actions": ["delete_files", "move_files", "archive_files"],
  "required_evidence": ["deletion_candidate_list", "human_approval"],
  "required_manifest": "approval_manifest",
  "human_gate": "blocking",
  "actual_worker": null,
  "routing_deviation": false,
  "boundary_drift": false,
  "boundary_drift_reason": null,
  "unknowns": ["whether any archived files are still referenced by active processes"],
  "assumptions": [],
  "next_safe_step": "Produce candidate deletion list only. Human reviews and approves before any deletion.",
  "ledger_note": "Deletion request. Blocking gate: human must confirm scope before worker acts."
}
```

**Why `CLEANUP_PLANNING` and not a deletion class?** v0.1 separates *planning* from *execution*. The worker produces a candidate list; a human decides whether to proceed. The actual deletion (if it happens) would be a separate `SSOT_MUTATION` card with its own gate.

**Why `blocking` instead of `required`?** `deletion_sensitive` in `risk_tags` means the risk of proceeding without approval is higher than the cost of stopping. `blocking` communicates to the consuming system: do not dispatch any worker for the execution phase until a human has explicitly signed off.

---

## Example 3: Scheduler-related config change

**Request:** "Update the nightly report pipeline to run at 3am instead of midnight."

This is a scheduler configuration change. The `task_class` is `SSOT_MUTATION` (a source-of-truth file changes), and `scheduler_risk` must appear in `risk_tags`.

```json
{
  "schema": "agent-frontdoor.v0.1",
  "task_id": "20260101_example_schedule",
  "timestamp": "2026-01-01T10:00:00Z",
  "input_summary": "Update the nightly report pipeline to run at 3am instead of midnight",
  "task_class": "SSOT_MUTATION",
  "risk_tags": ["scheduler_risk", "ssot_mutation_risk", "human_approval_required"],
  "predicted_worker": ["architect-review-worker"],
  "predicted_confidence": "high",
  "allowed_actions": ["read_current_schedule_config", "produce_proposed_diff"],
  "forbidden_actions": ["apply_schedule_change", "restart_scheduler", "edit_config_directly"],
  "required_evidence": ["current_config_snapshot", "proposed_diff", "human_approval"],
  "required_manifest": "approval_manifest",
  "human_gate": "blocking",
  "actual_worker": null,
  "routing_deviation": false,
  "boundary_drift": false,
  "boundary_drift_reason": null,
  "unknowns": ["whether downstream jobs depend on the midnight start time"],
  "assumptions": [],
  "next_safe_step": "Read current config and produce diff. Do not apply. Human applies after review.",
  "ledger_note": "Schedule change. Blocking gate. Human applies; worker proposes only."
}
```

**Why is `SCHEDULER_PROCESS` not a valid `task_class`?** Scheduler management is a risk dimension, not a work classification. The work here is still an SSOT mutation — it is a config file change. The *risk* is captured in `risk_tags: [scheduler_risk]`. Keeping the enum small and stable reduces classifier drift.

---

## Example 4: Unknown — escalate to human

**Request:** "Something is off with the weekly numbers."

The request is ambiguous. No worker can act safely without more information.

```json
{
  "schema": "agent-frontdoor.v0.1",
  "task_id": "20260101_example_unknown",
  "timestamp": "2026-01-01T11:00:00Z",
  "input_summary": "Something is off with the weekly numbers",
  "task_class": "UNKNOWN",
  "risk_tags": ["stale_authority_risk", "human_approval_required"],
  "predicted_worker": ["none-until-approval"],
  "predicted_confidence": "low",
  "allowed_actions": ["ask_clarifying_question", "produce_diagnosis_candidates"],
  "forbidden_actions": [
    "take_corrective_action",
    "modify_any_files",
    "escalate_autonomously"
  ],
  "required_evidence": ["clarified_task_description"],
  "required_manifest": "none",
  "human_gate": "required",
  "actual_worker": null,
  "routing_deviation": false,
  "boundary_drift": false,
  "boundary_drift_reason": null,
  "unknowns": [
    "what 'the weekly numbers' refers to",
    "what 'off' means in this context",
    "which system or file to look at"
  ],
  "assumptions": [],
  "next_safe_step": "Ask human for clarification. Do not act until scope is confirmed.",
  "ledger_note": "Task is unclassifiable. Escalate to human before any worker dispatch."
}
```

**Why `none-until-approval` in `predicted_worker`?** When the task cannot be classified, dispatching any worker risks acting on wrong assumptions. The safest predicted worker is "no one, until a human confirms what to do."

---

## Routing deviation and boundary drift

These two optional boolean fields support post-hoc audit, not preflight enforcement.

- `routing_deviation: true` — the actual worker differed from `predicted_worker`. Record why in `substitution_reason`.
- `boundary_drift: true` — the worker took actions outside `allowed_actions`. Record why in `boundary_drift_reason`.

During preflight creation, both default to `false` and `actual_worker` is `null`. They are filled in after the task completes by the consuming system.

```json
{
  "actual_worker": "implementation-worker",
  "substitution_reason": "local-classifier-worker was unavailable; implementation-worker used in read-only mode",
  "routing_deviation": true,
  "boundary_drift": false,
  "boundary_drift_reason": null
}
```

---

## What makes a good `input_summary`

The `input_summary` is a human-readable description of the raw request. Guidelines:

- One sentence, past-tense or infinitive
- Describe the request as given, not as interpreted
- Do not include decisions made during classification (those belong in other fields)
- Do not include internal system names or paths

Good:
> "Delete the archived files from the backlog folder"
> "Check the log directory and report files older than 30 days"

Avoid:
> "CLEANUP_PLANNING task for /var/log/app/archive/ using rm -rf" ← classification and paths mixed in
