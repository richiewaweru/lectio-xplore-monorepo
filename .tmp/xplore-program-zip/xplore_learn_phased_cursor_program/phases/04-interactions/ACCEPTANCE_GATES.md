# Acceptance Gates — Phase 04

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Representative interactions evaluate deterministic correct/incorrect/partial outcomes.
- [ ] Existing passive Learn content still renders.
- [ ] Interaction contracts are serializable and validate strictly.
- [ ] Keyboard/accessibility basics are covered for new interactions.
- [ ] A fixture lesson can be completed in-memory.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
