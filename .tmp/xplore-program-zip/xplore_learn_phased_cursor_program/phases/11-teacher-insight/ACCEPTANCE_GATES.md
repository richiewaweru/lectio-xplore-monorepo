# Acceptance Gates — Phase 11

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Teacher sees only authorized classes/learners.
- [ ] Dashboard aggregates reconcile with raw attempt fixtures.
- [ ] Practice and graded results remain separate.
- [ ] First-attempt vs eventual success is correct.
- [ ] Misconception aggregation traces to stable evidence.
- [ ] Projection rebuild produces same analytics.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
