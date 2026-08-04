# Implementation Handoff

## Status

Vertical slice RUN_00–RUN_10 is on branch `pageobject-integration` at monorepo `C:\Projects\lectio`.

- Import baseline tag: `pageobject-import-baseline`
- Cutover baseline tag: `pageobject-cutover-baseline`
- Legacy archive of pre-bootstrap root: `C:\Projects\lectio-legacy-20260805`
- Page package source left untouched: `C:\Projects\lectio - Copy` @ `14ca43b`

## Proven path

```text
fixture conceptual first-exposure plan
→ object writers / questions assembler
→ LectioDocumentV2 assemble + document_json envelope
→ frontend version routing → @lectio/page
→ A4 PDF fixture (page package)
```

## Reproducible commands

```powershell
cd C:\Projects\lectio
pnpm --filter @lectio/page test
pnpm --filter @lectio/page check
pnpm --filter @lectio/page pdf:fixture

cd apps\textbook-agent\backend
uv run pytest tests/resource_specs/test_page_candidates.py tests/planning/test_page_block_planner.py tests/generation tests/planning/test_page_projections.py -q
uv run python scripts/page_plan_dryrun.py

cd ..\..
python apps/textbook-agent/tools/update_lectio_page_contracts.py
pnpm --dir apps/textbook-agent/frontend exec vitest run src/lib/studio/document-version.test.ts src/lib/components/studio/LectioPageDocumentView.test.ts
```

Verification snapshot (this session): 15 backend page-object tests green; 4 frontend routing tests green; page PDF fixture report teacher 6 / student 5 pages.

## Flags

- `XPLORE_PAGE_DOCUMENTS_ENABLED` (default **true**)
- `XPLORE_PAGE_DOCUMENT_SCOPE=conceptual_first_exposure`
- `ALLOW_PAID_LLM_TESTS=0` unless explicitly evaluating live planners

## Packaging note

Prefer `@lectio/page/LectioDocumentView.svelte` and `@lectio/page/contract` subpath exports. The package barrel still pulls an AJV schema via a dist-relative path that can break outside the package.

## Still deferred

- Full application Playwright PDF against a live authenticated generation ID with `lectio_document` written through the studio writer path
- Paid LLM planner evaluation (`ALLOW_PAID_LLM_TESTS=1`)
- Wiring `apply_figure_asset_update` into live `visual_ready` merge path (helper + tests exist)
- Expanding projections into existing `planning/projections.py` v1 consumers beyond the new v2 module

## Rollback

1. Tag: `pageobject-cutover-baseline` / `pageobject-import-baseline`
2. Disable creation: `XPLORE_PAGE_DOCUMENTS_ENABLED=false` (v2 reads remain via `document_version=2`)

## Next run

Human-controlled: paid planner eval, then expand along **procedural first_exposure** only (see `EXPANSION_DECISION.md`).
