# Phase C — Delete Residual V1 Learn Salvage

## Goal

Finish the clean cut from the retired ordinary component Learn architecture.

## Tasks

- Trace every caller of v1/salvage helpers before deletion.
- Migrate tests/callers to LearnDocument v2.
- Delete primitive→`explanation-block` host remapping.
- Delete v1-only generation/salvage helpers and dead imports/fixtures.
- Preserve only genuinely historical migration references.
- Run zero-reference searches.

## Gate

PASS only if there is no executable v1 ordinary-content Learn generation/salvage path in active source.

## Required evidence

- files changed/deleted
- exact commands/results
- canonical call graph
- positive live proof
- negative proof excluding prior wrong behavior
- PASS / FAIL / BLOCKED
