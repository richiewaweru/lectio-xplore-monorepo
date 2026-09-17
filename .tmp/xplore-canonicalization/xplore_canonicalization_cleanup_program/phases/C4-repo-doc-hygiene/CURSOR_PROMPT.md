# Cursor Prompt — C4: Repository + Documentation Hygiene

Reread all permanent documents first. Then read cleanup state, reachability manifest, and previous report if applicable.

## Objective

Clean non-code repository noise.

- Remove committed temp packs.
- Remove stale implementation-run reports/evidence/packs.
- Fold durable knowledge into current docs.
- Remove docs referencing removed paths.
- Remove stale scripts/assets/fixtures not required by active flows.
- Keep migrations and required schema history.

Target durable docs: `docs/architecture/`, `docs/runbooks/`, `docs/adr/`, plus a concise current README.

PASS only when active docs describe the current system and no required artifact was removed.

## Protocol
1. Record starting SHA/branch/dirty state.
2. Inspect actual code.
3. Write a short execution plan.
4. Execute only this phase.
5. Run relevant regressions.
6. Write `docs/cleanup-program/reports/C4/PHASE_REPORT.md`.
7. Update `docs/cleanup-program/CLEANUP_STATE.md` only on PASS.
8. STOP.

If uncertain whether something is dead, reclassify it rather than guessing.
