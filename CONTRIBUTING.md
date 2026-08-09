# Contributing

Thank you for helping improve Agent Frontdoor. Contributions must preserve its
read-only core, explicit human gates, and separate optional-adapter boundary.

## Before you start

Search existing issues before opening a new one. Use [SUPPORT.md](SUPPORT.md) to
choose the question, bug, feature, or confidential-vulnerability route. Follow
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) in every project interaction. Suspected
vulnerabilities belong only in the private route described by
[SECURITY.md](SECURITY.md), never in an ordinary issue or pull request.

## Trust boundaries

The core validates local task-card inputs and returns deterministic decisions.
It must not execute tasks, invoke workers, access the network at runtime, write
source files, activate hooks, or grant authority. Task identity is not
authorization.

The optional `agent-frontdoor-hooks` distribution may write only its documented,
privacy-minimized session state after an operator separately installs and
configures it. Installing or testing the adapter must not edit operator-owned
settings or activate a live hook.

## Source setup

Use the public source repository and an isolated virtual environment:

```bash
git clone https://github.com/UMEBOSHIISAN/agent-frontdoor.git
cd agent-frontdoor
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pip install -e adapters
source .venv/bin/activate
```

These commands install source for development. They do not configure a live
hook. The project has no published release; do not substitute a package-index
installation or describe the checkout as a released artifact. Keep this
environment activated for every `python3` verification command below.

## Test-first workflow

Start with a focused failing test that demonstrates the missing behavior. Check
that it fails for the expected reason, implement the smallest bounded change,
and rerun the focused test. Keep tests deterministic and offline. Do not weaken
existing assertions or add retries, network access, live settings changes, or
unrelated refactors.

## Focused verification

Choose the smallest relevant group:

```bash
# Read-only core and Intent Lock
python3 -m pytest -q tests/test_intake_schema.py tests/test_validator.py tests/test_cli.py tests/test_intent_lock.py

# Optional adapter
python3 -m pytest -q tests/test_adapter_safety.py tests/test_hook_adapter.py tests/test_hook_fixtures.py tests/test_hook_state.py

# Public documentation and runnable examples
python3 -m pytest -q tests/test_public_docs.py tests/test_readme.py tests/test_examples.py tests/test_distribution_boundary.py
```

## Full verification

Run the complete suite once the focused checks pass:

```bash
python3 -m pytest -q
```

## Documentation and packaging checks

Update documentation and examples when a public contract changes. Confirm that
commands, paths, exit codes, and safety claims match measured behavior. Review
`pyproject.toml`, `adapters/pyproject.toml`, `MANIFEST.in`, package data, and the
distribution-boundary tests for any packaging change. Keep the core and adapter
as separate distributions, scan the diff for private data, and run:

```bash
git diff --check
python3 -m pytest -q tests/test_public_docs.py tests/test_examples.py tests/test_distribution_boundary.py
```

## Pull requests

Keep each pull request narrowly scoped and explain its safety-boundary impact.
Complete the repository pull request template with focused and full verification
evidence. Link the relevant issue without including secrets or private paths.
Source changes do not imply a release, deployment, live hook activation, or
authorization to change repository settings.
