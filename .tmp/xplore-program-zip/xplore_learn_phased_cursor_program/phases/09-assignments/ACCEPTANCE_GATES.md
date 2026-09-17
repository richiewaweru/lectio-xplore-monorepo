# Acceptance Gates — Phase 09

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Published lesson can be assigned to one/multiple classes.
- [ ] Selected-student assignment works.
- [ ] Late joiner receives still-active rolling assignment exactly once.
- [ ] Snapshot assignment does not add late joiner.
- [ ] Same release reassigned later creates distinct LearningInstance context.
- [ ] Permissions enforced server-side.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
