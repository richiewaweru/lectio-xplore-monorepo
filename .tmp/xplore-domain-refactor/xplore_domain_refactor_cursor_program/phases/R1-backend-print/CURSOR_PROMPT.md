# Cursor Prompt — R1: Backend Print Ownership

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Move only clearly Print-owned backend code into `src/print/`.

Expected candidates include:
- `planning/whole_lesson`
- `generation/page_objects`
- Print-specific resource candidates
- PDF/export and Page-only figure/rendering machinery where safely movable
- Print-owned prompts/writers/validators

Use compatibility re-exports only where required to keep the move mechanical.
Do not touch Learn behavior.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R1/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- Page tests/check/golden PDF remain behaviorally identical,
- all moved Print modules resolve under `src/print`,
- Learn tests remain green,
- no Print→Learn imports exist,
- old paths are removed or documented temporary compatibility shims.

If blocked, stop and report rather than inventing architecture.
