# Intent Lock README Redesign

**Date:** 2026-08-09
**Status:** Human-approved design
**Selected approach:** Intent Lock-first full reorganization

## Goal

Reorganize the root README for a first-time OSS user so they can quickly
understand the derailment problem, see a deterministic Intent Lock example, and
distinguish the read-only core from the optional runtime hook adapter. Preserve
the complete public contracts already enforced by the README tests.

## Audience and language

- The primary reader is a first-time OSS evaluator deciding whether Agent
  Frontdoor addresses adjacent-task drift in tool-using agents.
- English is the primary reference language for the public OSS surface.
- A concise Japanese summary remains near the top; the README will not duplicate
  the full reference in both languages.
- Existing detailed manuals remain canonical for their narrow topics:
  `docs/INTENT_LOCK.md`, `adapters/README.md`, and `docs/FRIEND_LAB.md`.

## Information architecture

The README will use this order:

1. Preserve the three required opening contract lines, badges, logo, and one-line
   product promise.
2. Explain the problem with a small, privacy-safe example of an exact request
   drifting into an adjacent Cloudflare subsystem.
3. Provide a 30-second pure-Python demo using `derive_lock()` and
   `evaluate_action()`. The demo shows that an unrelated Wrangler action is
   denied while `codex mcp login cloudflare-api` remains target-consistent. It
   evaluates strings only and does not execute either command.
4. Show a two-distribution boundary table:
   - `agent-frontdoor`: pure contracts, validation, drift detection, and Intent
     Lock decisions; read-only and side-effect free.
   - `agent-frontdoor-hooks`: optional Codex and Claude Code lifecycle adapter;
     stores privacy-minimized local state and is not activated by installation.
5. State the safety model: task identity is independent of authority; a matching
   action can still be denied by permission, safety, or human approval gates.
6. Present the core quick start, followed by a clearly separated optional-hook
   path linking to reviewed installation, activation, and removal instructions.
7. Retain the detailed `intake.v0` CLI, schema, gates, boundary-drift, offline
   acceptance, metrics, programmatic API, and uninstall reference without
   repeating the introductory explanation.
8. End with platform limits and audit disclosure, including `CC_UNAUDITED` as a
   status label rather than evidence.

## Content boundaries

- Keep every exact command, field, task class, exit code, blocking category,
  drift family, and safety phrase required by `tests/test_readme.py`.
- Keep the core's four-command CLI unchanged.
- Do not claim a test count, successful external audit, security boundary, live
  activation, publication, deployment, or authority grant.
- Do not include private paths, session identifiers, credentials, tokens, raw
  transcripts, or operator-owned configuration.
- Keep the inert Codex and Claude Code example paths visible, while directing
  activation details to `adapters/README.md`.
- Do not change runtime code, package behavior, live settings, release state, or
  the `CC_UNAUDITED` label.

## Reader flow and failure handling

The first screen answers three questions: what failure this prevents, what it
does not do, and how to observe a decision locally. Every path that could be
misread as activation is paired with an explicit non-activation statement.
Unknown or platform-dependent hook coverage remains described as a limitation;
the README must not convert it into a compatibility promise.

The demo will display decision properties rather than rely on unstable object
representations. Expected values will be derived from the tested public API so a
reader can reproduce them in an editable install.

## Files and scope

- Rewrite and reorganize `README.md`.
- Update `tests/test_readme.py` only where a new structural contract is needed;
  existing safety assertions must not be weakened or removed.
- Do not modify implementation, adapter configuration examples, packaging
  metadata, or live agent configuration.

## Verification

1. Add a README contract assertion for the new Intent Lock-first reader flow
   before rewriting the document.
2. Run the focused README and distribution-boundary tests.
3. Execute the documented pure-Python example and compare its output with the
   README.
4. Run the complete local pytest suite.
5. Inspect the final diff for accidental private data, activation claims,
   duplicated sections, stale version text, and unrelated edits.
6. Run Codex review before closeout.

## Acceptance criteria

- A first-time reader reaches the problem, reproducible demo, and core/adapter
  boundary before the long-form reference.
- The README has one primary explanation of each concept instead of separate
  introductory and English-reference copies.
- Core installation cannot be mistaken for hook activation.
- Intent matching cannot be mistaken for authority.
- All existing README, distribution-boundary, privacy, and full-suite contracts
  pass without loosening their guarantees.
