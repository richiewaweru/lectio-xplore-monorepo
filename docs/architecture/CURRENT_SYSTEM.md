# Current System Architecture

Canonical lesson creation is the **Unit path** only:

```text
Unit → Concepts → PathLesson → approved instructional meaning
                         ├→ PRINT → whole_lesson / page objects / @lectio/page → PDF
                         └→ LEARN → component_lectio → Builder → Preview → LearnRelease
                                                   → Runtime / Distribution / Insight
```

## Backend layout (`apps/textbook-agent/backend/src/`)

| Package | Role |
|---|---|
| `application/` | Thin cross-domain orchestration (`unit_lesson`, `builder_print`) |
| `curriculum/` | Units, path planning, schedules, shapes |
| `print/` | Print generation, rendering, resources, contracts, `http/v3_studio` |
| `learn/` | `authoring`, `generation`, `publishing`, `runtime`, `analytics`, `distribution`, `evidence`, `resources`, `contracts` |
| `infra/` | Auth helpers, DB, LLM, telemetry, health, config (name avoids stdlib `platform`) |
| `app.py` | Composition root |

Historical shims (`planning/`, `generation/`, `core/`, `learning/`, …) may still exist for call-site migration; they are not the canonical API.

## Frontend (`apps/textbook-agent/frontend`)

Product routes: `/units`, `/studio*`, `/builder*`, `/learn*`, `/packs*`, `/settings*`, `/login`, `/onboarding`.

`src/lib/` ownership: `shared/`, `curriculum/`, `print/`, `learn/{authoring,student,distribution,insight}`.

## Packages

- `@lectio/page` — `packages/lectio-page` (print document engine)
- `@lectio/learn` — `packages/lectio-learn` (interactive Learn components)

## Program state

Cleanup program: `docs/cleanup-program/`. Prior domain refactor: `docs/refactor-program/`.
