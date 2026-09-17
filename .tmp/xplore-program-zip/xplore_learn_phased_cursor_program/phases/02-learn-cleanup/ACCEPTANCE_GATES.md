# Acceptance Gates — Phase 02

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Existing generated Learn documents render.
- [ ] Existing Builder editing and save/reload work.
- [ ] No @lectio/learn public API requires print metadata.
- [ ] Page package remains independently green.
- [ ] Generation contract tests remain green or migrations are explicit and versioned.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
