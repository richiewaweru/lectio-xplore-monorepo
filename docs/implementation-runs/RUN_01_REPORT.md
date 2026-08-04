# Run 01 Report

## Result
DONE

## Baseline
- start SHA: e0ba54d
- branch: pageobject-integration
- relevant pre-existing failures: none for page/contract gates

## Implemented
- Section title renders as visible `h2.lectio-section-title`
- Nested heading blocks clamped to h3 (document h1 / section h2 ownership)
- `tools/update_lectio_page_contracts.py` syncs schema/catalogues/manifest + generated Python adapter
- Facade `contracts/lectio_page.py` with hash verification and JSON Schema validation
- Drift + fixture tests under `tests/contracts/test_lectio_page_contracts.py`
- Shared fixtures in `backend/tests/fixtures/lectio-page/`

## Files changed
| file | reason |
|---|---|
| packages/lectio-page/src/lib/render/SectionView.svelte | section.title h2 |
| packages/lectio-page/src/lib/render/objects/HeadingView.svelte | nested headings as h3 |
| packages/lectio-page/src/lib/normalize/document.ts | heading ownership comment |
| packages/lectio-page/src/lib/print/base-print.css | section title styles |
| packages/lectio-page/src/lib/render/heading-hierarchy.test.ts | hierarchy tests |
| apps/textbook-agent/tools/update_lectio_page_contracts.py | sync script |
| apps/textbook-agent/backend/contracts/lectio-page/* | synced snapshots |
| apps/textbook-agent/backend/src/contracts/generated/lectio_page.py | generated literals |
| apps/textbook-agent/backend/src/contracts/lectio_page.py | facade |
| apps/textbook-agent/backend/tests/contracts/test_lectio_page_contracts.py | drift/parity |
| apps/textbook-agent/backend/tests/fixtures/lectio-page/* | valid/invalid fixtures |

## Verification
| command | result | evidence |
|---|---|---|
| sync script ×2 | idempotent | no content churn beyond first write |
| `pnpm test` (page) | PASS | `_run01_page_test.log` |
| `pnpm check` (page) | PASS | `_run01_page_check.log` |
| `uv run pytest tests/contracts/test_lectio_page_contracts.py` | PASS 6/6 | terminal |

## Contract checks
- invariants checked: no StanceSpec; legacy update_lectio_contracts untouched; section title once as h2
- legacy behavior checked: generation pipeline unchanged

## Deviations
None.

## Blockers / risks
None.

## Rollback
- commit(s): this RUN_01 commit
- command: `git revert HEAD`

## Next run readiness
READY — RUN_02_PLANNING_CONTRACTS_AND_CANDIDATES.md
