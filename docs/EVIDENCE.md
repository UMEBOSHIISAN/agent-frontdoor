# Evidence

## What these numbers measure

These are fixture-corpus regression evidence for Agent Frontdoor's documented
hard contracts. They describe the checked repository corpus and static source
boundary at the snapshot below; they do not describe generalized semantic
accuracy, a production prevention rate, security certification, or current
release status.

## Reproducible corpus snapshot

| Contract | Snapshot result | Scope |
| --- | --- | --- |
| Positive cards | `31 / 31` | All 31 schema/semantic validations succeed. |
| Negative cards | `41 / 41` | All 41 are rejected with their exact named issue-code sets. |
| Drift cases | `16 / 16` | All 16 labeled drift envelopes produce their exact expected code sets. |
| Safe controls | `4 / 4` | All four labeled safe envelopes produce no finding. |
| Source boundary | zero forbidden core execution/network/worker/routing/source-write paths | The static core-source guard finds zero prohibited path classes. |

## Reproduce the hard contracts

Run the focused hard-contract checks:

```bash
python3 -m pytest -q tests/test_fixture_metrics.py tests/test_no_execution_paths.py
```

Run the complete suite:

```bash
python3 -m pytest -q
```

## Dated full-suite baseline

The baseline `836 passed` belongs only to commit
`e866efa025f5299d638adfb4bf903a8de2594c0e` on 2026-08-09. It is a dated
full-suite observation, not a claim about the current release.

## Interpretation limits

This fixture-corpus regression evidence is not a real-world effectiveness
benchmark. It is not an independent security audit. The checked fixtures and
static source guard make their defined contracts reproducible, but they do not
establish generalized semantic accuracy, production prevention rate, or
security certification.
