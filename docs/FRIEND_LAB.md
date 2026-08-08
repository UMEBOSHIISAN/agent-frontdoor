# Agent Frontdoor Friend Lab

This is a human-attended acceptance procedure for one exact Agent Frontdoor
friend pack. It is not an installer, deployment script, remote-management tool,
model router, or permission grant. It never changes an existing project,
settings file, hook, service, scheduler, model inventory, or secret store.

The transfer set contains exactly two files:

1. `agent-frontdoor-friend-pack-0.2.0.tar.gz`
2. `verify_handoff_archive.py`

The expected pack, source, and verifier SHA-256 values arrive through a separate
human-confirmed channel. Values carried only inside the pack are not independent
trust evidence.

## 1. Record out-of-band digests

Before opening the pack, record these three lowercase SHA-256 values:

```text
EXPECTED_PACK_SHA256=<64 lowercase hex>
EXPECTED_SOURCE_SHA256=<64 lowercase hex>
EXPECTED_VERIFIER_SHA256=<64 lowercase hex>
```

Compare the detached verifier file with `EXPECTED_VERIFIER_SHA256` first. If any
value is missing, malformed, or supplied only beside the pack, stop. Do not infer
a value from a filename, chat history, or local operator note.

## 2. Verify before extraction

Run the detached standard-library verifier while the pack is still unopened:

```bash
python3 verify_handoff_archive.py friend-pack \
  agent-frontdoor-friend-pack-0.2.0.tar.gz \
  --detached-verifier verify_handoff_archive.py \
  --expected-pack-sha256 "$EXPECTED_PACK_SHA256" \
  --expected-source-sha256 "$EXPECTED_SOURCE_SHA256" \
  --expected-verifier-sha256 "$EXPECTED_VERIFIER_SHA256"
```

Continue only after one `PASS friend-pack ...` line and exit status `0`. The
verifier checks the detached bytes, outer manifest and checksum, every outer
member, the identical in-pack verifier, and the nested source archive entirely
in memory. It never calls filesystem extraction.

## 3. Create a disposable root

Choose a new, empty, receiver-owned path and bind it explicitly:

```bash
export FRIEND_TRANSFER_ROOT="$PWD"
export FRIEND_TEMP_ROOT='<FRIEND_TEMP_ROOT>'
mkdir "$FRIEND_TEMP_ROOT"
tar -xzf agent-frontdoor-friend-pack-0.2.0.tar.gz -C "$FRIEND_TEMP_ROOT"
export FRIEND_PACK_ROOT="$FRIEND_TEMP_ROOT/agent-frontdoor-friend-pack-0.2.0"
export FRIEND_RUN_ROOT="$FRIEND_TEMP_ROOT/friend-lab-run"
```

The leaf must not already exist, be a symbolic link, contain files, or resolve
inside an existing project. Keep the pack and detached verifier present until
acceptance finishes. Never extract over an existing checkout.

## 4. Run positive controls

The lab carries three synthetic controls bound by the outer manifest:

- privacy categories in `lab/controls/privacy_control.txt`;
- one deliberate out-of-root write attempt;
- one deliberate socket operation attempt.

The packaged runner performs these controls before package installation; do not
run or waive them separately. Acceptance is invalid unless the
privacy scanner detects every declared category and the audit guard records both
deliberate probes. Record that control ledger as the baseline. The controls are
test evidence, not exceptions granted to Agent Frontdoor. The single runner
invocation in step 5 executes steps 4 through 11 once, without retry.

## 5. Confirm physical network disconnect

For a local run, the receiver physically disables network connectivity before
invoking the runner. The runner confirms that the bounded reachability probe
fails before either environment is created; it does not disable adapters itself.

From the transfer directory, run the exact packaged entrypoint. The run-root
leaf must not already exist:

