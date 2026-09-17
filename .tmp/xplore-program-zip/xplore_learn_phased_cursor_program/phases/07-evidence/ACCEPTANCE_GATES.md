# Acceptance Gates — Phase 07

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Every meaningful scored interaction can trace learner→attempt→node→release→path lesson→concept→unit.
- [ ] Multi-concept node can emit correct weighted/bound evidence rows.
- [ ] Misconception evidence is stable where configured.
- [ ] Concept-state projection can be deleted and rebuilt from raw evidence.
- [ ] Classification thresholds are documented and testable.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
