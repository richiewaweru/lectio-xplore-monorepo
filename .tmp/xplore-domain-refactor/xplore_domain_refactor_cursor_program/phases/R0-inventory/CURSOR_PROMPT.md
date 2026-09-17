# Cursor Prompt — R0: Inventory + Ownership Manifest

Read the permanent refactor documents again before starting this phase.

Also read:
- `docs/refactor-program/REFACTOR_STATE.md` if it exists
- previous phase report if applicable
- `docs/refactor-program/OWNERSHIP_MANIFEST.json`

## Phase objective

Create a complete factual ownership map before any moves.

Tasks:
- Record current SHA/dirty state.
- Inventory backend/frontend/packages/tests relevant to curriculum/print/learn/platform.
- Classify each meaningful module as CURRICULUM, PRINT, LEARN, PLATFORM, REMOVE_LATER, or NEEDS_SEAM_EXTRACTION.
- Identify import hotspots/cycles and public import paths.
- Record baseline test commands and golden paths.
- Produce a machine-readable ownership manifest.
- Do not move product code.


## Execution requirements

1. Record starting SHA and dirty state.
2. Inspect actual imports/usages before moving files.
3. Write a short move plan listing source → destination and why.
4. Use mechanical moves first; semantic cleanup second.
5. Keep API/routes/contracts/DB behavior stable.
6. Run phase-specific and cross-domain regressions.
7. Write `docs/refactor-program/reports/R0/PHASE_REPORT.md`.
8. Update `docs/refactor-program/REFACTOR_STATE.md` only on PASS.
9. STOP. Do not begin the next phase.

## Acceptance

PASS when:
- ownership manifest covers all top-level backend domains and feature frontend folders,
- baseline Page/Learn/Builder tests are recorded and green or failures are documented,
- ambiguous modules are explicitly marked instead of guessed,
- current dependency graph is documented.

If blocked, stop and report rather than inventing architecture.
