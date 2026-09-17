# Cursor Prompt — R5: Frontend Feature Ownership

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Reorganize frontend library code by durable feature ownership.

Target:
- `shared/`
- `curriculum/`
- `print/`
- `learn/authoring`
- `learn/student`
- `learn/distribution`
- `learn/insight`

Keep SvelteKit route URLs stable.
Route files should become thin entrypoints where practical.
Preserve existing visual behavior.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R5/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- route URLs and user-visible behavior are unchanged,
- Builder remains the same editing surface,
- Learn student/class/insight code is easy to locate,
- shared UI contains only genuinely shared primitives,
- frontend checks/tests pass.

If blocked, stop and report rather than inventing architecture.
