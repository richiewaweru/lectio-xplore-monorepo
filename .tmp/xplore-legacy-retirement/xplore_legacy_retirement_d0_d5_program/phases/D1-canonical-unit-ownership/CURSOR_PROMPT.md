# D1 — Canonical Unit Ownership

Read permanent docs, state, manifest, and previous report first.

## Objective
Move real Unit orchestration implementation into application/unit_lesson/.
Evacuate planning.bridge/path-preparation facades into prepare/dispatch/status/contracts.
Rewire supported callers.
Temporary shims only when strictly necessary.
PASS only when application/unit_lesson owns implementation, not re-exports.

## Protocol
1. Record branch/SHA/dirty state.
2. Inspect actual call sites.
3. Write short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write docs/legacy-retirement/reports/D1/PHASE_REPORT.md
7. Update LEGACY_STATE only on PASS.
8. STOP.
