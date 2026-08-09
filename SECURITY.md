# Security Policy

## Release status

Agent Frontdoor has no published release. The current repository is
unreleased source, and reports must identify the exact commit being reviewed. A
repository-hosted reporting route must not be treated as available until this
policy is present on the default branch and GitHub private vulnerability
reporting is enabled.

## Scope

Security reports may cover either of these source boundaries:

- the read-only `agent-frontdoor` core, including local input validation,
  boundary-drift checks, Intent Lock decisions, and package contents;
- the separately installable `agent-frontdoor-hooks` adapter, including its
  privacy-minimized local state and event handling.

The core does not execute tasks, make network requests at runtime, invoke
workers, write source files, or grant authority. The optional adapter is not
part of the core's read-only boundary and is inactive until an operator
separately configures it.

## Security model

A matching task or action identity is not authorization. Independent
permissions, human gates, and platform controls still apply. Local hooks are a
guardrail, not a security boundary; hosted, specialized, or differently
configured execution paths may be outside their coverage.

## Reporting a vulnerability

Use the intended [confidential security report](https://github.com/UMEBOSHIISAN/agent-frontdoor/security/advisories/new)
route after GitHub private vulnerability reporting is enabled.
Do not open a public issue, pull request, or conduct report for a suspected vulnerability.
Publication remains gated until that private route is enabled.

Include only redacted information:

- the affected core or adapter boundary and exact commit revision;
- a minimal reproduction that does not contain credentials or private paths;
- observed and expected behavior;
- security impact and the conditions required to reproduce it;
- any relevant logs after removing secrets and identifying data.

Do not include tokens, credentials, unredacted operator configuration, or real
session content.

## Response expectations

No response SLA is promised. Maintainers will assess reports according to
available capacity and will avoid making disclosure or remediation commitments
before the evidence and affected boundary are understood.
