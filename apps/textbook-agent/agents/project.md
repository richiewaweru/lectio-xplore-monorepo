# Project Config

AI-powered Unit → Print + Learn system that generates Lectio-native instructional materials from curriculum units and learner context.
Monorepo app: `backend/` (FastAPI + Python) and `frontend/` (SvelteKit + TypeScript), plus packages `@lectio/page` and `@lectio/learn`.

## Architecture Rules

Canonical lesson creation is the **Unit path** only (see `docs/architecture/CURRENT_SYSTEM.md`):

```text
Unit → Concepts → PathLesson → approved instructional meaning
                         ├→ PRINT → whole_lesson / page objects / @lectio/page → PDF
                         └→ LEARN → component_lectio → Builder → Preview → LearnRelease
                                                   → Runtime / Distribution / Insight
```

### Backend layout (`backend/src/`)

| Package | Role |
| --- | --- |
| `application/` | Thin cross-domain orchestration (`unit_lesson`, `builder_print`) |
| `curriculum/` | Units, path planning, schedules, shapes, shared instructional meaning |
| `print/` | Print generation, rendering, resources, contracts, `http/v3_studio` |
| `learn/` | Authoring, generation, publishing, runtime, analytics, distribution, evidence |
| `infra/` | Auth helpers, DB, LLM, telemetry, health, config |
| `app.py` | Composition root |

Historical shims (`planning/`, `generation/`, `core/`, `learning/`, …) may remain for call-site migration; they are not the canonical API.

Critical invariants:
- `print/` must not import `learn/` product modules (and inverse) except through documented application orchestration
- `curriculum/` owns instructional truth; native domains realize it
- `application/` stays thin: admission, status, cross-domain handoff only
- `infra/` owns DB/provider/auth primitives; not product pedagogy
- The Print canonical artifact is a structured Lectio page document; Learn uses `LessonDocument` / release snapshots

### Frontend layout (`frontend/src/lib/`)

| Owner | Typical contents |
| --- | --- |
| `shared/` | Auth stores, settings, cross-cutting UI |
| `curriculum/` | Units UI |
| `print/` | Studio, print canvas, PDF preview |
| `learn/` | Builder, student shell, distribution, insight |
| `api/` | HTTP clients |

Product routes: `/units`, `/studio*`, `/builder*`, `/learn*`, `/packs*`, `/settings*`, `/login`, `/onboarding`.

## Validation Commands

See `CLAUDE.md` and monorepo root `package.json`. Quick alternatives:

```bash
pnpm page:test / page:check
pnpm app:test / app:check
pnpm program:domain-guards
# Backend (from apps/textbook-agent/backend)
uv run python tools/agent/validate_repo.py --scope backend
uv run python ../tools/agent/check_architecture.py --format text
```

## Conventions

- **Commits**: `type(scope): summary` -- types: feat, fix, refactor, docs, test, chore, ci, build
- **Branches**: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`, `chore/<slug>`
- **Protected branches**: `main`
- **Package managers**: `uv` (backend), `pnpm`/`npm` (frontend/packages)

## Key Entities

- `Unit` / `PathLesson` -- curriculum identity and approved instructional meaning
- `Generation` -- stored generation metadata plus native document/state
- `LessonDocument` / `LearnRelease` -- Learn authoring and immutable release
- Page document v2 -- Print native artifact used for reload and PDF
