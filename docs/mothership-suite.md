# Mothership suite compatibility

Agent Frontdoor is the semantic owner of the `frontdoor-task` protocol at `intake.v0`. The owner schema remains
`src/frontdoor/schema/intake.v0.json`; Mothership 0.2.0 freezes those exact bytes and their SHA-256 for composition with
the other independently adoptable projects.

The closed conformance manifest is `suite/mothership-0.2-conformance.json`. It binds the repository, protocol version,
owner schema digest, and one fictional example without granting runtime authority.

## Reproduce

```sh
.venv/bin/agent-frontdoor validate examples/mothership-task.json
.venv/bin/python -m pytest tests/test_mothership_conformance.py -q
```

The first command prints `VALID demo-review-001`. A valid task card remains preflight metadata: `human_gate` describes
the review boundary but does not approve, route, invoke, or execute work. `card` and `explain` render only intake fields;
they do not add Mothership protocol metadata or authority claims.

See the exact suite order and snapshot rules in the
[Mothership protocol reference](https://github.com/UMEBOSHIISAN/mothership/blob/main/docs/protocols.md).

## Compatibility boundary

Conformance proves only owner/schema/example compatibility with Mothership 0.2.0. It does not prove publication,
production accuracy, approval, execution, downstream freshness, or the availability of another repository.
