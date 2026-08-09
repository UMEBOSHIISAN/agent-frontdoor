# Mothership 0.2 owner-side conformance

Agent Frontdoor owns the `frontdoor-task` protocol at `intake.v0`. This
repository publishes an owner-side conformance snapshot that binds the local
[owner schema](../src/frontdoor/schema/intake.v0.json), its SHA-256, the
[closed manifest](../suite/mothership-0.2-conformance.json), and one
[synthetic example](../examples/mothership-task.json).

The snapshot proves local schema, example, and CLI compatibility only. It does
not prove external Mothership availability or behavior. It does not install,
invoke, route through, grant authority, or execute work.

## Reproduce

```sh
PYTHONPATH=src .venv/bin/agent-frontdoor validate examples/mothership-task.json
PYTHONPATH=src .venv/bin/python -m pytest tests/test_mothership_conformance.py -q
```

The first command prints `VALID demo-review-001`. A valid task card remains
preflight metadata: `human_gate` describes a review boundary but does not
approve, route, invoke, or execute work. `card` and `explain` render only intake
fields; they do not add conformance metadata or authority claims.

## Compatibility boundary

The manifest's `suite_release` identifies the intended 0.2 compatibility line;
it is not evidence of a remote tag, release, deployment, or downstream
freshness. Any multi-repository composition must separately verify the exact
external revision and its own authority boundary.
