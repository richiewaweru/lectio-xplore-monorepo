# D6D — Regression + Architecture Gates

Read all permanent D6 documents first.

## Objective

Run:
- zero-legacy guard
- backend domain boundary guard
- package Print/Learn boundary guard
- ORM metadata
- Alembic head/upgrade sanity
- @lectio/page tests/check
- @lectio/learn tests/build
- focused backend integration suite
- frontend tests/typecheck/build

Classify every failure as refactor regression, pre-existing product defect, test-harness defect, or environment limitation. Do not silently exclude failing canonical tests.


## Protocol
1. Record branch/SHA/dirty state.
2. Inspect existing production services/tests.
3. Write a short plan.
4. Implement only this subphase.
5. Run relevant tests.
6. Record every failure and classification.
7. Write `docs/d6/reports/D6D/PHASE_REPORT.md`.
8. Update `docs/d6/D6_STATE.md` only on PASS.
9. STOP.
