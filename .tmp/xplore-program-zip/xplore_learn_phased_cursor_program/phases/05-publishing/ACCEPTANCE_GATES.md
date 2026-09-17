# Acceptance Gates — Phase 05

    The phase is PASS only if all applicable gates below are demonstrated with commands/tests/manual evidence.

    - [ ] Generate→edit→student preview→publish v1 works.
- [ ] Post-publish edit does not mutate v1.
- [ ] Publish v2 creates a distinct retrievable release.
- [ ] Release hashes/version provenance are stable.
- [ ] Only valid LearnDocuments can publish.

    ## Regression gate
    - [ ] Relevant existing tests/build/checks remain green.
    - [ ] Any baseline failure that pre-existed this phase is clearly distinguished from a new regression.
    - [ ] No later-phase capability was partially introduced without explicit necessity.

    ## Report gate
    - [ ] `PHASE_REPORT.md` records files changed, schema changes, tests, reuse decisions, new-file justification, known limitations, and exact final git status/SHA.
    - [ ] `docs/xplore-program/PROGRAM_STATE.md` is updated only after phase gates pass.
