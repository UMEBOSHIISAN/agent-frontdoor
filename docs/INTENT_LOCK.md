# Intent Lock Reference

Intent Lock addresses a general failure mode: an agent can replace a literal
target with an adjacent product, expand a bounded repair into project creation,
or continue exploring after a direct action fails. Individually reasonable
procedures do not prevent that drift unless every proposed tool call remains
attached to the literal target.

This reference describes the deterministic contract and adapter boundary. See
[Architecture](https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/docs/ARCHITECTURE.md)
for the full pipeline,
[Evidence](https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/docs/EVIDENCE.md)
for the published test scope,
[Troubleshooting](https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/docs/TROUBLESHOOTING.md)
for non-escalating recovery, and the
[public adapter guide](https://github.com/UMEBOSHIISAN/agent-frontdoor/blob/main/adapters/README.md)
for a non-live evaluation path.

## Boundary

Agent Frontdoor gains a pure, deterministic `intent-lock.v1` contract. It derives
a privacy-minimized lock from an exact command or structured error target, evaluates
a proposed action against that lock, and performs immutable state transitions.

The existing `agent-frontdoor` package remains read-only and side-effect free. Hook
state, filesystem writes, and lifecycle-specific JSON are isolated in a separately
packaged optional adapter named `agent-frontdoor-hooks`.

```text
human prompt
  -> pure intent-lock derivation
  -> same-task decision
  -> independent authority gate
  -> executor
  -> result transition
```

Intent matching never grants authority. If a separate authority hook blocks the
same-task action, the lock remains active. The agent must report the block; it may
not substitute another subsystem.

## Core contract

`intent-lock.v1` contains:

- an integer `intent_epoch`;
- the SHA-256 of the source prompt;
- phase `DIRECT_REQUIRED`, `REPORT_REQUIRED`, or `RELEASED`;
- mode `EXACT_COMMAND` or `LITERAL_TARGET`;
- an optional normalized-command SHA-256;
- SHA-256 digests for required target tokens;
- safe display labels for human-readable denial messages;
- an optional SHA-256 digest binding an accepted tool-use id to one lock epoch.

The contract never stores the raw prompt, raw session id, transcript path, tool
response, or OAuth material. The adapter hashes the session id for the state
filename and writes only validated contract JSON.

## Deterministic derivation

An exact-command lock is created from a shell-looking command in a standalone
fenced block, a fenced block after an affirmative run directive, standalone
inline code, inline code following an explicit affirmative run directive, an
equivalently bounded `$`-prefixed line, or a recognized CLI command followed by a
bounded Japanese request suffix such as `してや`. Free prose, trailing English
prose, failure descriptions, and command mentions negated before or after their
code span do not create
exact-command locks. Exact-command comparison collapses only unquoted horizontal
whitespace and preserves newlines, quotes, escapes, and shell operators before
hashing. Commands containing heredocs or nested shell expansions are compared with
all horizontal whitespace preserved because their bodies have separate quoting
rules and may be data rather than shell-token whitespace. The state file therefore
does not retain command arguments, and a different shell program, expansion, or
heredoc payload cannot compare equal by losing syntax boundaries.

A literal-target lock is created from structured error forms such as:

- `client for <target>`;
- `server <target>`;
- `component <target>`;
- backticked identifiers near `failed`, `error`, or `invalid`.

Secret-context, known credential-prefix, high-entropy credential-shaped, network,
and path-like target labels are never retained for display. Only simple opaque
labels made from letters, digits, `_`, and `-` are displayable. One-way digests
may still bound the current action without persisting raw target material. A
prompt that yields no deterministic evidence creates no lock rather than
inventing one.

## State machine

```text
new exact command/error -> DIRECT_REQUIRED
matching exact command with explicit success succeeds -> RELEASED
matching tool action fails -> REPORT_REQUIRED
Codex result with no explicit structured status -> REPORT_REQUIRED
REPORT_REQUIRED + any tool -> deny and require human-facing report
affirmative correction while DIRECT_REQUIRED -> new DIRECT_REQUIRED epoch
affirmative correction while REPORT_REQUIRED -> preserve the report hold
negated/cancellation phrase -> REPORT_REQUIRED hold; never re-enable the action
REPORT_REQUIRED + same target/action or bounded related-result evidence -> preserve
REPORT_REQUIRED + genuinely different explicit command/error -> replacement lock
REPORT_REQUIRED + meaningful unrelated prompt, even a short one -> prior lock released
```

During `REPORT_REQUIRED`, related evidence is bounded to a prompt-token digest
matching the stored target digests, strong prior-result terms such as `failed`,
`problem`, `issue`, or `happened`, and short acknowledgements or bounded deictic
references such as `What about that?`. Digest comparison also covers targets
that are intentionally hidden from display. Affirmative correction and
standalone continuation wording preserve the same report hold. Generic `work`,
`report`, `why`, or `なぜ`, and string length alone are not related evidence.
Therefore short unrelated tasks such as `Fix docs.` and `Run tests.` release the
hold, while a genuinely different explicit command or structured error replaces
it with a new lock. The same explicit action or target never bypasses the required
report by creating a new epoch.

Both identity modes first require a recognized shell-action context. A caller
marked with `evaluate_action(..., shell_action=False)`, or a standalone parsed
JSON object or array, is denied with `non_shell_action` before exact-command or
literal-target comparison. JSON text inside an actual shell-command argument
remains ordinary command text. In `EXACT_COMMAND` mode, only the syntax-preserving
exact command is then accepted. In `LITERAL_TARGET` mode, the command must contain
all target tokens as shell arguments. A `#` starts a comment only when it begins
an unquoted shell word. An escaped or mid-word `#`, or a `#` inside a quoted
argument, remains part of that argument. Other non-shell envelopes and inert
payload text likewise never satisfy the identity check. This prevents
`cloudflare-api` from becoming an unqualified `wrangler` action without trying to
infer semantic equivalence. Target-mode actions must also be one shell command:
control operators, redirections, substitutions, parentheses, and embedded
newlines are rejected even when the target token is present.

## Adapter boundary

The optional adapter consumes hook JSON from stdin and supports:

- `UserPromptSubmit`: derive, replace, preserve, or release the session lock;
- `PreToolUse`: deny mismatched or uncorrelatable actions with the current
  documented `hookSpecificOutput.permissionDecision = deny` shape, and hash-bind
  an accepted `tool_use_id` to the current epoch;
- Codex `PostToolUse`: process explicit structured status when present; for raw
  strings or mappings without status, preserve the original result and require a
  report without guessing the outcome;
- Claude Code `PostToolUse`: process successful calls;
- Claude Code `PostToolUseFailure`: require a report after failures;
- `SessionEnd`: remove only the hashed state file for that session.

The adapter does not execute workers, commands, network requests, retries, repairs,
or alternative routes. Multiple-hook authority remains independent; a same-task
allow decision is represented by silence, never an authority-granting `allow`.
Only recognized shell-tool identities may supply the raw command used for exact-
command or literal-target comparison; an unrelated function or MCP tool with a
coincidental `command` field retains its full envelope and does not match. Shell-
tool names must be ASCII, and only ASCII letter case is normalized; Unicode or
confusable names are never trusted as shell tools.
Result events are applied only when their `tool_use_id` matches the digest bound
at `PreToolUse`. A result from an older epoch, even for the same command, is
ignored and cannot release or fail the current lock.
An empty private marker is created with an atomic exclusive create before the
binding is saved. While that marker and pending digest exist, a different tool-use
id is denied. There is no retry loop; a competing or stale claim fails closed until
the matching result, a new user prompt, or `SessionEnd` releases it.

## Platform limits

Codex local hooks cover Bash, unified exec, `apply_patch`, MCP, and most local
function tools, but hosted and specialized paths can bypass that hook path. Claude
Code exposes a broader set of named tools but also has paths outside command-hook
coverage. The implementation is therefore a strong runtime guardrail, not a
security boundary.

The adapter currently assumes that Codex `ExecCommandToolOutput` serializes only
truncated raw output into the Bash `PostToolUse` response even though the internal
object has an exit-code field. Under that assumption, a response without explicit
structured status is outcome-opaque and requires a human-facing report; the
adapter does not parse success or failure from arbitrary command text or mapping
shape. Check this assumption against the current official hook documentation and
the synthetic adapter smoke test before activation.

State reads validate an exact mode-`0700` real directory and an exact
mode-`0600` regular file. Missing paths are distinct from permission, type, and
symlink failures; only genuine absence means no saved lock.
The optional state adapter requires POSIX permission and advisory-lock semantics.
Windows is rejected explicitly instead of pretending that POSIX mode checks
provide an equivalent privacy boundary there.
State failures remain fail-closed but expose only the bounded public code and
message `INTENT_LOCK_STATE_ERROR: Intent Lock state is unavailable; the event is
blocked.` Raw exception and operator-path text is never emitted in a hook result,
stdout, or stderr.

## Required regression cases

1. `cloudflare-api` plus `invalid_grant` creates a literal-target lock.
2. Wrangler discovery, installation, and Worker creation are denied.
3. `codex mcp login cloudflare-api` is target-consistent.
4. An exact natural-language command creates an exact-command lock.
5. An exact-command mismatch is denied even when it names the same vendor.
6. A failed or outcome-opaque matching action moves to `REPORT_REQUIRED`.
7. No later tool call is allowed before the result is reported to the human.
8. Affirmative `最初の依頼` and `do the original request` re-lock a direct prior
   intent but cannot bypass an active `REPORT_REQUIRED` hold.
9. A negated, cancelled, or ambiguous correction preserves a blocking lock and
   never re-enables the prior action.
10. A stale result from an older epoch cannot mutate the current lock.
11. Hook state contains no raw prompt, session id, command, or tool-use id.
12. Codex and Claude Code fixtures produce the same intent decision despite their
    different result-event shapes.

## Rollout boundary

This repository may ship the pure core, optional hook distribution, examples, and
tests. Installing the adapter, editing a live `config.toml` or `settings.json`,
trusting a hook, and publishing a release are separate operator actions. They do not
become authorized merely because the OSS implementation exists.

## Primary references

- OpenAI Codex hooks: <https://developers.openai.com/codex/hooks/>
- OpenAI Codex Bash hook response implementation:
  <https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/context.rs>
- Claude Code hooks: <https://code.claude.com/docs/en/hooks>

No independent security audit has been completed.
