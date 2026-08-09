# Agent Frontdoor Hooks

`agent-frontdoor-hooks` is an optional sibling distribution for applying Agent
Frontdoor's pure `intent-lock.v1` decisions to local Codex and Claude Code hook
events. It writes only privacy-minimized, session-scoped lock state. It does not
run the requested command, call a worker, access the network, retry a failure, or
grant authority.

The core `agent-frontdoor` package remains read-only. Installing this adapter
does not edit any Codex or Claude Code settings and does not activate a hook.

## Install in an isolated environment

The adapter depends on the matching unreleased `agent-frontdoor` 0.2 source
line. Review both distributions and the example configuration before trusting
the command as a local hook.

### Monorepo checkout

From the root of a reviewed monorepo checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install -e adapters
```

The inert configuration files for this flow are under `adapters/examples/`.

### Unpacked adapter sdist

An unpacked standalone adapter sdist does not contain the core. Before
installing the adapter, obtain and review the matching core `agent-frontdoor` 0.2.0
artifact or local source path. This standard form names the reviewed core
sdist explicitly, installs it first, and then installs the adapter from the
current unpacked directory without asking pip to resolve a different core:

```bash
reviewed_core_sdist="/ABSOLUTE/PATH/TO/REVIEWED/agent_frontdoor-0.2.0.tar.gz"
test -f "$reviewed_core_sdist"
python3 -m venv .venv
.venv/bin/python -m pip install "$reviewed_core_sdist"
.venv/bin/python -m pip install --no-deps .
```

The core command may use configured package indexes for its runtime and build
requirements. The adapter command still builds the reviewed local directory;
`--no-deps` prevents dependency resolution from substituting another core.

#### Bounded offline form

Use this form only with a reviewed isolated environment that already contains
pip, `setuptools>=77`, and the core runtime dependency `jsonschema>=4`. These
commands use only the two reviewed local sources: `--no-index` prohibits index
access, `--no-deps` disables dependency resolution, and
`--no-build-isolation` prevents a build environment from fetching requirements.
Missing prerequisites are a hard stop; do not remove the flags to continue.

```bash
reviewed_core_sdist="/ABSOLUTE/PATH/TO/REVIEWED/agent_frontdoor-0.2.0.tar.gz"
offline_python="/ABSOLUTE/PATH/TO/PREPROVISIONED/OFFLINE/VENV/bin/python"
test -f "$reviewed_core_sdist"
test -x "$offline_python"
"$offline_python" -m pip install --no-index --no-deps --no-build-isolation "$reviewed_core_sdist"
"$offline_python" -m pip install --no-index --no-deps --no-build-isolation .
```

The inert configuration files for this standalone flow are under `examples/`.

For either flow, the state adapter requires a POSIX operating system.
Windows is rejected explicitly because this source line cannot enforce its
required mode `0700` / mode `0600` state permissions with the Python standard
library.

Wheel installation copies the same inert files to
`<VIRTUAL_ENV>/share/agent-frontdoor-hooks/examples/`; inspect those copies
before merging any entries into operator-owned configuration.

## Non-live smoke test

Run this sequence only from the reviewed source checkout and before any live
activation. It uses a disposable state directory.
The sequence does not modify operator-owned settings. Each synthetic JSON object
passes to the hook on stdin. The hook evaluates each
embedded `tool_input.command` as data; this procedure never runs those commands.

```bash
adapter_state_dir="$(mktemp -d)"
chmod 700 "$adapter_state_dir"
hook_bin=".venv/bin/agent-frontdoor-hook"
test -x "$hook_bin"

