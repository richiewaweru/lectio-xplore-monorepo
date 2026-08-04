# Architecture

## Strategy

The live system uses a `Core + Generation + Planning + Telemetry + Pipeline` split.

- `backend/src/core/` owns shared auth, config, database, rate limiting, events, and generic LLM wiring.
- `backend/src/planning/` owns Teacher Studio brief validation, review, planning, and the planning-to-generation bridge.
- `backend/src/generation/` owns generation persistence, orchestration, history/detail routes, SSE transport, and PDF export.
- `backend/src/telemetry/` owns saved reports and LLM usage reporting.
- `backend/src/pipeline/` is the standalone lesson-generation engine and remains the only live content generator.
- `frontend/` is the SvelteKit client. `/studio` is the teacher creation entrypoint and `/textbook/[id]` is the generation-centric viewer.

Architecture guard: `python tools/agent/check_architecture.py --format text`

## Boundary Rules

- `core/` must not import from `generation/`, `planning/`, `telemetry/`, or `pipeline/`.
- `generation/` may import `core/`, `planning/`, `telemetry/`, and `pipeline/`.
- `planning/` may import `core/` and selected generation bridge types, but must not depend on pipeline LLM internals.
- `telemetry/` may import `core/` and `pipeline.reporting`, but must not import `generation/` or `planning/`.
- `pipeline/` must never import `generation/`, `planning/`, or `telemetry/`.
- The canonical saved artifact is a structured JSON `PipelineDocument`, not HTML.

## Teacher Studio Flow

`/studio` renders `TeacherBriefBuilder` directly. The live planning path is a JSON round trip, not planning SSE:

1. `POST /api/v1/brief/resolve-topic`
2. `POST /api/v1/brief/validate`
3. `POST /api/v1/brief/review`
4. `POST /api/v1/brief/plan`
5. Teacher reviews the returned `PlanningGenerationSpec`
6. `POST /api/v1/brief/commit`
7. `GenerationView` follows the generation through `/generations/{id}`, `/document`, `/report`, and `/events`

Planning produces a reviewed `PlanningGenerationSpec`. It never generates lesson content itself.

## Runtime Boundaries

- Contract catalog: `GET /api/v1/contracts`
- Planning endpoints: `POST /api/v1/brief/resolve-topic`, `/validate`, `/review`, `/plan`, `/commit`
- Generation detail: `GET /api/v1/generations/{id}`
- Document hydration: `GET /api/v1/generations/{id}/document`
- Report hydration: `GET /api/v1/generations/{id}/report`
- Live stream: authenticated SSE at `GET /api/v1/generations/{id}/events`
- PDF export: `POST /api/v1/generations/{id}/export/pdf`

These legacy endpoints are not live and should stay absent:

- `POST /api/v1/brief`
- `POST /api/v1/brief/stream`
- `POST /api/v1/generations`

## Planning and Contracts

- The route layer in `backend/src/planning/routes.py` is the only place that adapts `PlanningGenerationSpec` into generation inputs.
- The current studio flow assumes `TeacherBrief`-shaped `source_brief` payloads.
- Lectio contracts under `backend/contracts/` are synced artifacts. App-facing typed payloads come from `pipeline.types.template_contract` and the planning models.

## LLM Routing

- Planning uses `backend/src/planning/llm_config.py`.
- Pipeline routing remains slot-based through the shared `core/llm/` layer.
- Media planning and execution stays under `pipeline.media.*`.

## Snapshot Reference

- Historical architecture notes live under `docs/v0.1.0/`.
