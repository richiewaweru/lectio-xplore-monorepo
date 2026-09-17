# D6C — Learn Distribution + Runtime

Read all permanent D6 documents first.

## Objective

Build/strengthen integration:
LearnRelease → class/assignment → recipient → LearningInstance → runtime load → attempt/progress → analytics.

Use current production semantics. Do not redesign known defects here. Add adversarial checks for another learner/class/release where feasible.


## Protocol
1. Record branch/SHA/dirty state.
2. Inspect existing production services/tests.
3. Write a short plan.
4. Implement only this subphase.
5. Run relevant tests.
6. Record every failure and classification.
7. Write `docs/d6/reports/D6C/PHASE_REPORT.md`.
8. Update `docs/d6/D6_STATE.md` only on PASS.
9. STOP.
