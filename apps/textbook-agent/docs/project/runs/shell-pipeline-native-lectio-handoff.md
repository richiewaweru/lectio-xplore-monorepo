# Handoff: Shell + Pipeline + Native Lectio

**Status**: implemented and validated
**Related runbook**: `docs/project/runs/shell-pipeline-native-lectio-overhaul.md`
**Architecture**: `backend/src/textbook_agent` shell + `backend/src/pipeline` engine + native Lectio frontend

## Implementation Report

| Area | Outcome | Primary files |
| --- | --- | --- |
| Backend architecture | The repo now treats `textbook_agent` as the product shell and `pipeline` as the only live generation engine. | `backend/src/pipeline/run.py`, `backend/src/textbook_agent/interface/api/routes/generation.py`, `agents/project.md`, `docs/project/ARCHITECTURE.md` |
| Generation engine | Live generation now runs through typed pipeline contracts, graph execution, QC events, and structured `PipelineDocument` output. | `backend/src/pipeline/api.py`, `backend/src/pipeline/run.py`, `backend/src/pipeline/graph.py`, `backend/src/pipeline/events.py` |
| Persistence | HTML artifact persistence was replaced by JSON document persistence, including partial save updates while sections stream in. | `backend/src/textbook_agent/domain/ports/document_repository.py`, `backend/src/textbook_agent/infrastructure/repositories/file_document_repo.py`, `backend/src/textbook_agent/infrastructure/repositories/sql_generation_repo.py` |
| Public API | The live API now centers on generation records, SSE events, document fetch, and draft enhancement. Legacy `/generate`, `/status`, and HTML textbook delivery are no longer the live path. | `backend/src/textbook_agent/interface/api/routes/generation.py`, `backend/src/textbook_agent/application/dtos/generation_request.py`, `backend/src/textbook_agent/application/dtos/generation_status.py` |
| Frontend | The dashboard uses Lectio registries locally, generation pages hydrate from saved document JSON, and section updates arrive over `EventSource`. The iframe viewer and polling flow are gone from the live app. | `frontend/src/routes/dashboard/+page.svelte`, `frontend/src/routes/textbook/[id]/+page.svelte`, `frontend/src/lib/components/LectioDocumentView.svelte`, `frontend/src/lib/api/client.ts` |
| Legacy demolition | The old orchestrator, renderer stack, HTML repository path, model catalog live path, and polling-only generation flow were removed from the active architecture. | `backend/src/textbook_agent/application/orchestrator.py` (deleted), `backend/src/textbook_agent/infrastructure/renderer/` (deleted), `frontend/src/lib/components/TextbookViewer.svelte` (deleted), `frontend/src/lib/generation/progress.ts` (deleted) |
| Architecture guard | The architecture checker now enforces the shell rules inside `textbook_agent` and separately forbids `pipeline -> textbook_agent` imports. | `tools/agent/check_architecture.py`, `tools/agent/tests/test_check_architecture.py`, `docs/project/context-summary.yaml` |
| Docs | Project docs now describe the shell + pipeline split and native Lectio runtime as the source of truth. | `README.md`, `CLAUDE.md`, `docs/project/README.md`, `docs/project/SCHEMAS.md`, `docs/project/SETUP.md` |

## What Changed

- Replaced the old `TextbookAgent` generation path with `pipeline.run`.
- Replaced HTML-first artifacts with persisted JSON `PipelineDocument` artifacts.
- Replaced status polling and HTML textbook fetch with SSE events plus `/document` hydration.
- Rebuilt the frontend generation flow around local Lectio template and preset registries.
- Removed the legacy orchestrator, renderer, and polling viewer code from the live path.
- Updated the architecture rules and validation tooling to recognize the shell + pipeline split.

## Current State

- The backend now has one live generation architecture: shell + pipeline.
- The shell owns auth, profiles, generation records, persistence, and HTTP transport.
- The pipeline owns graph orchestration, typed generation contracts, section assembly, streaming events, and final `PipelineDocument` construction.
- The frontend renders native Lectio sections and reconnects from saved JSON documents rather than HTML.
- Draft generations can still be enhanced into a higher mode using seeded document input.

## Validation

| Command | Result |
| --- | --- |
| `python tools/agent/check_architecture.py --format text` | Passed with no architecture violations |
| `uv sync --all-extras` | Completed successfully |
| `uv run pytest` in `backend/` | `56 passed` |
| `npm test` in `frontend/` | `8 files passed, 26 tests passed` |
| `npm run check` in `frontend/` | Passed with `0 errors, 0 warnings` |
| `npm run build` in `frontend/` | Passed |
| `python tools/agent/validate_repo.py --scope all` | Passed end to end |

## Not Done Yet

- A concrete production SvelteKit adapter still needs to replace `adapter-auto`.
- The frontend production build still emits non-failing chunk-size and circular chunk warnings.
- This branch does not have a recorded pre-overhaul baseline test capture, so validation evidence is final-state only.

## Start Here

1. Read `docs/project/runs/shell-pipeline-native-lectio-overhaul.md` for the execution checklist and validation record.
2. Read `backend/src/textbook_agent/interface/api/routes/generation.py` to understand the live shell contract, SSE flow, and draft enhancement entrypoints.
3. Read `backend/src/pipeline/run.py` to see the public engine boundary and event emission flow.
4. Read `backend/src/textbook_agent/infrastructure/repositories/file_document_repo.py` and `backend/src/textbook_agent/infrastructure/repositories/sql_generation_repo.py` to understand document persistence and generation metadata storage.
5. Read `frontend/src/routes/dashboard/+page.svelte` and `frontend/src/routes/textbook/[id]/+page.svelte` to understand the new generation UX and native Lectio viewer flow.

## Risks

- Do not reintroduce shell imports into `backend/src/pipeline`; the architecture guard now treats that as a first-class violation.
- Be careful with any future frontend routing or deployment work until the production SvelteKit adapter is chosen.
- Historical docs under `docs/v0.1.0/` and archived prompt material describe the old HTML pipeline; treat them as archival context, not live architecture guidance.

## Recommended Next Moves

1. Choose and wire the production SvelteKit adapter.
2. Add a small manual smoke checklist for real browser verification of create, stream, reload, and enhance flows.
3. If bundle growth continues, investigate the frontend build warnings before they become deployment pain.
