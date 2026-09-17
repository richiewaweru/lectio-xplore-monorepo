# D4 — Database Dependency Retirement

Read permanent docs, state, manifest, and previous report first.

## Objective
Classify legacy DB objects as ACTIVE / HISTORICAL_DATA_ONLY / MIGRATE_DATA_THEN_DROP / DROP_SAFE.
Prove Unit readers/writers.
Move needed ORM ownership.
Remove obsolete ORM/repository code.
Use explicit migrations for data/drop actions.
Preserve migration history.
Verify existing upgrade, clean bootstrap, ORM metadata.

## Protocol
1. Record branch/SHA/dirty state.
2. Inspect actual call sites.
3. Write short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write docs/legacy-retirement/reports/D4/PHASE_REPORT.md
7. Update LEGACY_STATE only on PASS.
8. STOP.
