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

The adapter depends on the matching `agent-frontdoor` 0.2 release line. Review
both distributions and the example configuration before trusting the command as
a local hook. The state adapter requires a POSIX operating system; Windows is
rejected explicitly because this release cannot enforce its required `0700` /
`0600` state permissions with the Python standard library.

In a source checkout or sdist, the inert JSON files are under `examples/`. A
wheel installation copies the same files to
`<VIRTUAL_ENV>/share/agent-frontdoor-hooks/examples/`; inspect those copies
before merging any entries into operator-owned configuration.

## Codex example

Merge the event entries from
[`examples/codex-hooks.json`](examples/codex-hooks.json) into the operator-owned
Codex hook configuration. Each entry invokes:

```bash
/ABSOLUTE/PATH/TO/REVIEWED/VENV/bin/agent-frontdoor-hook --platform codex
```

Before merging the example, replace the placeholder
`/ABSOLUTE/PATH/TO/REVIEWED/VENV` with the absolute path to the reviewed virtual
environment created during installation. Do not rely on an interactive shell's
`PATH`; hook processes may receive a different environment.

The example covers `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and
`SessionEnd`. Current Codex Bash `PostToolUse` payloads expose the command output
as a raw string but omit the process exit status. The adapter therefore treats a
matching result without an explicit structured status—whether a raw string or a
content mapping—as outcome-opaque and enters `REPORT_REQUIRED`; it never guesses
success from output text or envelope shape. If a future or synthetic payload
supplies an explicit structured status, that status is honored.

## Claude Code example

Merge the event entries from
[`examples/claude-settings.json`](examples/claude-settings.json) into the
operator-owned Claude Code settings. Each entry invokes:

```bash
/ABSOLUTE/PATH/TO/REVIEWED/VENV/bin/agent-frontdoor-hook --platform claude
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
contains prompt and target hashes, a hash binding the accepted tool-use id to its
lock epoch, and safe opaque display labels, but never the raw prompt, raw command,
raw session ID, raw tool-use ID, tool result, transcript path, OAuth token, network
endpoint, path-like target, or other credential material.
Before binding an accepted action, the adapter atomically creates an empty private
pending marker. A second tool-use id is denied while that claim is active; there
is no retry or wait loop. A matching result, a new user prompt, or `SessionEnd`
releases the marker.
Each session transition is additionally serialized by a hashed private guard
file, so an overlapping old tool hook cannot restore or delete a newer prompt's
intent epoch. The guard contains no session or prompt data and remains as an
opaque mode-`0600` file; the operating system releases its lock if a hook
process exits unexpectedly.

The adapter creates its dedicated state directory with mode `0700`. If an
explicit `--state-dir` already exists, the adapter never changes its permissions:
it accepts only a real directory already at mode `0700` and rejects a shared,
under-permissioned, over-permissioned, or symlinked path. Reads validate the same
root plus a real mode-`0600` state file and distinguish absence from lookup
failure.

Malformed persisted state causes `PreToolUse` to fail closed. `SessionEnd`
removes only the current session's hashed state file. A crashed session can leave
stale state; inspect the exact configured state directory before manually
removing anything.

## What the lock enforces

- A direct exact command permits only the same command syntax, with differences
  limited to unquoted horizontal whitespace. Newlines, quotes, escapes, and shell
  operators remain significant.
- A structured error target permits only actions containing the same literal
  target tokens. Shell control operators, redirections, substitutions,
  parentheses, and embedded newlines are denied in target mode, preventing an
  unrelated command from sharing the same tool invocation.
- A matching action must have a non-empty `tool_use_id`; its result is accepted
  only for that id and lock epoch. Late results from older epochs are ignored.
- A failed matching action enters `REPORT_REQUIRED`; the next tool is denied
  until the result is surfaced to the human.
- A Codex result without explicit structured status also enters
  `REPORT_REQUIRED`, whether it is a raw string or content mapping, because the
  outcome is unknown. The original result remains visible for accurate reporting.
- An explicit negation of the previous request never re-enables it; tool use is
  held until the agent responds to the human.
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
