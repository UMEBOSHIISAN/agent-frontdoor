# Changelog

## 0.1.0 (unreleased)

Initial release candidate.

- `intake.v0` JSON Schema contract: 14 core fields, 10 bounded task classes,
  three human-gate states.
- Fail-closed validator: schema validation plus deterministic semantic checks
  (mandatory blocking categories, UNKNOWN preservation, action-conflict
  detection), returning typed issues with human-readable reasons.
- Deterministic card and explanation formatter.
- Boundary-drift comparator covering six named expansion families.
- Read-only CLI: `validate`, `card`, `explain`, `check-drift` with a documented
  exit-code contract.
- Fixture corpus (positive, negative, drift envelopes) with hard metric test
  contracts and per-task-class coverage guarantees.
- Runnable `examples/` card pairs for the `check-drift` quickstart.
