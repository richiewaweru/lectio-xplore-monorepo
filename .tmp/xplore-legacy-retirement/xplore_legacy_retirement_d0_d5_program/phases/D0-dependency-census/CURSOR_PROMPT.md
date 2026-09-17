# D0 — Legacy Dependency Census

Read permanent docs, state, manifest, and previous report first.

## Objective
Map every remaining historical subsystem and all dependencies:
imports, API routes, frontend consumers, workers/startup, DB, telemetry, config/env, exports, tests, scripts, docs.
Classify each as MIGRATE_AND_DELETE / DELETE_NOW / KEEP_CANONICAL / DATA_RETIREMENT_REQUIRED / UNKNOWN_BLOCKER.
Write docs/legacy-retirement/LEGACY_DEPENDENCY_MANIFEST.json and retirement order.
No deletion yet.

## Protocol
1. Record branch/SHA/dirty state.
2. Inspect actual call sites.
3. Write short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write docs/legacy-retirement/reports/D0/PHASE_REPORT.md
7. Update LEGACY_STATE only on PASS.
8. STOP.
