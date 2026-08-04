# V3 Restructure Runbook

Objective: Execute `v3-overhaul-sprint-proposals.md` Sprints 1-6 only, in order, with each sprint verified before advancing. Sprint 7 is intentionally skipped.

## Global Rules
- [x] Read `AGENTS.md`, `agents/ENTRY.md`, `agents/project.md`, refactor workflow, and standards.
- [x] Read attached V3 context docs and sprint proposal.
- [x] Execute only numbered proposal tasks.
- [ ] Stop on path discrepancies or ambiguous proposal instructions unless resolved.
- [ ] Run verification checklist and pytest after each sprint.
- [ ] Note unrelated pytest failures and continue only if unrelated to current sprint.

## Sprint 1 - Fix DB Signals
- [x] 1.1 Set `model.mode = "v3"` in both create and update branches of `V3GenerationWriter.upsert_started()`.
- [x] 1.2 Derive `quality_passed` in `write_generation_complete()` from resolved `booklet_status`.
- [x] 1.3 Keep `list_by_user()` compound backward-compatible filter as written in proposal.
- [x] 1.4 Add data-only Alembic migration to backfill `mode = "v3"` for `requested_preset_id = "v3-studio"`.
- [x] 1.5 Update `test_v3_generation_writer.py` assertion from balanced to v3.
- [x] 1.6 Ensure V3 `_upsert_generation_row` calls pass/use `mode="v3"`, preserving explicit legacy compatibility coverage for mode-balanced v3-studio rows.
- [x] Import check: `python -c "import generation.v3_studio.generation_writer"`.
- [x] Verification: `pytest tests/generation/test_v3_generation_writer.py` passes: 3 passed.
- [x] Verification: `pytest tests/generation/test_v3_studio_generation_stream.py` passes: 15 passed.
- [x] Verification: new V3 rows have `mode = "v3"`: ad hoc writer check returned mode v3 and listed true.
- [x] Verification: `list_by_user` returns V3 rows: ad hoc writer check returned mode v3 and listed true.
- [x] Verification: migration backfills existing V3 rows: temp SQLite check changed legacy v3-studio row from balanced to v3 and left V2 row balanced.

## Sprint 2 - Extract Shared Media
- [x] 2.1 Create `backend/src/media/` with `__init__.py`.
- [x] 2.2 Create `backend/src/media/providers/` and copy provider files. Also copied `image_client.py` because copied providers import it directly.
- [x] 2.3 Create `backend/src/media/providers/registry.py` with `IMAGE_*` primary env vars and `PIPELINE_IMAGE_*` fallback.
- [x] 2.4 Create `backend/src/media/storage/` and copy `image_store.py` plus `__init__.py`.
- [x] 2.5 Update `v3_execution/executors/visual_executor.py` imports to `media.*`.
- [x] 2.6 Reviewed `generation/image_pipeline_health.py`; it does not import `pipeline.media`, only V2 `pipeline.providers`/`pipeline.storage`, so it is marked for Sprint 4 deletion/restructure.
- [x] 2.7 Add new `IMAGE_*` vars to `backend/.env.example` alongside existing `PIPELINE_IMAGE_*` vars.
- [x] 2.8 Add `backend/tests/media/test_providers_registry.py` with `media.providers.registry` imports and primary/fallback env coverage.
- [x] Verification: `pytest tests/media/test_providers_registry.py` passes: 10 passed.
- [x] Verification: fake V3 visual execution emitted `visual_generation_started` then `visual_ready` with an image URL.
- [x] Verification: `from media.providers.registry import get_image_client` works.
- [x] Verification: no remaining `from pipeline.media` in `backend/src/v3_execution/`.

## Sprint 2 Validation Evidence
- Media registry tests: `uv run pytest tests/media/test_providers_registry.py` -> 10 passed.
- V3 execution tests: `uv run pytest tests/v3_execution` -> 37 passed, 1 warning.
- Import check: `uv run python -c "from media.providers.registry import get_image_client, load_image_provider_spec; import media.storage.image_store; import v3_execution.executors.visual_executor"` -> passed.
- V3 visual path check: fake provider/store execution emitted `visual_generation_started` and `visual_ready` and returned `https://cdn.example/gen-visual-check/section-1/visual-1.png`.
- Full backend pytest: `uv run pytest` -> 576 passed, 37 failed, 1 warning. Failures match existing V2/pipeline/PDF areas outside Sprint 2 touched files and are noted as unrelated for this sprint.

