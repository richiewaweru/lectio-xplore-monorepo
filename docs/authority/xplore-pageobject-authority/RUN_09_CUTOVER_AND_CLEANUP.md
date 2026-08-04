# Cursor Run 09 — Controlled Cutover and Cleanup

## Goal

Enable v2 by default for the proven first scope and remove only code proven dead.

## Preconditions

All previous run gates green; production-like full lesson evidence exists; v1/v2 read tests green; rollback drill documented.

## Work

1. Set first-scope feature flag default according to deployment configuration.
2. Add explicit telemetry for v1/v2 creation routing and blocked v2 runs.
3. Verify disabling creation flag restores v1 creation while preserving v2 reads.
4. Generate import/reference report for candidate dead code.
5. Remove only migrated-route component selection branches with no references.
6. Do not delete legacy renderer/contracts.
7. Treat free-route deletion and runtime rename as separate optional commits, each with its own full test gate.
8. Tag cutover baseline.

## Gate

First scope creates v2 by default; rollback works; existing v1 and v2 documents open; no hidden fallback; deleted code has no references.

## Commit

`feat(xplore): enable native page documents for first slice`
