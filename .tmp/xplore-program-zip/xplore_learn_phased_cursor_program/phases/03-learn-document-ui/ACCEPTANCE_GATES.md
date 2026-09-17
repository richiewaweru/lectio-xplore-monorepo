# Acceptance Gates — Phase 03

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] One real existing generated lesson renders in Builder unchanged and in student shell as sections/stages.
- [ ] Section order is canonical and deterministic.
- [ ] No learner state is written into LearnDocument.
- [ ] Responsive behavior works across representative breakpoints.
- [ ] Existing visual design tokens/components are reused.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
