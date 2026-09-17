# Cursor Prompt — R6: Physical Package Alignment

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Rename the physical `packages/lectio` directory to `packages/lectio-learn` so filesystem and npm identity align.

Update workspace paths, lockfiles, imports/config references and tests mechanically.

Do not alter `@lectio/learn` public behavior.
Do not modify `@lectio/page` behavior.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R6/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- workspace resolves `@lectio/learn` from `packages/lectio-learn`,
- package tests/build pass,
- frontend resolves the local workspace package,
- no stale `packages/lectio` path references remain except historical docs.

If blocked, stop and report rather than inventing architecture.
