# Project Config

AI-powered Unit → Print + Learn system that generates Lectio-native instructional materials from curriculum units and learner context.
Monorepo app: `backend/` (FastAPI + Python) and `frontend/` (SvelteKit + TypeScript), plus packages `@lectio/contracts` and `@lectio/page`. Learn interaction UI lives under `frontend/src/lib/learn/interactions/`.

## Architecture Rules

Canonical lesson creation is the **Unit path** only (see `docs/architecture/CURRENT_SYSTEM.md`):

```text
Unit → Concepts → PathLesson → Teaching Plan (approved instructional meaning)
                              ├→ PRINT → document primitives → Print realizer
                              │          → page objects / @lectio/page → PDF
                              └→ LEARN → document primitives + retained interactions
                                         → LearnDocument v2 → Builder / Runtime
                                         → LearnRelease / Distribution / Insight

Shared ordinary content vocabulary: backend/src/document/
  Paragraph | Heading | List | Figure | Table | Callout
Retained Learn interactions (KEEP):
  choice | multi-select | fill-blank | classify | match-pairs | sequence | numeric | short-response
```

Package ownership:
- `@lectio/contracts` owns shared instructional intents / learner actions
- `@lectio/page` is the Print page-document engine
- Learn ordinary document rendering and interaction shells live under the app (`frontend/src/lib/learn/document/`, `frontend/src/lib/learn/interactions/`). `@lectio/learn` has been removed.

### Backend layout (`backend/src/`)

| Package | Role |
| --- | --- |
| `application/` | Thin cross-domain orchestration (`unit_lesson`, `builder_print`) |
| `curriculum/` | Units, path planning, schedules, shapes, Teaching Plan (shared instructional meaning) |
| `document/` | Neutral ordinary content vocabulary shared by Print and Learn realizers |
| `print/` | Print generation, document realizer, rendering, resources, contracts, `http/v3_studio` |
| `learn/` | Authoring, document generation, interactions, publishing, runtime, analytics, distribution, evidence |
| `infra/` | Auth helpers, DB, LLM, telemetry, health, config |
| `app.py` | Composition root |

Historical shims (`planning/`, `generation/`, `core/`, `learning/`, …) may remain for call-site migration; they are not the canonical API.

Critical invariants:
- `print/` must not import `learn/` product modules (and inverse) except through documented application orchestration
- `curriculum/` owns instructional truth (Teaching Plan); native domains realize it independently on Print|Learn paths
- `document/` owns ordinary content forms only; interactions stay Learn-owned
- `application/` stays thin: admission, status, cross-domain handoff only
- `infra/` owns DB/provider/auth primitives; not product pedagogy
- Print canonical artifact is a structured Lectio page document; Learn uses LearnDocument v2 / release snapshots

### Frontend layout (`frontend/src/lib/`)

| Owner | Typical contents |
| --- | --- |
| `shared/` | Auth stores, settings, cross-cutting UI |
| `curriculum/` | Units UI, explicit Print|Learn path admission |
| `print/` | Studio, print canvas, PDF preview |
| `learn/` | Document canvas/renderers, interactions, builder, student shell, distribution, insight |
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

- `Unit` / `PathLesson` / Teaching Plan -- curriculum identity and approved instructional meaning
- `Generation` -- stored generation metadata plus native document/state
- LearnDocument v2 / `LearnRelease` -- Learn authoring and immutable release
- Page document v2 -- Print native artifact used for reload and PDF
- Document primitives (`document/`) -- ordinary content shared before path realization