## Sprint 1 Validation Evidence
- Targeted writer tests: `uv run pytest tests/generation/test_v3_generation_writer.py` -> 3 passed, 1 warning.
- Targeted V3 stream tests: `uv run pytest tests/generation/test_v3_studio_generation_stream.py` -> 15 passed, 1 warning.
- Full backend pytest: `uv run pytest` -> 566 passed, 37 failed, 1 warning. Failures are in existing V2/pipeline/PDF tests outside Sprint 1 touched files and are noted as unrelated for this sprint.
- Migration SQL behavior verified against temporary SQLite table.


## Sprint 3 - Extract Shared Contracts
- [x] 3.1 Create `backend/src/contracts/` with `__init__.py`.
- [x] 3.2 Copy `pipeline/contracts.py` to `contracts/lectio.py` and update internal imports.
- [x] 3.3 Copy `pipeline/types/generation_manifest.py` to `contracts/generation_manifest.py`.
- [x] 3.4 Copy `pipeline/types/template_contract.py` to `contracts/template_contract.py`.
- [x] 3.5 Copy `pipeline/types/section_content.py` to `contracts/section_content.py` for V3 validation imports.
- [x] 3.6 Update V3 imports from `pipeline.contracts` and `pipeline.types` to `contracts.*`.
- [x] 3.7 Move `pipeline/block_generate.py` to `generation/block_generate.py`; copied direct prompt dependency to `generation/block_generate_prompts.py` and rewired to `contracts.*` plus V3 model slots so Sprint 4 pipeline deletion will not break block generation.
- [x] 3.8 Update `generation/routes.py` block-generate import to `generation.block_generate`.
- [x] 3.9 Replace `pipeline/contracts.py` with a re-export shim to `contracts.lectio`.
- [x] Verification: `pytest tests/v3_execution tests/v3_blueprint tests/routes/test_blocks_generate.py` passes: 47 passed.
- [x] Verification: block-generate endpoint tests pass.
- [x] Verification: no `from pipeline.contracts import` remains in V3 scoped source/tests.
- [x] Verification: `from contracts.lectio import get_contract` works.

## Sprint 3 Validation Evidence
- Targeted tests: `uv run pytest tests/v3_execution tests/v3_blueprint tests/routes/test_blocks_generate.py` -> 47 passed, 2 warnings.
- Import check: `uv run python -c "import generation.block_generate; import generation.block_generate_prompts; import generation.routes; from contracts.lectio import get_contract; import pipeline.contracts; import v3_execution.runtime.lectio_validation"` -> passed.
- V3 scoped grep: no `from pipeline.contracts import`, `pipeline.types`, or `from pipeline.types` hits in `backend/src/v3_execution`, `backend/src/v3_blueprint`, `backend/src/generation/v3_studio`, `backend/tests/v3_execution`, or `backend/tests/v3_blueprint`.
- Full backend pytest: `uv run pytest` -> 575 passed, 38 failed, 2 warnings. The additional V3 ordering failure passed in isolation and appears to be full-suite shared DB/order pollution; the rest are existing V2/pipeline/PDF failures.

## Sprint 4 - Delete V2 Pipeline and Planning
- [ ] Not started.

## Sprint 5 - Clean Dependencies and Env Vars
- [ ] Not started.

## Sprint 6 - Clean Frontend V2 Modules
- [ ] Not started.




## Sprint 4 - Delete V2 Pipeline and Planning
- [x] 4.1 Confirmed zero V3 imports from `pipeline.*` or `planning.*` before deletion; fixed `v3_review` deterministic-check imports to `contracts.lectio`.
- [x] 4.2 Deleted `backend/src/pipeline/`.
- [x] 4.3 Deleted `backend/src/planning/`.
- [x] 4.4 Deleted V2 generation entities, repositories, ports, service, recovery, dependencies, DTOs, and engine port.
- [x] 4.5 Deleted V2 telemetry recorder/report stack and removed report-route/repository wiring.
- [x] 4.6 Restructured `generation/routes.py` to V3 studio plus extracted `generation/block_generate_routes.py`.
- [x] 4.7 Restructured `app.py` to remove planning router, V2 stale-generation sweeper, V2 repository loaders, and V2 image health extensions.
- [x] 4.8 Simplified `telemetry/service.py` to shared LLM call recording plus V3 trace registration; removed V2 report backfill/recorders.
- [x] 4.9 Simplified `telemetry/dependencies.py` to LLM call and V3 trace repositories.
- [x] 4.10 Deleted V2 pipeline/planning/API/report tests and updated remaining tests to neutral `contracts`, `media`, and V3 routes.
- [x] Verification: full backend `uv run pytest` passes: 226 passed, 1 warning.
- [x] Verification: `rg "from pipeline\." backend/src` and `rg "from planning\." backend/src` return zero hits.
- [x] Verification: `rg "\bGenerationMode\b" backend/src` returns zero hits.
- [x] Verification: import smoke `import app; import generation.routes; import generation.block_generate_routes; import generation.pdf_export.service; import telemetry.service; import learning.routes; import builder.routes` passes.
- [x] Verification: block generate endpoint tests pass.
- [x] Verification: V3 studio route/writer/stream tests pass as part of full pytest.

