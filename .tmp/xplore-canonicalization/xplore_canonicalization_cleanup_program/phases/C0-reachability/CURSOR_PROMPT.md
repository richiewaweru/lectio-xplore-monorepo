# Cursor Prompt — C0: Reachability Audit

Reread all permanent documents first. Then read cleanup state, reachability manifest, and previous report if applicable.

## Objective

No product-code changes.

- Record SHA/branch/dirty state.
- Enumerate mounted FastAPI routes, startup workers, SvelteKit product routes, package exports and production scripts.
- Trace Unit→Print and Unit→Learn call graphs.
- Classify every meaningful backend/frontend/package/docs area.
- Identify old non-Unit paths, stale docs/packs/temp artifacts, mixed modules, cycles and shims.
- Produce `docs/cleanup-program/REACHABILITY_MANIFEST.json`.

PASS only when the supported graphs and deletion/split candidates are evidence-backed.

## Protocol
1. Record starting SHA/branch/dirty state.
2. Inspect actual code.
3. Write a short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write `docs/cleanup-program/reports/C0/PHASE_REPORT.md`.
7. Update `docs/cleanup-program/CLEANUP_STATE.md` only on PASS.
8. STOP.

If uncertain whether something is dead, reclassify it rather than guessing.
