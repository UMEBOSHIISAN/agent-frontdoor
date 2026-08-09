# Getting Started

Agent Frontdoor is a source-only, unreleased read-only core. This guide installs
the repository source so you can validate and render one local task card. It
does not activate hooks, edit settings, execute tasks, or grant authority.

## Requirements

| Component | Requirement and boundary |
| --- | --- |
| Read-only core | Python 3.10 or newer. The core validates local inputs and returns deterministic decisions without task execution, network requests, worker invocation, or source writes. |
| Optional adapter | POSIX only. This adapter release rejects Windows; it does not claim an unmeasured Windows compatibility matrix. |

## Install from source

Clone the public source repository and install the core into an isolated virtual
environment. This runtime quick start intentionally omits test extras. For the
supported isolated `.[test]` setup used to reproduce repository evidence, see
[Evidence](EVIDENCE.md).

```bash
git clone https://github.com/UMEBOSHIISAN/agent-frontdoor.git
cd agent-frontdoor
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Installation can use network access to retrieve Python dependencies. After
installation, the core's task-card validation and Intent Lock runtime are
network-free local operations.

## Validate your first task card

Validate the curated audit card:

```bash
.venv/bin/agent-frontdoor validate examples/task-card.json
# VALID example-readme-audit
```

`VALID` means the card satisfies the documented input contract. It does not
authorize the audit or any later action.

## Read the task card

Render the same validated card in its fixed field order:

```bash
.venv/bin/agent-frontdoor card examples/task-card.json
```

The four read-only CLI commands and their exit contracts are in the
[Core Reference](CORE_REFERENCE.md).

## Next routes

For the runnable task-card, drift, and Intent Lock inputs, see the
[example index](../examples/README.md). The Intent Lock demo makes decisions
without executing either proposed command.

Optional adapter installation and configuration are separate, non-live operator
actions. Review the [Optional adapter](https://github.com/UMEBOSHIISAN/agent-frontdoor/tree/main/adapters)
before any configuration; installation does not activate a hook or edit live
settings.

## Uninstall

Remove the core package from this virtual environment without changing the
source checkout or other environments:

```bash
.venv/bin/python -m pip uninstall -y agent-frontdoor
```
