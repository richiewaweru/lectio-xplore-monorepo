# Cursor Prompt — C1: Canonical Unit-Path Wiring

Reread all permanent documents first. Then read cleanup state, reachability manifest, and previous report if applicable.

## Objective

Make the Unit path the explicit canonical application flow.

- Introduce/use a thin `application/unit_lesson/` orchestration seam where genuinely needed.
- Rewire app.py, routes, startup and workers to current curriculum/print/learn/infra modules.
- Remove old module names as canonical entrypoints.
- Keep API behavior stable.
- Do not broadly delete legacy code yet.

PASS only when Unit→Print and Unit→Learn each have one supported orchestration graph and app/startup imports resolve.

## Protocol
1. Record starting SHA/branch/dirty state.
2. Inspect actual code.
3. Write a short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write `docs/cleanup-program/reports/C1/PHASE_REPORT.md`.
7. Update `docs/cleanup-program/CLEANUP_STATE.md` only on PASS.
8. STOP.

If uncertain whether something is dead, reclassify it rather than guessing.
