# Acceptance Gates — Phase 00

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Existing component generation/edit/reload path is demonstrably green or failures are precisely documented.
- [ ] Existing page render/PDF path is demonstrably green or failures are precisely documented.
- [ ] BASELINE_REUSE_MANIFEST.json exists and identifies canonical source/target paths.
- [ ] PROGRAM_STATE.md exists in target repo.
- [ ] No feature behavior changed.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
