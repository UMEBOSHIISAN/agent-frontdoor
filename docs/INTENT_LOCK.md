# Intent Lock Design

Date: 2026-08-09
Status: implementation requested by the human
Adoption label: `CODEX_SELF_CONFIDENT_ADOPTED`
Adoption reason: `REPEATED_EXCESSIVE_DERAILMENT`
Root-cause label: `COMPOSITE_CONFIRMED_WITH_MISSING_COMMON_INVARIANT`
CC review: `CC_UNAUDITED`
Training status: `CANDIDATE_ONLY`

## Problem

An agent can replace a literal target with an adjacent product, expand a repair
into project creation, or continue exploring after a direct action fails. In the
regression incident, a `cloudflare-api` MCP OAuth failure expanded into Wrangler
installation and Worker-project discussion. Later human corrections did not
immediately restore the literal command `codex mcp login cloudflare-api`.

The fault was amplified by individually reasonable procedures: product-specific
skills, documentation-first instructions, authentication policy, and design gates.
No shared invariant required every proposed tool call to remain attached to the
literal target.

## Decision

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
prose, failure descriptions, and negated command mentions do not create
exact-command locks. Exact-command comparison collapses only unquoted horizontal
whitespace and preserves newlines, quotes, escapes, and shell operators before
hashing, so the state file does not retain its arguments and a different shell
program cannot compare equal by losing syntax boundaries.

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
Codex Bash raw result with no exit status -> REPORT_REQUIRED
REPORT_REQUIRED + any tool -> deny and require human-facing report
affirmative human correction phrase -> DIRECT_REQUIRED on the previous literal intent
negated/cancellation phrase -> REPORT_REQUIRED hold; never re-enable the action
ambiguous mention of an original request -> no re-lock
new explicit command/error -> new epoch and replacement lock
new substantive unrelated prompt -> prior lock released
```

In `EXACT_COMMAND` mode, only the syntax-preserving exact command is accepted. In
`LITERAL_TARGET` mode, every proposed local tool action must contain all target
tokens. This prevents `cloudflare-api` from becoming an unqualified `wrangler`
action without trying to infer semantic equivalence.

## Adapter boundary

The optional adapter consumes hook JSON from stdin and supports:

- `UserPromptSubmit`: derive, replace, preserve, or release the session lock;
- `PreToolUse`: deny mismatched or uncorrelatable actions with the current
  documented `hookSpecificOutput.permissionDecision = deny` shape, and hash-bind
  an accepted `tool_use_id` to the current epoch;
- Codex `PostToolUse`: process explicit structured status when present; for the
  current raw Bash response, preserve the original result and require a report
  without guessing its exit status;
- Claude Code `PostToolUse`: process successful calls;
- Claude Code `PostToolUseFailure`: require a report after failures;
- `SessionEnd`: remove only the hashed state file for that session.

The adapter does not execute workers, commands, network requests, retries, repairs,
or alternative routes. Multiple-hook authority remains independent; a same-task
allow decision is represented by silence, never an authority-granting `allow`.
Only recognized shell-tool identities may supply the raw command used for an
exact-command comparison; an unrelated function or MCP tool with a coincidental
`command` field retains its full envelope and does not match.
Result events are applied only when their `tool_use_id` matches the digest bound
at `PreToolUse`. A result from an older epoch, even for the same command, is
ignored and cannot release or fail the current lock.

## Platform limits

Codex local hooks cover Bash, unified exec, `apply_patch`, MCP, and most local
function tools, but hosted and specialized paths can bypass that hook path. Claude
Code exposes a broader set of named tools but also has paths outside command-hook
coverage. The implementation is therefore a strong runtime guardrail, not a
security boundary.

Current Codex `ExecCommandToolOutput` serializes only truncated raw output into
the Bash `PostToolUse` response even though the internal object has an exit-code
field. Because that stable hook boundary loses the status, the adapter treats a
raw response as outcome-opaque and requires a human-facing report. It does not
parse success or failure from arbitrary command text.

State reads validate an exact mode-`0700` real directory and an exact
mode-`0600` regular file. Missing paths are distinct from permission, type, and
symlink failures; only genuine absence means no saved lock.

## Required regression cases

1. `cloudflare-api` plus `invalid_grant` creates a literal-target lock.
2. Wrangler discovery, installation, and Worker creation are denied.
3. `codex mcp login cloudflare-api` is target-consistent.
4. An exact natural-language command creates an exact-command lock.
5. An exact-command mismatch is denied even when it names the same vendor.
6. A failed or outcome-opaque matching action moves to `REPORT_REQUIRED`.
7. No later tool call is allowed before the result is reported to the human.
8. Affirmative `最初の依頼` and `do the original request` re-lock the prior intent.
9. A negated, cancelled, or ambiguous correction never re-enables the prior action.
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
