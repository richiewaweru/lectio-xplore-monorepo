# CURRENT_ARCHITECTURE — Phase 01 verified facts

**Captured:** 2026-09-06 (updated after Phase 01 PASS)  
**Target:** `C:\Projects\lectio` @ `bd19a9060b637b84f6d86c002cbf01513adf1e4b` (`main`, dirty Phase 01 tree)  
**Supersedes for this program:** stale claims in `docs/implementation-runs/BASELINE_MAP.md` and `apps/textbook-agent/docs/project/ARCHITECTURE.md` that treat Studio/pipeline as the live product surface.

## Product lineages (do not flatten)

```text
Unit / concept / path authoring
        /                    \
   PRINT (monorepo)      LEARN (now co-located in monorepo)
   whole_lesson          component_lectio
   page_objects          Builder LessonDocument
   @lectio/page          workspace packages/lectio (→ @lectio/learn in Phase 02)
   PDF
```

## Repositories

| Role | Path | Branch | SHA | Notes |
|---|---|---|---|---|
| Permanent target | `C:\Projects\lectio` | `main` | `bd19a906…` | Untracked evidence/logs only |
| Live Component Learn | `C:\Projects\Textbook agent` | `xplore` | `d2cf2f27…` | 37 commits after charter `8509233c` |
| Component Lectio source | `C:\Projects\lectio-legacy-20260805` | `xplore` | `f71e78cd…` | `lectio@0.6.0`; dirty `content-zod.ts` |

Monorepo textbook-agent was historically imported from `ba677486`, **not** current `d2cf2f27`. Earlier page-object RUN 00–10 under `docs/implementation-runs/` is a different program.

## Ownership map

### Authoring (shared, Unit path)

- DB: `UnitModel`, `UnitScopeContractModel`, `PathVersionModel`, `PathLessonModel`, `ConceptModel`, …
- Backend: `apps/textbook-agent/backend/src/planning/`
- Frontend: `apps/textbook-agent/frontend/src/routes/units/`
- Both trees use Units; **xplore** is the cutover-complete Learn admission (`control.pipeline=component_lectio`).

### Print

- `planning/whole_lesson/` → `generation/page_objects/` → `packages/lectio-page` (`@lectio/page`)
- Viewer: `LectioPageDocumentView.svelte`
- Fixture PDF: `pnpm --filter @lectio/page pdf:fixture`
- **Present only in monorepo.** Absent on standalone xplore.

### Learn (live — Phase 01 imported)

- `generation/component_lectio/` + `units_dispatch.py` + `canonical.py` + `builder/service.py`
- Output: validated `LessonDocument` → Builder
- **Now present in monorepo** (imported from xplore @ `d2cf2f27`). Standalone xplore remains the historical source of truth SHA.

### Learn (pre-cutover leftover — REMOVE later)

- `generation/v3_studio/`, `v3_execution` assembly → `V3BookletPackView`
- Not the live Units → `component_lectio` path. Do not restore as production Learn.

### Builder / persistence

- Frontend: `frontend/src/lib/builder/` (document store, history undo/redo, IDB, sync queue)
- Backend: `/api/v1/builder/lessons` + `builder/service.py` (Component Lectio → Builder materialization)
- Source types: `manual|component_lectio|template`

### Component library

- Workspace package `packages/lectio` (`lectio@0.6.0`, `workspace:*`)
- Source imported from `lectio-legacy-20260805`
- Next: Phase 02 rename/evolve to `@lectio/learn` + remove print-only exports

### Not present yet (later phases)

- `LearnRelease`, `LearningInstance`, classes, assignments, attempt/evidence runtime, teacher insight

## Dependency direction (program invariant)

```text
instructional core
   /        \
Print      Learn
             ↓
        Distribution
             ↓
          Runtime
             ↓
          Evidence
```

Forbidden: Print ↔ Learn package imports. App frontend is the composition root.

## Docker / Postgres

Healthy container `textbookagent-db-1` (`postgres:16-alpine`) on host `5432`. Compose: `apps/textbook-agent/docker-compose.yml`.

## Visual language

Extend Fraunces / Inter / IBM Plex Mono and `--paper|--surface|--rule|--ink|--accent|--amber` from app layout + `lectio/theme.css`. Do not invent a parallel design system.