printf '%s\n' '{"session_id":"adapter-smoke-codex","turn_id":"turn-1","hook_event_name":"UserPromptSubmit","prompt":"MCP client for `cloudflare-api` failed to start: invalid_grant: Grant not found"}' | "$hook_bin" --platform codex --state-dir "$adapter_state_dir"
printf '%s\n' '{"session_id":"adapter-smoke-codex","turn_id":"turn-1","hook_event_name":"PreToolUse","tool_name":"Bash","tool_use_id":"tool-1","tool_input":{"command":"npx wrangler whoami"}}' | "$hook_bin" --platform codex --state-dir "$adapter_state_dir"
printf '%s\n' '{"session_id":"adapter-smoke-codex","turn_id":"turn-1","hook_event_name":"PreToolUse","tool_name":"Bash","tool_use_id":"tool-2","tool_input":{"command":"codex mcp login cloudflare-api"}}' | "$hook_bin" --platform codex --state-dir "$adapter_state_dir"
printf '%s\n' '{"session_id":"adapter-smoke-codex","turn_id":"turn-1","hook_event_name":"PostToolUse","tool_name":"Bash","tool_use_id":"tool-2","tool_input":{"command":"codex mcp login cloudflare-api"},"tool_response":"Error: server not found"}' | "$hook_bin" --platform codex --state-dir "$adapter_state_dir"
printf '%s\n' '{"session_id":"adapter-smoke-codex","turn_id":"turn-1","hook_event_name":"PreToolUse","tool_name":"Bash","tool_use_id":"tool-3","tool_input":{"command":"rg cloudflare-api ."}}' | "$hook_bin" --platform codex --state-dir "$adapter_state_dir"
printf '%s\n' '{"session_id":"adapter-smoke-codex","turn_id":"turn-1","hook_event_name":"SessionEnd"}' | "$hook_bin" --platform codex --state-dir "$adapter_state_dir"
```

The six results demonstrate the following deterministic sequence:

1. `UserPromptSubmit` creates a literal-target lock for `cloudflare-api` and
   prints `INTENT_LOCK_ACTIVE`.
2. `PreToolUse` for `npx wrangler whoami` returns a `permissionDecision` of
   `deny` while exiting `0`.
3. The matching `codex mcp login cloudflare-api` action exits `0` with empty
   stdout. Silence means only that the action has the same intent; it does not
   grant permission or authority and it does not execute the command.
4. The status-less Codex `PostToolUse` response prints
   `INTENT_LOCK_REPORT_REQUIRED` because the outcome is unknown.
5. The later `rg cloudflare-api .` call returns a deny decision pending a human
   report, again with exit status `0`.
6. `SessionEnd` removes only the synthetic session state and prints nothing.

The outer `fixtures/intent-lock/*_sequence.json` documents are multi-event test
wrappers, not valid one-shot hook stdin payloads. Feed only one event object per
invocation as above.

Before the `SessionEnd` invocation, an optional privacy check can confirm that
state contains no raw session, prompt, command, or tool-use strings:

```bash
rg -n 'adapter-smoke-codex|MCP client for|npx wrangler whoami|codex mcp login cloudflare-api|rg cloudflare-api \.|tool-[123]' "$adapter_state_dir"
```

No matches are expected. A safe display label such as `cloudflare-api` may still
appear by itself as documented below. After inspection, leave physical deletion
of the disposable directory as a separate, explicit operator decision.

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
`SessionEnd`. The adapter assumes that Codex Bash `PostToolUse` payloads expose
the command output as a raw string but omit the process exit status. Under that
assumption, a matching result without an explicit structured status—whether a
raw string or a content mapping—is outcome-opaque and enters `REPORT_REQUIRED`;
the adapter never guesses success from output text or envelope shape. If a
future or synthetic payload supplies an explicit structured status, that status
is honored. Check this assumption against the current official Codex hook
documentation before activation.

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

Intent Lock compares an action with a deterministic exact-command or
literal-target lock, binds an accepted tool-use id to the current epoch, and
requires a human-facing report after a failed or outcome-opaque result. It never
treats identity with the original intent as permission or authority. The
canonical phase, matching, transition, and correlation rules are in the
[Intent Lock reference](https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/docs/INTENT_LOCK.md).

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

## Security disclosure

No independent security audit has been completed.
