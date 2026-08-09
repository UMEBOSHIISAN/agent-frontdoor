## Summary

- Describe the bounded change and the problem it addresses.

## Scope

- List the files or interfaces changed and any explicitly excluded work.

## Verification

- [ ] Added or updated a focused test first and observed the expected failure.
- [ ] Ran the relevant focused tests successfully.
- [ ] Ran `python3 -m pytest -q` successfully.
- [ ] Ran a private-data scan and removed credentials, private paths, and identifying data.

## Safety boundary

- [ ] The read-only core still performs no task execution, runtime network access, worker invocation, or source writes.
- [ ] Task identity is not presented as authorization; independent human gates remain external.
- [ ] Optional adapter state and hook activation remain separate from the core and operator controlled.

## Documentation and packaging

- [ ] Updated or verified affected public documentation and runnable examples.
- [ ] Reviewed affected manifests, package data, and core/adapter distribution boundaries.

## Release truth

- [ ] This pull request does not imply a published release, deployment, live hook activation, or repository-settings change.

## Related issue

- Link the relevant issue without including confidential report contents.