```bash
python3 "$FRIEND_PACK_ROOT/lab/acceptance_runner.py" \
  --pack "$FRIEND_TRANSFER_ROOT/agent-frontdoor-friend-pack-0.2.0.tar.gz" \
  --detached-verifier "$FRIEND_TRANSFER_ROOT/verify_handoff_archive.py" \
  --pack-root "$FRIEND_PACK_ROOT" \
  --run-root "$FRIEND_RUN_ROOT" \
  --expected-pack-sha256 "$EXPECTED_PACK_SHA256" \
  --expected-source-sha256 "$EXPECTED_SOURCE_SHA256" \
  --expected-verifier-sha256 "$EXPECTED_VERIFIER_SHA256" \
  --execution-mode local \
  --verifier-role receiver-human \
  --network-disconnected-confirmed
```

A remote SSH run cannot independently confirm physical disconnect and therefore
cannot earn `PRIVATE_HANDOFF_READY`. Even when every other check passes, it is
capped at `PRIVATE_HANDOFF_READY_WITH_GAPS`.

## 6. Verify source and wheel environments

The runner creates two fresh environments beneath `FRIEND_RUN_ROOT`: one for the
verified source archive and one for the exact Agent Frontdoor wheel. Neither
inherits global packages. It installs the source with its `[test]` extra and the
exact locked backend using `--no-index`, `--find-links`, and
`--no-build-isolation`, then source-binds and privacy-scans both installed
package trees before running them.

The only package input is `FRIEND_PACK_ROOT/wheelhouse`. A missing wheel, sdist,
tag mismatch, backend version mismatch, unlisted file, private wheel member, or
source/wheel mismatch stops the run. Do not download or compile a replacement.

## 7. Run tests and samples

Run the complete core-distribution suite with bytecode and cache disabled in the
source environment. The separately packaged optional `agent-frontdoor-hooks`
runtime tests are excluded because this acceptance lane installs only the core
wheel; they are verified in the adapter's own build/test lane. Record the freshly
collected count; do not copy a historical number. Then run the documented
positive commands against
`fixtures/positive/01_install_only.json`:

```bash
agent-frontdoor validate fixtures/positive/01_install_only.json
agent-frontdoor card fixtures/positive/01_install_only.json
```

Repeat the relevant suite and samples in the wheel environment. Agent Frontdoor
must still expose exactly `validate`, `card`, `explain`, and `check-drift`.

## 8. Run negative fixtures

Run one fixture from each required fail-closed family and require the documented
non-zero result:

- deployment;
- scheduler mutation;
- destructive cleanup;
- authority promotion;
- missing required manifest.

An unexpected zero exit is a failure. Do not rewrite a fixture or weaken a gate
to make the run pass.

## 9. Check deterministic repetition

Run every deterministic command twice with identical verified input. Compare
exit status plus complete stdout and stderr bytes. Record only their hashes in
the receipt. Any difference is `NOT_READY`; there is no second repair attempt or
fallback command.

## 10. Scan privacy and writes

First prove the privacy scanner with the exact hash-bound positive control.
Then scan the source tree, installed package bytes, captured outputs, and receipt
candidate. Exclude only that exact control path with its manifest digest.

Compare the audit ledger against the control baseline and require zero new
socket or out-of-root write events. Compare the disposable tree with its declared
allowlist and reject undeclared files. Separately run the static execution,
network, dynamic-loader, native-extension, subprocess, and write-path checks.

The receipt contains hashes and closed result codes only. It never contains a
receiver identity, machine name, address, home location, environment value,
credential, prompt, model output, raw command, raw output, or source content.

## 11. Uninstall and write the receipt

The runner uninstalls Agent Frontdoor from both environments and confirms the
CLI is absent. On success it writes exactly one receipt here:

```bash
test -f "$FRIEND_RUN_ROOT/friend-acceptance-receipt.json"
```

The receipt is schema-valid and remains inside the disposable root. Classification
is mechanical:

- `PRIVATE_HANDOFF_READY`: every phase passed in a local receiver run with
  independently confirmed physical disconnect;
- `PRIVATE_HANDOFF_READY_WITH_GAPS`: every executable phase passed, but the run
  was remote or disconnect could not be independently confirmed;
- `NOT_READY`: any digest, control, install, test, sample, determinism, privacy,
  write, uninstall, or receipt requirement failed or was missing.

The procedure never deletes evidence automatically. The receiver may inspect
the receipt and captured hashes before deciding whether to remove the disposable
root.
