# Phase 02 execution plan (fresh after Phase 01 PASS)

## Goal
Sharpen workspace `packages/lectio-learn` into web-native `@lectio/learn` without breaking Builder or generated Learn documents; keep `@lectio/page` independently green.

## Inspected facts
- Package lives at `packages/lectio-learn`, name `lectio@0.6.0`, exports `.`, `./theme.css`, `./print`, contracts, components.
- Frontend has ~many `from 'lectio'` imports (Builder + Studio views). Some routes still call `providePrintMode` for Component Lectio print chrome — not Page Print.
- Per-component `print.ts` specs and `lib/print/` utilities exist; print-registry-compliance tests enforce print metadata.
- Print product remains `@lectio/page` + whole_lesson (must stay green).

## Steps
1. Add optional web-facing metadata types (interaction / responseEvaluation / narration / learnerBand / a11y) on registry/component meta without breaking existing schemas.
2. Soft-deprecate public `./print` export and stop requiring print metadata for Learn public API (compliance test → web-native or skip print-required assertions for Learn package).
3. Rename package to `@lectio/learn` (keep path `packages/lectio-learn` OR move to `packages/lectio-learn` — prefer rename in place with package.json name change to minimize churn).
4. Update frontend + workspace deps: `lectio` → `@lectio/learn`; keep temporary alias if needed for one release — prefer clean cut since monorepo-only.
5. Rebuild package; run Learn package tests, Builder/frontend focused tests, Page package tests, domain boundary (already knows `@lectio/learn`).
6. Report + PROGRAM_STATE.

## Explicit non-goals
- No student runtime persistence
- No assignments
- No Page editor
- No arbitrary component redesign
- Do not delete Print product (`@lectio/page`)
