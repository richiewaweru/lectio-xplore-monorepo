# Cursor Prompt — R4: Prompts, Writers, Validators, Resources

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Clean the remaining ambiguous realization machinery.

Move final prompts, writers, validators, resource catalogues/candidates and render helpers into the product path that owns their output.

Do not deduplicate Print and Learn prompts simply because they resemble each other.

Split mixed resource modules only when the split is mechanical and behavior-preserving.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R4/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- searching for Print prompts/writers/resources leads under `print/`,
- searching for Learn prompts/writers/resources leads under `learn/`,
- generic platform contains no final product prompts,
- regression outputs remain unchanged.

If blocked, stop and report rather than inventing architecture.
