# Cursor Run Protocol

Every phase prompt must be executed as an independent bounded run.

## At the start of every phase

1. Read:
   - `permanent/PROGRAM_CHARTER.md`
   - `permanent/ARCHITECTURE_BOUNDARIES.md`
   - `permanent/REUSE_POLICY.md`
   - `permanent/DATA_INVARIANTS.md`
   - the current phase contract
2. Read target-repo `docs/xplore-program/PROGRAM_STATE.md` if present.
3. Read the immediately previous phase report if present.
4. Inspect current code before planning changes.
5. Record actual current commit + dirty state.
6. Run prerequisite/baseline checks specified for the phase.

## During implementation

- Preserve unrelated dirty work.
- Prefer additive migrations.
- Do not silently rewrite existing architecture.
- Do not start later-phase features.
- Keep ownership boundaries explicit.
- Extend existing UI visual language.
- Add tests at the same time as behavior.
- If a prerequisite is broken due to prior phase work, repair only the prerequisite regression needed to proceed and record it.
- If architecture has drifted so far that the phase contract is unsafe, stop with a BLOCKED report rather than improvising a new product architecture.

## At phase completion

1. Run all phase acceptance gates.
2. Run relevant existing regression suites.
3. Write:
   - `docs/xplore-program/reports/phase-XX/PHASE_REPORT.md`
   - any phase-specific machine-readable manifest required.
4. Update `docs/xplore-program/PROGRAM_STATE.md`.
5. Commit if the user's Cursor workflow is configured to commit; otherwise report the exact resulting SHA/diff status.
6. STOP. Do not begin the next phase.
