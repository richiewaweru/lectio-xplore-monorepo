# Acceptance Gates — Phase 01

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Page golden path works from the monorepo.
- [ ] Component golden generation→Builder→edit→save→reload works from the monorepo.
- [ ] Workspace package resolution is local and deterministic.
- [ ] Boundary guards pass.
- [ ] No duplicate app/backend subsystem is retained without documented ownership.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
