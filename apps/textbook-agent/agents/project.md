# Project Config

AI-powered shell + pipeline system that generates personalized Lectio-native textbooks from learner profiles.
Monorepo: `backend/` (FastAPI + Python) and `frontend/` (SvelteKit + TypeScript).

## Architecture Rules

The backend uses a `Core + Generation + Planning + Telemetry + Pipeline` architecture:

- `backend/src/core/` holds shared infrastructure: config, auth primitives, database, error handling, event bus, and generic LLM utilities.
- `backend/src/generation/` owns generation HTTP, persistence, and orchestration.
- `backend/src/telemetry/` owns report persistence, telemetry routes, and usage queries; it may depend on `core/` and `pipeline.reporting`, but must not import `generation/` or `planning/`.
- `backend/src/planning/` holds planning-specific models and services that may depend on `core/`, and may hand committed specs to generation, but not on `pipeline/` LLM internals.
- `backend/src/pipeline/` is the standalone generation engine.
- `backend/src/app.py` assembles the FastAPI application.

The shell is flattened into top-level packages:

| Package group | Typical contents |
| --- | --- |
| `entities/`, `value_objects/`, `ports/` | Shell domain model and repository contracts |
| `dtos/`, `services/`, `routes/`, `repositories/` | Shell application and HTTP wiring |
| `middleware/`, `dependencies.py`, `app.py` | Shell composition layer |

Critical invariants:
- `core/` must not import from `generation`, `planning`, `telemetry`, or `pipeline`
- `generation/` may import `core/`, `planning/`, `telemetry/`, and `pipeline/`
- `telemetry/` may import `core/` and `pipeline.reporting`, but must not import `generation/` or `planning/`
- `planning/` may import `core/` and selected `generation/` bridge types, but must not import `pipeline` LLM internals
- `pipeline/` may import `core/`, but must never import `generation`, `planning`, or `telemetry`
- Entities, value objects, and ports stay framework-light and reusable
- All live generation goes through the pipeline engine
- The canonical artifact is a structured JSON document, not HTML

## Validation Commands

See `CLAUDE.md` for the full command reference. Quick alternative:

```bash
python tools/agent/validate_repo.py --scope all       # Runs everything
python tools/agent/check_architecture.py --format text # Shell + pipeline boundary check
```

## Conventions

- **Commits**: `type(scope): summary` -- types: feat, fix, refactor, docs, test, chore, ci, build
- **Branches**: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, `chore/<slug>`
- **Protected branches**: `main`
- **Package managers**: `uv` (backend), `npm` (frontend)

## Key Entities

- `StudentProfile` -- persistent learner data (age, education, interests, goals). Stored in DB.
- `Generation` -- stored generation metadata plus document and failure state.
- `GenerationRequest` -- per-request DTO (`subject`, `context`, `template_id`, `preset_id`, optional `section_count`).
- `PipelineDocument` -- canonical saved output used by the frontend viewer.
