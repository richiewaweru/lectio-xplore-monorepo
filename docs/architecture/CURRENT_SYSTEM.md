# Current System Architecture

Canonical lesson creation is the **Unit path** only:

```text
Unit → Concepts → PathLesson → Teaching Plan (approved instructional meaning)
                              ├→ PRINT → document primitives → Print realizer
                              │          → page objects / @lectio/page → PDF
                              └→ LEARN → document primitives + retained interactions
                                         → LearnDocument v2 → Builder / Runtime
                                         → LearnRelease / Distribution / Insight
```

Shared ordinary content lives in `apps/textbook-agent/backend/src/document/`
(`Paragraph`, `Heading`, `List`, `Figure`, `Table`, `Callout`). Print and Learn
each realize an approved Teaching Plan independently; they do not consume each
other's final artifact.

## Backend layout (`apps/textbook-agent/backend/src/`)

| Package | Role |
|---|---|
| `application/` | Thin cross-domain orchestration (`unit_lesson`, `builder_print`) |
| `curriculum/` | Units, path planning, schedules, shapes, Teaching Plan |
| `document/` | Neutral ordinary content vocabulary for both paths |
| `print/` | Print generation, document realizer, rendering, resources, contracts, `http/v3_studio` |
| `learn/` | `authoring`, document `generation`, `interactions`, `publishing`, `runtime`, `analytics`, `distribution`, `evidence`, `resources`, `contracts` |
| `infra/` | Auth helpers, DB, LLM, telemetry, health, config (name avoids stdlib `platform`) |
| `app.py` | Composition root |

Historical shims (`planning/`, `generation/`, `core/`, `learning/`, …) may still exist for call-site migration; they are not the canonical API. The ordinary `component_lectio` production path has been removed.

## Frontend (`apps/textbook-agent/frontend`)

Product routes: `/units`, `/studio*`, `/builder*`, `/learn*`, `/packs*`, `/settings*`, `/login`, `/onboarding`.

`src/lib/` ownership: `shared/`, `curriculum/`, `print/`, `learn/{document,interactions,authoring,student,distribution,insight}`.

## Packages

- `@lectio/contracts` — `packages/lectio-contracts` (shared instructional intents / learner actions)
- `@lectio/page` — `packages/lectio-page` (Print page-document engine)
- `@lectio/learn` — `packages/lectio-learn` (retained interaction UI only; ordinary document path is app-owned)

## Program state

Document overhaul: `docs/document-overhaul/`. Cleanup program: `docs/cleanup-program/`. Prior domain refactor: `docs/refactor-program/`.
