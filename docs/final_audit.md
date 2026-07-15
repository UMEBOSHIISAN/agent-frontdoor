# Agent Frontdoor v0 Independent Codex Final Audit

- Auditor role: independent Codex final reviewer (review-only for source, runtime, and tests)
- Audited commit: `ab2b87ffb093a35bfb3eba816fbaf809316337f0`
- Audit date: 2026-07-15
- Verdict: **PASS**
- Verification level: cross-verified

## Conclusion

No material gap remains against the explicit Agent Frontdoor v0 lexical,
schema, CLI, fixture, worker-evidence, or no-execution contract. The package is
a local preflight validator only; it has no worker invocation, routing,
execution, network, daemon, hook, deployment, or source-mutation path.

## Audit history

1. `ff3b4e3` failed because `rm old files`, authority approval, and UNKNOWN
   `chmod` mutation forms were accepted. `8ab1f41` added fail-closed aliases.
2. `8ab1f41` failed because erase/wipe remained open and generic past-tense
   approval language overblocked safe review/research. `f9113ab` added
   inflection-aware destructive matching and contextual authority matching.
3. `f9113ab` failed on ordinary indefinite-article authority actions and
   explicit `truncate`/`drop` destructive operations. `ab2b87f` added bounded
   contextual determiners, contextual SQL/data deletion matching, safe drop
   controls, and UNKNOWN drop protection.

The final audit re-ran every prior reproducer and the associated safe controls.
All now produce the intended result.

## Fresh verification evidence

### Package and tests

- `.venv/bin/python -m pip install --no-deps --no-build-isolation -e .`:
  exit `0`; editable package built and installed without dependency download.
- `.venv/bin/pytest tests/test_validator.py -q`: **378 passed**.
- `.venv/bin/pytest tests/test_fixture_metrics.py tests/test_no_execution_paths.py -q`:
  **31 passed**.
- `.venv/bin/pytest -q`: **500 passed**, 0 failed, in 0.50s.

### Reproducer and safe-control matrix

Mandatory-blocking / UNKNOWN-mutation cases all failed closed:

```text
rm old files                              -> blocking_gate_required
Approve this proposal for execution       -> blocking_gate_required
UNKNOWN: review and chmod local files     -> unknown_mutation_forbidden
erase archived records                    -> blocking_gate_required
wipe generated artifacts                  -> blocking_gate_required
Approve a proposal for execution          -> blocking_gate_required
Authorize a task for execution            -> blocking_gate_required
Promote a worker                          -> blocking_gate_required
Truncate the stale table                  -> blocking_gate_required
Drop the stale table                      -> blocking_gate_required
UNKNOWN: review then drop my stale table  -> unknown_mutation_forbidden
```

Bounded close variants also failed closed: `Approve our request`, `Authorize
your task`, `Promoting that user`, `Drops the archive table`, and `Dropping my
local database`.

Safe descriptive controls remained valid:

```text
Review the approved local design document without implementing it
Research the authorized public API documentation
Analyze the reported drop in test coverage
Summarize the dropped calls metric
Report the product drop rate
Review the approved proposal without implementing it
```

### Installed CLI

- `agent-frontdoor validate fixtures/positive/01_install_only.json`: exit `0`,
  `VALID positive-01`.
- `agent-frontdoor card fixtures/positive/01_install_only.json`: exit `0`,
  complete fixed-order card.
- `agent-frontdoor explain fixtures/positive/01_install_only.json`: exit `0`,
  self-contained explanation.
- `agent-frontdoor check-drift fixtures/positive/21_design_review.json fixtures/positive/19_code_patch.json`:
  exit `3`, `design_to_implementation` reported.

### Hard metrics

- Positive schema/semantic validity: **30/30 = 1.00**.
- Negative fixtures: **40**.
- Named blocking cases: **25/25 = 1.00** recall.
- Labeled drift cases: **16/16 = 1.00** recall.
- Safe drift controls: **4/4 = 1.00**.

## Contract checklist

- [x] Required components exist: schema, validator, formatter, drift detector,
  CLI, fixtures, tests, README, and package metadata.
- [x] Local installation succeeds without dependency download.
- [x] All four installed read-only CLI commands work with documented exits.
- [x] `schema/intake.v0.json` has exactly the 14 core fields,
  `additionalProperties: false`, the 10 approved task classes, and the exact
  `NONE` / `CONFIRM` / `BLOCKING` gates.
- [x] The capability enum contains generic capability labels only; no model or
  vendor is fixed in the core schema.
- [x] Fixture counts are 30 positive, 40 negative, and 20 drift envelopes; all
  required categories and hard thresholds pass.
- [x] UNKNOWN cards fail closed for gate, worker, stated-unknown, and mutation
  violations covered by the explicit v0 lexical contract.
- [x] README begins with the exact required three-line disclaimer and documents
  install, gates, commands, exits, drift, metrics, and safety boundaries.
- [x] Worker comparison assets use the same 20 inputs and include exact aliases,
  raw artifacts, measurements, and mismatches.
- [x] Independent Codex audit: **PASS**.
- [x] Local commits exist; no remote is configured and no push evidence exists.

## Security and boundary result

**Security Review**

- Verdict: **PASS**.
- Runtime AST/source checks found no subprocess, socket, HTTP client, worker
  launcher, dynamic import, execution primitive, network call, or file-write
  path under `src/frontdoor/`.
- Runtime reads only local JSON/schema data and emits only stdout/stderr.
- CLI surface is exactly `validate`, `card`, `explain`, and `check-drift`.
- `ab2b87f` changes only `src/frontdoor/validator.py` and
  `tests/test_validator.py`; no prohibited project, settings, hook, scheduler,
  deploy, routing-ledger, worker-registry source, or external target was touched.
- `git remote -v` is empty. Before this report, `git status --short --branch`
  showed clean `main` except the permitted untracked audit report.

The fixed grep audit returned:

```text
check=keys_env_ref status=ok count=0
check=direct_env_file status=ok count=0
check=os_environ_secret status=ok count=0
check=hardcoded_secret_like status=ok count=0
check=exec_primitives status=hit count=2
```

Both execution hits are test-only evidence at
`tests/test_no_execution_paths.py:80` and
`tests/test_no_execution_paths.py:305`: a forbidden prefix constant and a
negative self-test source literal rejected by the AST guard. Runtime-source
text hits for `unlink` are regex literals, not calls.

## Worker scorecard assessment

- Input and oracle files contain the same 20 request IDs; both raw artifacts and
  the project-local scorecard exist.
- `qwen-fast-mini`: one approved attempt, 120s timeout, no parseable output;
  failure is retained transparently without retry.
- `gemma-fast-mini`: valid 20-row JSON; independently recomputed task-class
  accuracy `0.90`, risk-tag recall `1.00`, blocking recall `1.00`, format
  validity `1.00`; exact mismatches are `eval-14` and `eval-18`.
- Worker answers remain evaluation evidence only and did not change validator
  behavior. The shared worker registry was not modified.

## Residual risk

The v0 classifier is intentionally deterministic and lexical. This PASS covers
the explicit risk vocabulary, tested inflections, contextual authority forms,
bounded destructive forms, UNKNOWN fail-safe rules, and the committed fixture
contract. It does not claim universal natural-language understanding or perfect
classification of every possible paraphrase. Unknown or unsupported inputs
must continue to be represented as `UNKNOWN` and/or `BLOCKING`, and future
lexical expansion should remain TDD-scoped to concrete failures with safe
controls to avoid overblocking.

This audit made no network request and modified no source, tests, remotes, or
file other than this report.
