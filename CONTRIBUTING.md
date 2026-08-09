# Contributing to Agent Frontdoor

Thanks for helping keep the front door narrow. This package exists to *refuse* things, so a contribution is judged less
by what it enables than by what it still refuses afterwards.

## Setup

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/pytest -q
```

## TDD workflow

1. Add the smallest failing test that expresses the intended public contract.
2. Run the focused test and confirm the failure is the one you expected — not a different failure that happens to be red.
3. Implement the smallest change that makes it pass.
4. Run the full suite with `.venv/bin/pytest -q`.
5. Run the hard contracts explicitly:
   `.venv/bin/pytest tests/test_fixture_metrics.py tests/test_no_execution_paths.py -q`
6. Run `git diff --check` and read every changed byte before committing.

Do not weaken a guard, relax a fixture, or delete a regression test to make a change green. A red test that describes a
real boundary is more valuable than a green suite that no longer describes one.

## The exit-code contract

Exit codes are public API here, not diagnostics:

| Exit | Meaning |
|---|---|
| `0` | valid card, or no drift |
| `1` | the loaded card violates the contract |
| `2` | input unreadable or malformed JSON |
| `3` | a validated before/after pair crossed a named boundary |

Changing what an exit code means is a breaking change even if every test still passes. Say so explicitly in the pull
request.

## Fixtures

The labeled corpus under `fixtures/` is evidence, not decoration. When you add a case:

- put positive cards in `fixtures/positive/`, negative cards in `fixtures/negative/`;
- give a negative card the exact issue code it must produce;
- keep every fixture fictional — no real repository paths, hostnames, ticket numbers, or customer wording;
- update the counts you cite in the README only from a measured run, never from an estimate.

## Safety boundaries

Changes must not add task execution, subprocess invocation, network access, worker invocation, automatic routing,
schedulers, hooks, daemons, deployment, credential access, retries, repair fallback, or authority promotion. `UNKNOWN`
and high-risk expansion must keep failing closed with `BLOCKING`.

Any proposal to move one of those boundaries needs a separate, human-approved design before implementation. "It was
convenient for my workflow" is not a design.

## Public-data hygiene

Do not commit secrets, personal paths, hostnames, private endpoints, prompt bodies, model output, or machine-specific
commands. Construct any sensitive-looking test value so that it is obviously fictional and cannot be a real credential.

## Pull requests

Explain the problem, the boundary involved, the test-first evidence, the compatibility impact, and what is still not
handled. Keep unrelated refactors out. A clean test run is necessary but does not replace review.
