# Cursor Master Prompt — Phase 00: Baseline + Reuse Inventory + Guardrails

You are implementing **only Phase 00** of the Xplore Learn Expansion program.

## First: recover program context

Read, in this order:

1. `permanent/PROGRAM_CHARTER.md`
2. `permanent/ARCHITECTURE_BOUNDARIES.md`
3. `permanent/REUSE_POLICY.md`
4. `permanent/DATA_INVARIANTS.md`
5. `permanent/VISUAL_DESIGN_CONTINUITY.md`
6. `permanent/RUN_PROTOCOL.md`
7. this phase's `IMPLEMENTATION_CONTRACT.md`
8. this phase's `ACCEPTANCE_GATES.md`

Then inspect the target repo's:
- `docs/xplore-program/PROGRAM_STATE.md`, if present
- `docs/xplore-program/BASELINE_REUSE_MANIFEST.json`, if present
- the immediately previous phase report, if this is not Phase 00

Do **not** ask the user to paste prior reports if they exist in the repo. Read them yourself.

## Phase goal

Establish factual current-state knowledge, golden regressions, reuse classifications, and persistent program state before implementation.

## Operating rule

**Inspect first. Reuse proven seams. Extend before replacing.**

Do not create a second Builder, second lesson document store, second persistence layer, second component renderer, or second generation pipeline merely because the new product domain needs additional behavior. Reuse or extend the existing seam unless you can demonstrate that its ownership/contract makes that unsafe.

## Execution

1. Record current branch/SHA/dirty state.
2. Verify prerequisites and relevant existing tests.
3. Trace the specific existing paths this phase will extend.
4. Write a short implementation plan grounded in actual files.
5. Implement only the in-scope contract.
6. Add/adjust tests.
7. Run every acceptance gate.
8. Repair failures caused by this phase.
9. Write the report using `PHASE_REPORT_TEMPLATE.md` to:
   `docs/xplore-program/reports/phase-00/PHASE_REPORT.md`
10. Update `docs/xplore-program/PROGRAM_STATE.md` only if PASS.
11. Do not begin Phase 1.

## Stop conditions

Stop with a BLOCKED report if:
- prerequisite phase is not actually complete,
- current code materially contradicts a permanent product invariant and safe bounded reconciliation is not possible,
- required destructive migration would risk existing Page or Component production behavior,
- test failures cannot be confidently attributed and repaired within this phase.

Do not conceal uncertainty by inventing parallel architecture.
