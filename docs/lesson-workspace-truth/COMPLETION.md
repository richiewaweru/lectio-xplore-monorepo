# Truthful Lesson Workspace Correction

## Scope

Implemented the attached truth-pack requirements for the lesson workspace only. The generation pipeline was not rewritten, lifecycle contracts were not weakened, and Learn/Print remain separate paths.

## Delivered

- Added shared Learn/Print artifact normalization with `not_created`, `preparing`, `ready`, `needs_attention`, and `failed` states.
- Artifact existence is derived only from the exact path realization row or explicit path-specific realization identity. Preparation `generation_id` cannot imply Print existence.
- Layout and Plan now keep the approved Teaching Plan visible and expose independent Learn and Print output cards with truthful Create/Open/Issues/Retry actions.
- Learn now defaults to `Preview`, reusing `StudentLessonShell`; Edit preserves Builder identity through document-load failures; Issues is path-specific.
- Print now has normalized Preview/Edit/Issues states, explicit empty/error states, and the existing PDF export flow.
- Added path-neutral `LessonIssuesPanel` with an explicit `No issues detected` state.
- Issues takes precedence over the not-created preview/editor empty state, so both paths can report an empty issue result before an artifact exists.
- Added `GET /api/v1/units/{unit_id}/path/lessons/{lesson_id}/issues?path=learn|print` with ownership enforcement, path filtering, stable IDs, severity mapping, repair metadata, source projection, deterministic deduplication, and counts.
- Issue projection covers realization failures, persisted coherence reports, document/interaction validation, required figures/media, Print booklet issues, and generation errors.
- Create/retry flows refresh status, content, and issues without creating a realization during tab loading.

## Verification evidence

- Frontend focused tests: 7 passed (`lesson-context`, `LessonIssuesPanel`).
- Frontend production build: passed. Existing Svelte warnings remain in unrelated editor components.
- Frontend type-check: existing unrelated errors remain in `src/routes/classes/[classId]/+page.svelte` (`detail` possibly null at lines 82 and 85); five existing warnings remain.
- Backend focused planning/issue tests: 17 passed; one existing Pydantic warning about the `schema` field remains.
- Backend Ruff checks: passed for the changed issue projection, route, and tests.
- Isolated backend on `127.0.0.1:8002`: `/health` returned 200; OpenAPI contains the Issues GET route with `path` enum `learn, print`; unauthenticated Issues access returned 401.
- Live in-app browser on `127.0.0.1:5173`, backed by the current API on `127.0.0.1:8001`:
  - Verified an uncreated lesson: Plan reports `Learn · not created` and `Print · not created`; Learn and Print default to Preview with truthful Create actions; both Issues tabs return `✓ No issues detected`.
  - Verified an existing lesson: Learn defaults to the learner-facing Preview and renders the document; Print renders the booklet preview; both path-specific Issues tabs return `✓ No issues detected`.
  - Verified `Plan → Learn → Print → Plan` navigation with the approved Teaching Plan still visible and independent Learn/Print output cards; the stale Print realization remains truthfully marked `Needs Attention`.
  - Backend access logs for the browser pass contained only GET requests for auth, unit/path/status/document/issues reads; no realization-creation POST was triggered by tab loading.

## Changed implementation files

- `apps/textbook-agent/frontend/src/lib/curriculum/lessons/lesson-context.ts`
- `apps/textbook-agent/frontend/src/lib/curriculum/lessons/LessonIssuesPanel.svelte`
- `apps/textbook-agent/frontend/src/lib/types/units.ts`
- `apps/textbook-agent/frontend/src/lib/api/units.ts`
- `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/+layout.svelte`
- `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/plan/+page.svelte`
- `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/learn/+page.svelte`
- `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/print/+page.svelte`
- `apps/textbook-agent/backend/src/curriculum/lesson_review/issue_projection.py`
- `apps/textbook-agent/backend/src/curriculum/lesson_review/__init__.py`
- `apps/textbook-agent/backend/src/curriculum/routes.py`
