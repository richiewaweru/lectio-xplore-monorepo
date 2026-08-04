# Cursor Run 01 — Contract Sync and Heading Hierarchy

## Goal

Make Lectio page contracts reproducibly consumable by Python and ensure section titles render exactly once as section headings.

## Work

1. Inspect existing legacy Lectio contract-sync tooling and reuse its conventions.
2. Add `tools/update_lectio_page_contracts.py`.
3. Sync canonical page schema, intent catalogue, object catalogue, version manifest, and generated Python models/adapters into committed backend paths.
4. Make sync idempotent: running twice leaves no diff.
5. Add hash/version drift tests.
6. Add shared valid/invalid fixtures consumed by TypeScript and Python tests.
7. In page package renderer, make document title h1 and `section.title` visible h2.
8. Ensure no duplicate title appears when first block is prose.
9. Preserve nested heading object capability as h3; do not expose it to planner yet.
10. Run page package tests/check/build/PDF and backend contract tests.

## Do not

- add `StanceSpec`;
- change intent/object catalogue contents unless a concrete contract defect blocks the run;
- change application generation;
- make backend runtime depend on sibling filesystem paths.

## Gate

- sync idempotent;
- contract drift test green;
- Python validates canonical document fixture;
- page fixture renders section title once;
- package PDF gate green.

## Commit

`feat(contracts): sync lectio page contracts into backend`
