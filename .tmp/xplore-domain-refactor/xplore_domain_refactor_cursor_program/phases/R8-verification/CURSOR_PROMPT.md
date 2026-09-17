# Cursor Prompt — R8: Full Refactor Verification + Final Map

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Run the complete structural verification.

Tasks:
- full relevant Page/Learn/backend/frontend regression suites,
- import graph audit,
- DB metadata/Alembic sanity,
- Page golden fixture,
- Component generation/Builder fixture,
- publish/runtime/distribution/analytics existing tests,
- compare behavior/output where golden fixtures exist,
- document final tree,
- document unresolved ownership seams,
- document deferred product bugs without fixing them.

Produce final handoff report for the post-refactor vertical-integration phase.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R8/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- all prior gates remain green,
- final tree matches ownership principles,
- no unresolved cross-domain import violations exist,
- behavior changes are zero or explicitly proven pre-existing,
- deferred runtime/integrity fixes have clear target paths in the new architecture.

If blocked, stop and report rather than inventing architecture.
