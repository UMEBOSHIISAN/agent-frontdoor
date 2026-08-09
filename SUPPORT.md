# Support

Agent Frontdoor is unreleased, source-only software. These routes describe the
intended repository community surface. A route is available only after its file
is present on the default branch and the corresponding GitHub feature is
enabled. GitHub Discussions are disabled.

## Usage questions

For a bounded usage or documentation question, open a
[blank question issue](https://github.com/UMEBOSHIISAN/agent-frontdoor/issues/new?labels=question).
Describe the source revision, what you are trying to validate, and the command's
redacted output. Do not include credentials, private paths, or real session
content.

## Reproducible bugs

For behavior that differs from the documented contract, use the
[bug form](https://github.com/UMEBOSHIISAN/agent-frontdoor/issues/new?template=bug.yml).
Include an exact revision and a minimal, secret-free reproduction. A suspected
vulnerability is not an ordinary bug and must use the confidential route below.

## Feature and design proposals

For a bounded change to behavior, documentation, or trust boundaries, use the
[feature form](https://github.com/UMEBOSHIISAN/agent-frontdoor/issues/new?template=feature.yml).
Explain the problem, alternatives, evidence, and any impact on core execution,
network, source-write, adapter-state, human-gate, or hook-activation boundaries.
A proposal does not authorize implementation, release, activation, or settings
changes.

## Confidential vulnerabilities

Do not disclose a suspected vulnerability in a public issue. Follow
[SECURITY.md](SECURITY.md) and use the intended
[confidential security report](https://github.com/UMEBOSHIISAN/agent-frontdoor/security/advisories/new)
route only after GitHub private vulnerability reporting is enabled.
