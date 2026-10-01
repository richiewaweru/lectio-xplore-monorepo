# Deletion and Zero-Caller Plan

Every temporary compatibility seam must document:

```text
why it exists
who calls it
what proves deletion safe
which phase deletes it
```

## After Learn cutover

Delete old Learn ordinary composition/writing, Teaching Plan→ordinary-content logic, obsolete prompts/tests and selection machinery used only by the old path.

## After Print cutover

Delete independent Print ordinary composition/writing, obsolete composition bridge behaviour, duplicated Teaching Plan interpretation, old prompts/tests.

## After runtime convergence

Delete superseded path-specific stage/retry/checkpoint/progress logic, replaced workers, old status normalization, zero-called V2/V3 capability constants.

## After API/frontend cutover

Delete obsolete `/v3` routes, compatibility DTOs and old frontend creation/polling flows.

## After DB proof

Drop obsolete tables/columns/state blobs.

## Proof

Before deletion inspect:
- static imports/calls;
- route registration;
- worker startup;
- dynamic indirection;
- frontend callers;
- test-only callers.

Delete, run full suite, then add/update architecture guard.
