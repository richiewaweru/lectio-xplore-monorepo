# Implementation Contract — Phase 12: End-to-End Hardening + Recorded Golden Runs

    ## Goal
    Prove the whole system as one product, verify architectural invariants, repair only evidenced defects, and produce final handoff evidence.

    ## In scope
    1. Run real end-to-end flows across representative learner bands/subjects.
2. Verify generation, editing, preview, publishing, release immutability, classes, rolling assignments, runtime, scoring, resume, evidence, analytics.
3. Run adversarial cases: post-publish edits, duplicate network submission, late join, selected learner, same release assigned twice, malformed/changed evaluator config, permission probes.
4. Audit dependency boundaries and new-file/subsystem justifications.
5. Run Page regressions to prove Learn expansion did not break Print.
6. Produce final architecture/state report and live-test checklist for human inspection.

    ## Explicitly out of scope
    - Do not add major new features during hardening.
- Do not use hardening as an excuse for architecture rewrite without reproduced failure.

    ## Required approach

    1. Inspect the current implementation before creating or replacing anything.
    2. Apply the permanent REUSE/EXTEND/REFACTOR/REMOVE/NEW classification.
    3. Reuse current Xplore visual primitives for any UI added in this phase.
    4. Preserve unrelated dirty work.
    5. Prefer additive schema migrations and reversible changes.
    6. Add tests with behavior.
    7. Do not begin later phases.
    8. Record architecture deviations rather than silently changing the north star.
