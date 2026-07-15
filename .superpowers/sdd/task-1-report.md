# Task 1 Report: Local Package Skeleton and Intake Schema

## Status

DONE

## TDD evidence

The first test invocation surfaced the missing schema as a pytest fixture setup
error. Before creating production files, the fixture was corrected so the
missing feature produced a canonical assertion failure, then RED was rerun.

### RED

Command:

```text
.venv/bin/pytest tests/test_intake_schema.py -q
```

Output (exit 1):

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_intake_schema_has_exact_core_contract __________________

schema = None

    def test_intake_schema_has_exact_core_contract(schema):
>       assert schema is not None, f"missing intake schema: {SCHEMA_PATH}"
E       AssertionError: missing intake schema: /Users/umeboshi/Workspace/oss_staging/agent-frontdoor/schema/intake.v0.json
E       assert None is not None

tests/test_intake_schema.py:81: AssertionError
=========================== short test summary info ============================
FAILED tests/test_intake_schema.py::test_intake_schema_has_exact_core_contract
1 failed in 0.02s
```

The failure was expected: `schema/intake.v0.json` did not exist.

### GREEN

Command:

```text
.venv/bin/pytest tests/test_intake_schema.py -q
```

Final output (exit 0):

```text
.                                                                        [100%]
1 passed in 0.05s
```

### Full current suite

Command:

```text
.venv/bin/pytest -q
```

Final output (exit 0):

```text
.............................................                            [100%]
45 passed in 0.64s
```

### Additional verification

Validated the schema with `jsonschema.Draft202012Validator.check_schema`,
imported `frontdoor` from `src`, parsed `pyproject.toml`, and confirmed the
console declaration is exactly `agent-frontdoor = frontdoor.cli:main`.
`git diff --cached --check` was clean before commit.

## Files committed

- `.gitignore`
- `pyproject.toml`
- `schema/intake.v0.json`
- `src/frontdoor/__init__.py`
- `tests/test_intake_schema.py`

The legacy `schema/agent-frontdoor.v0.1.json` remains present and was not
modified or staged. All unrelated pre-existing files remained unstaged.

## Commit

`e341df0bb3fedd1b6862f5fabcd6a4e15e49525c` —
`feat: define agent frontdoor v0 intake contract`

## Self-review and concerns

- The schema requires exactly the 14 approved fields and denies unknown fields.
- Task class, gate, capability, and risk enums match the approved vocabularies.
- Required text, action arrays, and manifest constraints match the Task 1 brief.
- No network, worker invocation, task execution, deploy, scheduler, settings,
  hook, or remote behavior was added.
- No Task 1 blockers or implementation concerns. The declared CLI target is a
  planned later-task dependency; Task 1 intentionally does not create `cli.py`.

## Python 3.10 floor correction (2026-07-15)

The approved plan specifies Python 3.10+, but `pyproject.toml` declared
`requires-python = ">=3.11"`. A focused package-floor assertion was added before
the metadata was corrected.

### RED

Command: `.venv/bin/pytest tests/test_intake_schema.py -q`

Result (exit 1): `1 failed, 1 passed in 0.03s`; the new
`test_package_supports_python_3_10_and_newer` assertion expected
`requires-python = ">=3.10"` and observed the existing `>=3.11` declaration.

### GREEN

- Focused: `.venv/bin/pytest tests/test_intake_schema.py -q` (exit 0) —
  `2 passed in 0.01s`.
- Full suite: `.venv/bin/pytest -q` (exit 0) — `46 passed in 0.06s`.
