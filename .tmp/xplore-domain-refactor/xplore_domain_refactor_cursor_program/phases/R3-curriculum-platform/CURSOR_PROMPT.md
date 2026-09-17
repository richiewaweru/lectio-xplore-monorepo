# Cursor Prompt — R3: Curriculum + Platform Extraction

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Rehome truly shared semantic and infrastructure modules.

Curriculum:
- unit/path/concept/objective/teaching-plan semantics used before realization.

Platform:
- auth primitives
- DB session/migration infrastructure
- LLM provider/client/retry
- storage/media primitives
- telemetry/logging/config

Do not move ambiguous code merely to complete the diagram.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R3/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- dependency direction is platform/curriculum ← print/learn,
- curriculum/platform do not import product domains,
- DB metadata/migrations still load,
- existing runtime/generation behavior remains unchanged.

If blocked, stop and report rather than inventing architecture.
