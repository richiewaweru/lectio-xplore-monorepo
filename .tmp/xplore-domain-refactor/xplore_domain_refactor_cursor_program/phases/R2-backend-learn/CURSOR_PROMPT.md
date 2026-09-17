# Cursor Prompt — R2: Backend Learn Ownership

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Move clearly Learn-owned backend code into `src/learn/`.

Expected candidates:
- `generation/component_lectio`
- Builder backend services/routes if they are Learn-only
- LearnRelease publishing
- runtime
- classes/distribution
- evidence
- analytics
- Learn component resources

Keep application API paths unchanged unless a route import-only change is required.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R2/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- Component generation→Builder→publish/runtime tests remain green,
- Page remains green,
- Learn-owned modules are discoverable under `src/learn`,
- HTTP API behavior remains unchanged,
- no Learn→Print imports exist.

If blocked, stop and report rather than inventing architecture.
