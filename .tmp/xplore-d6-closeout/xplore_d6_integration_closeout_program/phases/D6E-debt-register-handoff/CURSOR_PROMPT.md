# D6E — Debt Register + Codex Handoff

Read all permanent D6 documents first.

## Objective

Create/update `docs/architecture/TECHNICAL_DEBT.md` with ID, problem, severity, canonical owner, why deferred, dependencies, acceptance criteria, and status for every known/new debt item.

Then create `docs/d6/CODEX_LIVE_RUN_HANDOFF.md` describing the later browser proof:
Teacher Unit → Print → PDF → Learn → Builder → Preview → Publish → Assign → learner attempt → teacher analytics.

Do not run the browser flow in Cursor.


## Protocol
1. Record branch/SHA/dirty state.
2. Inspect existing production services/tests.
3. Write a short plan.
4. Implement only this subphase.
5. Run relevant tests.
6. Record every failure and classification.
7. Write `docs/d6/reports/D6E/PHASE_REPORT.md`.
8. Update `docs/d6/D6_STATE.md` only on PASS.
9. STOP.
