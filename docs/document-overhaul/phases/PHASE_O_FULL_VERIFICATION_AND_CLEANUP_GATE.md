# Phase O — Full Verification and Cleanup Gate

## Goal
Prove the new architecture from fresh lesson creation through both independent paths and prove the old production architecture is gone.

## Open these active files first
- `package.json`
- `apps/textbook-agent/backend/tests/`
- `apps/textbook-agent/frontend/`
- `packages/lectio-page/`
- `packages/lectio-contracts/`
- `tools/xplore-program/`
- `apps/textbook-agent/tools/agent/`

## Implementation tasks
- Run baseline static/unit/integration suites.
- Run multiple fresh Unit → Teaching Plan → Learn generations.
- Run multiple fresh Unit → Teaching Plan → Print generations.
- Generate Learn first then Print from the same Teaching Plan; repeat in reverse.
- Exercise all six document primitives.
- Exercise every retained interaction end to end.
- Exercise Learn edit/save/reload and local regeneration.
- Exercise Print reload and PDF generation.
- Exercise recoverable failure/retry at composition, writer and interaction stages.
- Run zero-legacy and dependency-boundary searches.
- Run a clean-install/clean-checkout verification if feasible.
- Record exact commit SHA and all command outputs in the final report.

## Expected outputs
- `final validation report`
- `fresh Learn artifact evidence`
- `fresh Print/PDF artifact evidence`
- `zero-legacy evidence`
- `final architecture map`

## Acceptance gate
No critical gate is waived. New Print and Learn flows pass from fresh source data, and the old ordinary content-component generation architecture cannot be reached.
