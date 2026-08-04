# Implementation Handoff

## Status
Vertical slice through RUN_09 is implemented on branch `pageobject-integration` at monorepo `C:\Projects\lectio`.

## Proven path
```text
fixture conceptual first-exposure plan
→ object writers / questions assembler
→ LectioDocumentV2 assemble + document_json envelope
→ frontend version routing → @lectio/page
→ A4 PDF fixture (page package)
```

## Commands
- Page tests: `pnpm --filter @lectio/page test`
- Page PDF: `pnpm --filter @lectio/page pdf:fixture`
- Backend candidates/planner/writers: `uv run pytest tests/resource_specs/test_page_candidates.py tests/planning/test_page_block_planner.py tests/generation -q`
- Contract sync: `python apps/textbook-agent/tools/update_lectio_page_contracts.py`
- Dry-run plans: `uv run python scripts/page_plan_dryrun.py` (from backend)

## Flags
- `XPLORE_PAGE_DOCUMENTS_ENABLED` (default true)
- `XPLORE_PAGE_DOCUMENT_SCOPE=conceptual_first_exposure`
- `ALLOW_PAID_LLM_TESTS=0` unless explicitly evaluating live planners

## Still deferred / next expansion
See `EXPANSION_DECISION.md`. Full application Playwright PDF against a live generation ID still needs a seeded backend generation with `lectio_document` persisted through the studio writer path.

## Rollback
- Tag: `pageobject-import-baseline`, `pageobject-cutover-baseline`
- Disable creation: `XPLORE_PAGE_DOCUMENTS_ENABLED=false`
