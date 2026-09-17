# Acceptance Gates — Phase 12

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] All prior phase gates remain green.
- [ ] At least one full teacher→student→analytics golden run passes.
- [ ] Representative PP/primary/older learner lesson runs pass where fixtures/content permit.
- [ ] Page golden PDF remains green.
- [ ] Permissions/idempotency/immutability adversarial tests pass.
- [ ] Final report identifies residual limitations honestly.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
