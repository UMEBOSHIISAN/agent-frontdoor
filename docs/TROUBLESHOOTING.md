# Troubleshooting

Agent Frontdoor and its optional adapter fail closed. Recovery means stop,
report, inspect, or return the decision to the human. In recovery, do not retry, do not switch to an adjacent subsystem, or change operator-owned settings. A diagnosis does not grant authority.

## Core results

| Result | Meaning | Safe recovery |
| --- | --- | --- |
| `ERROR`, exit `2` | Input was unreadable or malformed JSON. | Stop and inspect the exact local input with the human; provide a corrected input only through the normal review path. |
| `INVALID`, exit `1` | A loaded card violates the contract. | Stop and report the typed validation issue; return the card to its author or human reviewer. |
| `DRIFT`, exit `3` | Valid before/after cards crossed a named boundary. | Stop the handoff and present the drift report to the human; do not treat the newer card as approved. |
| `UNKNOWN` | The task has unresolved facts or an unbounded classification. | Stop and return the task for human clarification. |
| `BLOCKING` | The card contains an unresolved or high-risk boundary. | Keep the work blocked until a human explicitly resolves the gate. |
| `REPORT_REQUIRED` | A matching adapter action failed or has an unknown outcome. | Surface the direct result to the human before any later tool action. |

The exact input, exit, and output contracts are in the [Core Reference](CORE_REFERENCE.md).

## Adapter state and hook outcomes

The optional `agent-frontdoor-hooks` adapter writes only privacy-minimized local
state. If its state root is not a real directory with mode `0700`, or a state
file is not a real regular file with mode `0600`, stop and inspect the configured
state path. Do not relax permissions, replace a path, or overwrite state to
continue.

The adapter is intentionally silent for a same-intent result: silence is not an
allow decision and does not grant authority. Another host permission or
authority control may still deny the action. Inspect the relevant local hook
event and return the decision to the human rather than inferring permission.

A Codex result without explicit structured status is outcome-opaque. It enters
`REPORT_REQUIRED` because output text is not proof of success or failure. Keep
the original result available for reporting and stop before any new action.

Windows is rejected for this adapter release because its POSIX permission model cannot be enforced there. In this case, stop adapter adoption and return the choice to the operator; do not claim an equivalent adapter configuration.

Paths outside supported hook coverage are outside this guardrail. Treat them as
uncovered, report that limit to the human or host, and use the host's own
controls. The adapter is not a security boundary.

## Offline and acceptance boundaries

For an offline Friend Lab acceptance, a missing or incompatible wheel is a hard
stop. Inspect the verified pack and wheelhouse with the receiver; do not fetch,
compile, substitute, or download a replacement. The attended procedure and its
digest prerequisites are in [Friend Lab](FRIEND_LAB.md).

If an acceptance control, privacy check, write check, determinism check, or
uninstall check fails, preserve the evidence and return the result to the human.
The procedure does not delete evidence automatically and does not offer a
fallback path.

## Review before changing anything

Before an operator chooses any configuration change, review the
[Getting Started](GETTING_STARTED.md) route for the read-only core and the
optional adapter's reviewed examples. Installation, configuration, activation,
execution, and authority remain separate human or host decisions.
