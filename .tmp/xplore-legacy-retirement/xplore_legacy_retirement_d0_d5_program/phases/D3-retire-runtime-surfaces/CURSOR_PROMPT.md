# D3 — Retire Routes Jobs Telemetry Config

Read permanent docs, state, manifest, and previous report first.

## Objective
Unmount unsupported APIs and old studio/block/non-Unit flows.
Remove frontend callers.
Remove obsolete workers/startup hooks.
Migrate/delete telemetry tied only to retired flows.
Remove stale env vars, flags, selectors, scripts, CI commands, exports.
PASS only when no operational surface invokes unsupported paths.

## Protocol
1. Record branch/SHA/dirty state.
2. Inspect actual call sites.
3. Write short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write docs/legacy-retirement/reports/D3/PHASE_REPORT.md
7. Update LEGACY_STATE only on PASS.
8. STOP.
