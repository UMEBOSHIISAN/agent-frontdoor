# Security policy

## Supported version

Security fixes are evaluated against the current `main`. The contract version is `intake.v0`; no long-term support
window is implied for earlier checkouts.

## Report privately

Use a [GitHub Security Advisory](https://github.com/UMEBOSHIISAN/agent-frontdoor/security/advisories/new) to report a
suspected vulnerability privately.

**Do not open a public issue** containing credentials, private paths, personal data, live exploit details, or anything
that could expose another person's environment.

Include only what is needed to reproduce:

- affected commit;
- operating system and Python version;
- the exact command and its exit code;
- a sanitized or fictional task card that triggers the behaviour;
- expected and actual closed behaviour;
- whether the issue crosses a validation, drift-detection, or execution boundary.

Do not send real tokens, private repository contents, or unredacted machine configuration. If a fictional fixture cannot
reproduce it, describe the shape of the input rather than pasting the real one.

## What counts as a vulnerability here

This package has no execution path, so the interesting failures are boundary failures rather than remote code execution:

- an invalid card that validates, or a card that validates and should not;
- a drift case that `check-drift` reports as `NO DRIFT`;
- any input that causes a write, a subprocess, or a network request;
- an exit code that does not match the documented contract;
- output that leaks the content of a file the caller did not name.

A crash on malformed input is a bug, but a *silent pass* on unsafe input is the more serious class.

## Response boundary

A report is evidence for review. It is not permission to access another system, rotate credentials, publish details, or
deploy a fix. Maintainers will reproduce with sanitized local data, scope the impact, add a regression test, and
coordinate disclosure separately.
