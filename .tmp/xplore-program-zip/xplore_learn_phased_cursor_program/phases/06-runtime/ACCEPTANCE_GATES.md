# Acceptance Gates — Phase 06

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Learner can start release, answer, leave, resume, and finish.
- [ ] Wrong→wrong→correct creates three immutable attempts.
- [ ] Duplicate submission ID does not double-score.
- [ ] Same learner can have separate LearningInstances for same release.
- [ ] Progress is rebuildable from attempts.
- [ ] Published release remains immutable.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
