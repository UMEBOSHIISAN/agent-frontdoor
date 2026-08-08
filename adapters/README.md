# Agent Frontdoor Hooks

`agent-frontdoor-hooks` is an optional sibling distribution for applying Agent
Frontdoor's pure `intent-lock.v1` decisions to local Codex and Claude Code hook
events. It writes only privacy-minimized, session-scoped lock state. It does not
run the requested command, call a worker, access the network, retry a failure, or
grant authority.

The core `agent-frontdoor` package remains read-only. Installing this adapter
does not edit any Codex or Claude Code settings and does not activate a hook.

## Install in an isolated environment

From a reviewed source checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -e adapters
```

The adapter depends on the matching `agent-frontdoor` 0.1 release line. Review
both distributions and the example configuration before trusting the command as
a local hook.

## Codex example

Merge the event entries from
[`examples/codex-hooks.json`](examples/codex-hooks.json) into the operator-owned
Codex hook configuration. Each entry invokes:

```bash
agent-frontdoor-hook --platform codex
```

The example covers `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and
`SessionEnd`. Codex reports command results through `PostToolUse`, so the adapter
examines explicit result fields to distinguish success from failure.

## Claude Code example

Merge the event entries from
[`examples/claude-settings.json`](examples/claude-settings.json) into the
operator-owned Claude Code settings. Each entry invokes:

```bash
agent-frontdoor-hook --platform claude
```

The example also covers `PostToolUseFailure`, which Claude Code emits separately
from successful `PostToolUse` events.

Do not replace an existing settings file with an example wholesale. Existing
hooks may enforce independent security or authority rules and must be preserved.
The shipped examples are inert files; activation is always a separate operator
decision.

## State and privacy

By default, state is stored below:

```text
~/.local/state/agent-frontdoor/intent-lock
```

Set `AGENT_FRONTDOOR_STATE_DIR` or pass `--state-dir` to select an explicit
alternative. The directory is restricted to mode `0700`; atomically written
state files use mode `0600`. Filenames are SHA-256 digests of session IDs. State
contains prompt and target hashes plus safe display labels, but never the raw
prompt, raw command, raw session ID, tool result, transcript path, OAuth token,
or other credential material.

Malformed persisted state causes `PreToolUse` to fail closed. `SessionEnd`
removes only the current session's hashed state file. A crashed session can leave
stale state; inspect the exact configured state directory before manually
removing anything.

## What the lock enforces

- A direct exact command permits only the normalized exact command.
- A structured error target permits only actions containing the same literal
  target tokens.
- A failed matching action enters `REPORT_REQUIRED`; the next tool is denied
  until the failure is surfaced to the human.
- A same-intent match emits no allow decision. Separate permission and authority
  hooks remain independent and may still deny the action.

This is a task-identity guardrail, not a security boundary. Local hooks do not
necessarily cover hosted or specialized execution paths. Platform behavior can
also change, so compare the examples with the current official hook
documentation before activation.

## Uninstall or deactivate

First remove only the Agent Frontdoor entries from the operator-owned Codex or
Claude Code hook configuration. Preserve unrelated hooks. Then uninstall the
adapter from the environment where it was installed:

```bash
.venv/bin/python -m pip uninstall -y agent-frontdoor-hooks
```

Uninstalling the Python package does not edit settings and does not delete
persisted state. Any manual state cleanup remains an explicit operator action.

## Audit status

The shared core and platform fixtures are tested together. The current adoption
record is `CODEX_SELF_CONFIDENT_ADOPTED` because of
`REPEATED_EXCESSIVE_DERAILMENT`. Independent Claude/CC review remains
`CC_UNAUDITED`; that label is disclosure, not evidence of approval or failure.
