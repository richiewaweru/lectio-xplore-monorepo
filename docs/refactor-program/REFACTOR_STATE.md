# REFACTOR_STATE

- current_phase: (complete)
- last_completed_phase: R8
- current_sha: a5e68a2 (working tree R0–R8 uncommitted)
- dirty_state: domain refactor complete on branch `refactor/domain-ownership`

## Completed
- [x] R0 Inventory
- [x] R1 Backend Print
- [x] R2 Backend Learn
- [x] R3 Curriculum + Platform (`infra/` implements target `platform/`)
- [x] R4 Prompts/Writers/Resources
- [x] R5 Frontend
- [x] R6 Package rename (`packages/lectio` → `packages/lectio-learn`)
- [x] R7 Guards/Cleanup
- [x] R8 Full verification

## Temporary compatibility shims
Retained (see R7 report for removal conditions). Do not delete until call sites migrated.

## Unresolved ownership seams
See `docs/refactor-program/reports/R8/PHASE_REPORT.md`.

## Naming map
- Target architecture `platform/` → package `infra/` (Python stdlib `platform` collision)

## Deferred product fixes
See `permanent/KNOWN_DEFERRED_FIXES.md`, `DEFERRED_FINDINGS.md`, and R8 deferred→target path table.
