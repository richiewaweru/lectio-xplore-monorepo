# Agent Context

This file is the descriptive source of truth for the current live system shape. Code in `backend/src/` and `frontend/src/` remains authoritative.

## Current Runtime Shape

- `backend/src/core/` holds shared auth, config, database, events, and generic LLM utilities.
- `backend/src/planning/` owns Teacher Studio brief workflows and the bridge into generation.
- `backend/src/generation/` owns persistence, orchestration, SSE, detail/history APIs, and PDF export.
- `backend/src/telemetry/` owns saved reports and LLM usage reporting.
- `backend/src/pipeline/` is the only live lesson-generation engine.
- `backend/src/app.py` assembles the FastAPI app.
- The canonical saved artifact is a JSON `PipelineDocument`.
- `/studio` is the teacher creation route and `/textbook/[id]` is generation-centric.

## Current Schema Highlights

- `TeacherBrief` is the planning input contract.
- `PlanningGenerationSpec` is the reviewed planning artifact that gets committed into generation.
- `GenerationAcceptedResponse` includes startup metadata used by `GenerationView`.
- `Generation.planning_spec_json` stores the committed planning artifact for detail/report hydration.
- `SectionContent` remains Lectio-aligned and renders natively in the frontend viewer.

## Current Studio Flow

- `/studio` renders `TeacherBriefBuilder` directly.
- Topic narrowing happens through `POST /api/v1/brief/resolve-topic`.
- Deterministic readiness checks happen through `POST /api/v1/brief/validate`.
- Pedagogical review happens through `POST /api/v1/brief/review`.
- Planning happens through `POST /api/v1/brief/plan`.
- After teacher review, generation starts through `POST /api/v1/brief/commit`.
- `GenerationView` hydrates generation detail/document state and follows live `/events`.

There is no live planning SSE route. `POST /api/v1/brief` and `POST /api/v1/brief/stream` are not current endpoints.

## Prompt and Contract Sources

- Planning prompt entrypoints live in the current planning modules such as `planning/section_composer.py`, `planning/service.py`, and `planning/routes.py`.
- Media prompt builders live under `backend/src/pipeline/media/prompts/`.
- Contract loading lives in `backend/src/pipeline/contracts.py`.
- Synced raw contract JSON lives in `backend/contracts/`; app-facing typed payloads are derived from the current pipeline and planning models.

## Viewer Contract

- The frontend loads generation detail by generation ID.
- `/document` hydrates the current saved `PipelineDocument`.
- `/report` hydrates telemetry/report state.
- `/events` carries authenticated generation SSE, including section progress and media lifecycle events.
- Viewer section states are media-aware: `planned`, `generating`, `partially_ready`, `blocked_by_required_media`, `ready`, `failed`, and `unplanned_output`.

## Media Runtime

- `pipeline.media.planner.media_planner` remains the single planning authority for media execution.
- Static media execution lives under `pipeline.media.executors`.
- Required media retries are frame-first and surfaced through runtime events and report state.
