# Runnable examples

Install the source checkout first, then run these examples from the repository
root. Each example is a local, read-only input or decision demonstration; none
activates hooks or changes settings.

| Example | Run | Expected outcome |
| --- | --- | --- |
| [`task-card.json`](task-card.json) | `.venv/bin/agent-frontdoor validate examples/task-card.json` | `VALID example-readme-audit` |
| [`intent_lock_demo.py`](intent_lock_demo.py) | `.venv/bin/python examples/intent_lock_demo.py` | `False literal_target_mismatch`, `True literal_target_match`, then `No command was executed; an intent match is not authority.` |
| [`drift_before.json`](drift_before.json) | with `drift_after.json`: `.venv/bin/agent-frontdoor check-drift examples/drift_before.json examples/drift_after.json` | exit `3` and `audit_to_mutation` |
| [`drift_after.json`](drift_after.json) | paired with `drift_before.json` | exit `3` and `audit_to_mutation` |
| [`safe_before.json`](safe_before.json) | with `safe_after.json`: `.venv/bin/agent-frontdoor check-drift examples/safe_before.json examples/safe_after.json` | exit `0` and `NO DRIFT` |
| [`safe_after.json`](safe_after.json) | paired with `safe_before.json` | exit `0` and `NO DRIFT` |

The four split drift cards are direct CLI inputs. The labeled envelopes under
`fixtures/drift/` are test corpus inputs, not replacements for these examples.
