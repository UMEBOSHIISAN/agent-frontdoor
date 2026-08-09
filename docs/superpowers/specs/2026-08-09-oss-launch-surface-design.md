# Agent Frontdoor OSS Launch Surface

**Date:** 2026-08-09
**Status:** Human-approved design
**Selected approach:** Integrated OSS launch surface

## Goal

Present Agent Frontdoor as one coherent AI agent safety gateway rather than as
a small collection of task-card and Intent Lock features. A first-time reader
must be able to understand the product, install it, reproduce a useful result,
inspect its evidence, and find the appropriate support or contribution path
without mistaking documentation, identity checks, or hooks for execution
authority.

The primary public promise is:

> Stop AI coding agents from drifting beyond the task you approved.

Task cards, validation, boundary-drift detection, Intent Lock, human gates,
optional lifecycle hooks, and offline evidence are parts of that one gateway.

## Baseline and problem statement

The current repository is strong on fail-closed contracts and explicit
non-authority boundaries, but its public surface is evaluator-oriented rather
than adoption-oriented:

- the first Python demonstration appears before installation;
- the source-oriented quick start contains a repository URL placeholder and
  validates a test fixture rather than a user-owned example;
- the README leads with Intent Lock while the four CLI commands operate on task
  cards, without an early route selector;
- detailed schema and fixture reference material dominates the main reader
  journey;
- the optional adapter has no documented, non-live smoke test before settings
  activation;
- package metadata, public examples, support routes, and GitHub community files
  are incomplete;
- relative README assets and adapter links are not all safe when rendered from
  the core source distribution;
- internal planning and audit labels are exposed as if they were public product
  documentation.

The public GitHub baseline observed for the default branch of
`UMEBOSHIISAN/agent-frontdoor` through GitHub's Community Profile and repository
APIs on 2026-08-09 is 42% community-profile health, zero repository topics, and
no release. These are baseline facts, not quality or adoption scores. The
redesign must not imply that a package, release, audit, or compatibility claim
exists before it is independently verified.

## Audience and first successful outcome

The primary reader is a developer or team lead using a tool-capable coding agent
such as Codex or Claude Code who has experienced adjacent-task drift.

Within the first screen, the reader should understand:

1. what kind of drift Agent Frontdoor blocks;
2. that the core evaluates data and does not execute commands;
3. that intent identity is separate from authority; and
4. that runtime hooks are optional, local, and explicitly activated.

Within 60 seconds after installation, a reader should be able to validate a
curated task card that they can copy and edit. Within five minutes, they should
be able to run a deterministic Intent Lock example or a disposable adapter
smoke test without modifying live Codex or Claude Code settings.

## Public reader journey

The root README will use progressive disclosure in this order:

1. Product name, literal one-line promise, concise Japanese summary, and a
   polished integrated hero.
2. A small before/after example showing an exact task and an adjacent action
   being denied without executing either string.
3. A compact architecture path:
   `Task Card -> Validation -> Drift Detection -> Intent Lock -> Human Gate -> Safe Handoff`.
4. A copy-paste source install using the canonical public repository URL,
   followed by a user-owned example and stable expected output.
5. A three-route selector:
   - validate task cards with the four-command core CLI;
   - evaluate action consistency with the Intent Lock Python API;
   - integrate optional lifecycle hooks only after a local smoke test.
6. An evidence-at-a-glance block containing only reproducible, correctly scoped
   measurements.
7. A concise safety model, platform limits, and explicit non-goals.
8. A documentation map, support and contribution routes, license, and project
   status.

Long schema inventories, task-class tables, gate definitions, drift families,
offline-receiver instructions, and adapter internals move behind clearly named
documentation links. The README remains complete as an entrypoint without
remaining the canonical reference for every detail.

## Documentation ownership

Each topic has one canonical owner to prevent drift and duplication:

| Topic | Canonical public owner |
| --- | --- |
| Product value, shortest success path, route selection | `README.md` |
| Source install, first task card, expected output, uninstall | `docs/GETTING_STARTED.md` |
| Component boundaries and data flow | `docs/ARCHITECTURE.md` |
| Reproducible measurements, corpus, commands, caveats | `docs/EVIDENCE.md` |
| Schema, CLI, gates, exit codes, drift reference | `docs/CORE_REFERENCE.md` |
| Intent Lock state machine and limitations | `docs/INTENT_LOCK.md` |
| Optional hook install, smoke test, activation, rollback | `adapters/README.md` |
| Common failures and safe recovery | `docs/TROUBLESHOOTING.md` |
| Advanced offline receiver workflow | `docs/FRIEND_LAB.md` |
| Runnable example index and expected results | `examples/README.md` |
| Contribution, support, conduct, vulnerability reports | Root community files |

Cross-document summaries stay short and link to their canonical owner. Relative
links used by package long descriptions must either be included in the relevant
distribution or replaced with verified canonical GitHub links.

## Visual system

