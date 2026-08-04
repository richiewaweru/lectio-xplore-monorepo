# BASELINE_MAP — Exact Current Code Owners

**Repo root:** `C:\Projects\lectio`  
**Inspected:** `apps/textbook-agent` (xplore `ba677486abe0b6090caaa570906a13244989899a`), `packages/lectio-page` (`14ca43b5fac17f4c5a268eb626f3f96eac63a7be`)  
**Recorded:** 2026-08-05 (RUN_00)

## Ten owners (path:symbol)

| # | Owner | Path:symbol |
|---|---|---|
| 1 | Final legacy section-writer entry point | `apps/textbook-agent/backend/src/v3_execution/executors/section_writer.py`:`execute_section` |
| 2 | Canonical persisted final-document field | `apps/textbook-agent/backend/src/core/database/models.py`:`GenerationModel.document_json` |
| 3 | Route returning generation document | `apps/textbook-agent/backend/src/generation/v3_studio/router.py`:`get_v3_generation_document` → `GET /api/v1/v3/generations/{id}/document` |
| 4 | Frontend render route/component | Route: `apps/textbook-agent/frontend/src/routes/studio/generations/[id]/+page.svelte`; Component: `…/components/studio/V3BookletPackView.svelte` |
| 5 | PDF/export route + readiness | `…/generation/v3_studio/router.py`:`post_v3_export_pdf` → `POST /api/v1/v3/generations/{id}/export/pdf`; readiness: `data-generation-complete="true"` (wait in `pdf_export/rendering/playwright.py`) |
| 6 | Visual request + writeback | Request: `v3_execution/models.py`:`VisualGeneratorWorkOrder`; Writeback: `generation/v3_studio/generation_writer.py`:`V3GenerationWriter.merge_stream_event` (`visual_ready` → `_merge_diagram_frame`) |
| 7 | Item store + question assembly | Store: `core/database/models.py`:`PackItemModel`; Assembly: `v3_execution/assembly/section_builder.py`:`V3SectionBuilder.build_sections` (practice bucket gated by `PRACTICE_BUCKET_COMPONENTS={"practice-stack"}`) |
| 8 | Projection functions (legacy fields) | `planning/projections.py`:`_revision_sections`, `_copy_component_section`, `_compose_document`, `build_composition_payload` |
| 9 | SSE events | Active studio stream is poke+poll (`connectV3StudioGenerationStream`); backend catalog in `v3_execution/runtime/events.py`; chunked planning switches named stage2_* events |
| 10 | Contract-sync tooling | `apps/textbook-agent/tools/update_lectio_contracts.py` (legacy `lectio` package). Page package: `packages/lectio-page` script `export-contracts`. Successor for page contracts: to be added in RUN_01 as `tools/update_lectio_page_contracts.py` |

## Key symbols

| Symbol | Location |
|---|---|
| `ComponentSlot` | `v3_blueprint/planning/models.py` |
| `run_component_selector` | `planning/agents.py`; wired from `planning/bridge.py` |
| `SectionContent` | Backend mirror `contracts/section_content.py`; frontend via npm `lectio` |
| `_component_order` | Written in `V3SectionBuilder.build_sections` |
| `BLOCK_FIELD_ORDER` | **Not present** in live monorepo source (docs/npm-only history) |

## Downstream flow (confirmed)

```text
skeleton slot.allowed_components
  → planning.bridge + run_component_selector
  → ComponentSelection → SectionPlan.components: ComponentSlot[]
  → execute_section → GeneratedComponentBlock
  → V3SectionBuilder.build_sections
  → GenerationModel.document_json
  → GET …/document → V3BookletPackView
  → POST …/export/pdf → Playwright @ /studio/print/{id}
```

## Toolchain discovered

| Surface | Commands |
|---|---|
| Page package | `pnpm test`, `pnpm check`, `pnpm build`, `pnpm pdf:fixture` (cwd `packages/lectio-page`) |
| App frontend | `pnpm check`, `pnpm test`, `pnpm build` (cwd `apps/textbook-agent/frontend`) |
| Backend | `uv run pytest` / `pytest` from `apps/textbook-agent/backend` (pyproject markers exclude integration/postgres by default) |
| Root wrappers | `page:test`, `page:check`, `page:pdf`, `app:check`, `app:test`, `contracts:sync` in root `package.json` |

## Caveats

1. Studio SSE is document-polling; do not assume live `component_ready` canvas wiring.
2. Item generation has two lanes: `PackItemModel` diagnostics vs `GeneratedQuestionBlock` practice.
3. `packages/lectio-page` has no live `SectionContent` / `BLOCK_FIELD_ORDER`.
4. Frontend still depends on npm `lectio` for v1; `@lectio/page` workspace dep added in RUN_06.