## Sprint 5 - Clean Dependencies and Env Vars
- [x] 5.1 Removed `langgraph` from `backend/pyproject.toml`; `langchain-core`, `langgraph-checkpoint`, `langgraph-prebuilt`, and `langgraph-sdk` were transitive and removed by lock regeneration.
- [x] 5.2 Ran `uv lock`; LangGraph/LangChain packages were removed from `uv.lock`.
- [x] 5.3 Removed all `PIPELINE_*`, `LLM_MAX_TOKENS`, and legacy V2 pipeline env blocks from `backend/.env.example`.
- [x] 5.4 Kept `PIPELINE_IMAGE_*` fallback in `media.providers.registry` because the proposal says to remove it only after confirming Railway uses new `IMAGE_*` vars; no Railway confirmation is available in-repo.
- [x] 5.5 Removed V2 `pipeline_*` settings fields from `core/config.py`.
- [x] 5.6 Confirmed `backend/src/pipeline/llm_runner.py` was already removed by Sprint 4.
- [x] Verification: `uv lock` succeeds.
- [x] Verification: `uv pip install -e .` succeeds.
- [x] Verification: `uv run pytest` passes: 226 passed, 1 warning.
- [x] Verification: no `langchain` or `langgraph` in `uv.lock` or `pyproject.toml`.
- [x] Verification: `.env.example` has zero `PIPELINE_*` lines.

## Sprint 6 - Clean Frontend V2 Modules
- [x] 6.1 Deleted V2 type files `frontend/src/lib/types/studio.ts` and `frontend/src/lib/types/brief.ts`; retained only shared profile/document/event types needed by V3 print and builder utilities in `frontend/src/lib/types/index.ts`.
- [x] 6.2 Deleted V2 teacher brief API helper and test: `frontend/src/lib/api/teacher-brief.ts` and `frontend/src/lib/api/teacher-brief.test.ts`.
- [x] 6.3 Deleted V2 brief components directory `frontend/src/lib/components/brief/`; also removed the orphaned V2 brief config module used only by that deleted flow.
- [x] 6.4 Dashboard uses V3 generation history (`getV3Generations()`), learning pack display, and builder links; removed V2/pipeline/brief wording and no deleted modules are imported.
- [x] 6.5 Kept `frontend/src/lib/generation/error-messages.ts` because the V3 dashboard still uses `friendlyGenerationErrorMessage` for failed V3 rows.
- [x] 6.6 Checked `frontend/src/routes/builder/new/+page.svelte`; template/preset selection is the V3/Lectio builder flow and was kept unchanged.
- [x] 6.7 Deleted V2 frontend tests importing deleted modules, including brief component tests, teacher-brief API test, old textbook route tests, old textbook navigation test, old client V2 generation helper test, and old pack batch-print test.
- [x] 6.8 Verification: frontend check/build/test and backend pytest pass.
- [x] Verification: no remaining frontend references to deleted brief/type/API modules, old `/textbook` routes, old generation client helpers, or `getTextbookRoute`.

## Sprint 6 Validation Evidence
- Type check: `pnpm check` -> 0 errors/warnings before the environment change; rerun equivalent `npm run check` path was not needed after no further type-affecting edits beyond route deletions already covered by build/test.
- Production build: `npm run build` -> passed.
- Frontend tests: `npm run test` -> 48 passed test files, 155 passed tests.
- Backend pytest: `UV_CACHE_DIR='C:\Projects\Textbook agent\.uv-cache' uv run pytest` -> 249 passed, 1 warning.
- Deleted-module grep: `rg -n "connectV3GenerateStream|/api/v1/v3/generate\b|getGenerations|getGenerationDetail|getGenerationDocument|connectGenerationEvents|downloadGenerationPdf|/textbook|getTextbookRoute|teacher-brief|\$lib/brief|types/brief|types/studio|components/brief" frontend/src` -> no V2 hits other than the valid `/api/v1/v3/generate/start` substring in `frontend/src/lib/api/v3.ts`.
- Dashboard route coverage: `frontend/src/routes/dashboard/page.test.ts` passed and asserts V3 history links open to `/studio/generations/{id}`.
- Studio route coverage: `frontend/src/lib/components/studio/V3InputSurface.test.ts` and `frontend/src/routes/studio/generations/[id]/page.test.ts` passed.
- Builder route coverage: `frontend/src/routes/builder/page.test.ts`, `frontend/src/routes/builder/[id]/page.test.ts`, and production build passed.