The public surface retains the existing dark navy, indigo, and green palette but
uses it as serious infrastructure/security language rather than generic neon AI
decoration.

Required assets:

1. A 1280 x 640 social-preview image below 1 MB, suitable for GitHub sharing.
   It depicts one constrained path passing through a clear review gate and uses
   the exact Agent Frontdoor name.
2. An integrated README hero that communicates the whole gateway, not only task
   validation or Intent Lock.
3. An accessible, deterministic vector architecture diagram with exact labels
   and alt text. It shows where the read-only core ends, where the optional
   state-writing adapter begins, and where human authority remains external.

AI image generation may supply the polished illustrative layer. Exact product
text, component labels, measurements, and architecture arrows must remain
deterministic and manually verifiable. No UMEBOSHI character, likeness, trained
model output, site identity, or other excluded brand IP may appear.

Badges are limited to facts with a durable public backing. There will be no CI,
coverage, security-audit, download, release, or compatibility badge until that
fact has a public source and has been measured.

## Evidence model

The README contains a short evidence snapshot; `docs/EVIDENCE.md` contains the
measurement protocol. Initial verified corpus facts are:

| Signal | Current evidence |
| --- | --- |
| Positive task-card fixtures | 31/31 validate |
| Negative task-card fixtures | 41/41 rejected with the expected issue codes |
| Drift expectations | 16/16 detected |
| Safe controls | 4/4 remain unblocked |
| Core execution/network/worker/routing/source-write paths | 0 by hard boundary tests |

The full-suite result is a dated, commit-bound observation: 836 tests passed on
commit `e866efa025f5299d638adfb4bf903a8de2594c0e`. It belongs in the detailed
evidence record because the count changes as tests are added. The README must
not turn it into a timeless badge or hard-coded quality claim.

Every measurement includes:

- the measurement date and tested commit;
- the exact local reproduction command;
- the fixture or test corpus being measured;
- the expected output or invariant;
- a statement that fixture-corpus regression evidence is not generalized
  real-world effectiveness, a security audit, or a semantic-accuracy benchmark.

No percentage is published without a numerator, denominator, and scoped
definition. No adoption number, star forecast, performance benchmark, platform
compatibility, or independent-audit claim is invented.

## Examples and safe onboarding

The repository gains a curated `examples/task-card.json` that is independent of
the regression fixture corpus, plus a runnable pure-Python Intent Lock example.
`examples/README.md` lists each example, command, expected exit status, expected
result, and lesson.

The adapter guide gains a non-live smoke test using:

- a disposable state directory;
- a synthetic event on standard input;
- no changes to operator-owned settings;
- expected allow/deny/report behavior;
- cleanup and rollback instructions.

Live activation remains manual and reviewable. Installation alone must never be
described as activation.

## Community and repository health

The local repository will add:

- `CONTRIBUTING.md` with focused and full verification paths;
- `SECURITY.md` with supported scope, explicit non-security-boundary language,
  and only a verified private reporting route;
- `CODE_OF_CONDUCT.md` with no placeholder enforcement contact;
- `SUPPORT.md` separating usage help, bugs, design proposals, and confidential
  security reports;
- focused bug and feature issue forms plus issue-template configuration;
- a pull-request template that asks for scope, tests, safety-boundary impact,
  and documentation changes.

The repository will not add CI workflows as part of this documentation project.
CI/CD is a separately governed execution area and is not required to make the
local public surface coherent.

A confidential-reporting claim is publication-blocking unless its route is
measured. The implementation must first verify an existing private channel. If
none exists, the local documents may be prepared against GitHub private
vulnerability reporting, but the branch must not be published until the human
has separately authorized that repository setting and the endpoint has been
enabled and rechecked. No email address, contact method, or availability claim
may be invented to satisfy a checklist.

Package metadata will use verified project, documentation, issue, changelog, and
source URLs. Descriptions will represent the integrated gateway while keeping
the core and optional adapter distributions distinct. Metadata must not claim a
PyPI release or supported platform that has not been measured.

## Release and public-state truth

The changelog and README must describe 0.2 work as unreleased until a tag and
release are measured. Static release-looking badges are removed or replaced by
truthful project-status text. No `pip install` command, PyPI badge, GitHub
release, or release date is advertised unless the corresponding public artifact
exists.

External state changes are deliberately separate from local documentation work:

- push the feature branch and create a draft pull request;
- set the GitHub description and a small accurate topic set;
- upload the social preview;
- optionally enable and verify GitHub private vulnerability reporting.

These actions occur only after operator-managed GitHub authentication, a final
scope review, and the human writing this exact repository publication token in
the active thread:

`DEPLOY_APPROVED:github.com/UMEBOSHIISAN/agent-frontdoor`

That token authorizes only the reviewed feature-branch push, draft pull request,
repository description, approved topic set, and social-preview upload described
by this design. It does not authorize a merge, release, package upload, secret or
credential change, hook activation, or repository security-setting mutation.

