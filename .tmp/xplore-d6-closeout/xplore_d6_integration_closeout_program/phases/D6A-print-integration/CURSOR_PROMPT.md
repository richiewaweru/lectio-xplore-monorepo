# D6A — Unit → Print Integration

Read all permanent D6 documents first.

## Objective

Build/strengthen a deterministic integration test:
Unit → PathLesson → application orchestration → Print planning → form plan → writers → persist/assemble → reload → @lectio/page validate → PDF.

Use real DB and production services. Fake only external providers. Add one recoverable failure/retry assertion. Do not construct the final document directly in the test.


## Protocol
1. Record branch/SHA/dirty state.
2. Inspect existing production services/tests.
3. Write a short plan.
4. Implement only this subphase.
5. Run relevant tests.
6. Record every failure and classification.
7. Write `docs/d6/reports/D6A/PHASE_REPORT.md`.
8. Update `docs/d6/D6_STATE.md` only on PASS.
9. STOP.
