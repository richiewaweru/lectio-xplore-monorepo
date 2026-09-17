# Cursor Prompt — R7: Architecture Guards + Compatibility Cleanup

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Add enforceable dependency guards for the new structure.

Checks should fail on:
- print importing learn
- learn importing print
- curriculum importing print/learn
- platform importing print/learn
- final product prompts placed in platform/shared
- imports from removed legacy module paths where compatibility period is complete

Remove temporary compatibility shims that are no longer needed.
Do not remove known product legacy such as `v3_studio` unless separately proven unused and explicitly within this phase's safe cleanup list.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R7/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- architecture guard runs in CI/test suite,
- no violations remain,
- compatibility shims have explicit owners/removal status,
- regressions remain green.

If blocked, stop and report rather than inventing architecture.