Enabling GitHub private vulnerability reporting, if required, has its own
separate target and requires this exact token:

`DEPLOY_APPROVED:github.com/UMEBOSHIISAN/agent-frontdoor/settings/private-vulnerability-reporting`

The setting must be re-read after mutation before the reporting route can be
called verified. Release creation, PyPI upload, deployment, live settings
changes, and hook activation are not included.

## Safety, privacy, and public wording

Public documentation must keep these invariants prominent:

- task identity is not execution authority;
- the core is read-only and side-effect free;
- the optional adapter writes only privacy-minimized local state;
- hooks are not a security boundary;
- unknown or malformed input fails closed where the contract specifies it;
- local platform and event coverage limitations remain explicit;
- no private paths, tokens, credentials, raw prompts, session IDs, or
  operator-owned configuration are published.

Internal labels such as `REPEATED_EXCESSIVE_DERAILMENT`,
`CODEX_SELF_CONFIDENT_ADOPTED`, and `CC_UNAUDITED` are converted into ordinary
public disclosure. The durable public statement is that no independent security
audit has been completed. Internal incident and orchestration provenance remains
available in Git history rather than on the product landing page.

Completed Superpowers design and implementation plans under `docs/superpowers/`
will be removed from the final published tree after all durable contracts have
been transferred to public documentation. Git history remains the recovery path.

## Implementation scope

Expected modifications:

- `README.md`
- `CHANGELOG.md`
- `MANIFEST.in`
- `pyproject.toml`
- `adapters/README.md`
- `adapters/pyproject.toml`
- `docs/INTENT_LOCK.md`
- `docs/FRIEND_LAB.md`
- existing documentation and distribution tests

Expected additions:

- `docs/GETTING_STARTED.md`
- `docs/ARCHITECTURE.md`
- `docs/EVIDENCE.md`
- `docs/CORE_REFERENCE.md`
- `docs/TROUBLESHOOTING.md`
- `examples/README.md`
- `examples/task-card.json`
- `examples/intent_lock_demo.py`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `SUPPORT.md`
- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/feature.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/pull_request_template.md`
- final visual assets under `assets/`

Expected removals after extraction are limited to these completed internal
artifacts:

- `docs/superpowers/plans/2026-08-09-intent-lock.md`
- `docs/superpowers/plans/2026-08-09-intent-lock-readme.md`
- `docs/superpowers/specs/2026-08-09-intent-lock-readme-design.md`
- `docs/superpowers/specs/2026-08-09-oss-launch-surface-design.md`
- `docs/superpowers/plans/2026-08-09-oss-launch-surface.md`

Before each removal, the implementation must verify that the artifact is
complete and that every durable contract it contains exists in a canonical
public document. No glob or directory-wide deletion is permitted.

The implementation may reduce this file set where duplication would add no
reader value, but it may not silently expand into runtime behavior, automatic
configuration, CI/CD, release engineering, deployment, or credential work.

## Verification strategy

Documentation behavior is implemented test-first where an automated contract is
valuable:

1. Assert the new reader journey, canonical documentation map, truthful status,
   safety wording, and absence of stale internal labels.
2. Validate every advertised example and its documented output.
3. Test that public relative links and image references resolve in the checkout.
4. Verify the core and adapter source distributions contain the public files
   their package descriptions reference while preserving the two-distribution
   boundary.
5. Run focused README, example, packaging, privacy, and adapter tests.
6. Reproduce the published fixture measurements from the existing metric tests.
7. Run the complete pytest suite and record the dated result against the tested
   commit.
8. Inspect rendered Markdown and all final raster/vector assets.
9. Scan the final diff for private paths, tokens, internal process residue,
   unsupported claims, placeholders, and unrelated changes.
10. Obtain an independent code/documentation review before publication.

## Acceptance criteria

- The repository presents one integrated gateway with a clear first-use wedge,
  not competing task-card and Intent Lock products.
- A new reader can copy, install, and reach one expected success without editing
  a placeholder or touching live agent settings.
- Each of the three usage routes states its prerequisites, expected outcome, and
  safety boundary.
- Stable evidence is visible near the adoption path and every detailed number is
  reproducible, dated where necessary, and correctly caveated.
- The social preview, hero, and architecture diagram are coherent, accessible,
  inspected, and free of excluded brand IP.
- Root and adapter package metadata, manifests, docs, examples, and links agree
  about what is available and what remains unreleased.
- Community files offer real, non-placeholder contribution, support, conduct,
  and confidential-reporting routes; publication remains blocked until the
  private route has been measured.
- No CI workflow, release, package publication, deployment, live configuration,
  credential change, or automatic hook activation is introduced.
- Focused tests, packaging checks, metric reproduction, the full suite, privacy
  scans, and independent review all pass on the final tree.
- Push, draft-PR creation, and GitHub metadata changes occur only after their
  explicit external-publication gate is satisfied.
