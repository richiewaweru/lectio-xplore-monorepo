# D2 — Evacuate Live Consumers

Read permanent docs, state, manifest, and previous report first.

## Objective
For every MIGRATE_AND_DELETE subsystem:
move useful implementation to application/curriculum/print/learn/infra;
update backend/frontend/package consumers;
update workers/startup/tests;
split mixed modules;
allow thin Print/Learn duplication when it removes mode-switch coupling.
Do not do destructive DB cleanup yet.

## Protocol
1. Record branch/SHA/dirty state.
2. Inspect actual call sites.
3. Write short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write docs/legacy-retirement/reports/D2/PHASE_REPORT.md
7. Update LEGACY_STATE only on PASS.
8. STOP.
