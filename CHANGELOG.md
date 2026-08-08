# Changelog

## Unreleased

- Added the pure `intent-lock.v1` schema and deterministic task-identity state
  machine for exact commands and literal error targets.
- Added the separate optional `agent-frontdoor-hooks` distribution with Codex
  and Claude Code lifecycle adapters, private atomic state, platform fixtures,
  and fail-closed regression coverage.
- Added inert configuration examples and activation/removal documentation. The
  adapter is not activated in local agent settings by this repository.
- Added a standard-library standalone archive verifier for detached, outer-pack,
  and nested-source integrity checks before extraction.
- Defined a deterministic friend pack and closed public manifest/receipt
  contracts for receiver-specific offline acceptance.
- Added guarded friend-lab acceptance documentation and lab-only tooling
  boundaries that do not expand the four-command runtime.
- Corrected offline installation instructions to require an exact verified
  wheelhouse without global-package or index fallback.

## 0.1.0 (release candidate)

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
