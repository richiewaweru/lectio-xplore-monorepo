# Teacher Studio Guide

This guide describes the current live `/studio` flow. It replaces the old `IntentForm` / `PlanStream` / SSE-planning walkthrough.

## Current Entry Points

- [frontend/src/routes/studio/+page.svelte](/C:/Projects/Textbook%20agent/frontend/src/routes/studio/+page.svelte) renders `TeacherBriefBuilder` directly.
- [frontend/src/lib/components/brief/TeacherBriefBuilder.svelte](/C:/Projects/Textbook%20agent/frontend/src/lib/components/brief/TeacherBriefBuilder.svelte) owns the teacher flow.
- [frontend/src/lib/components/studio/GenerationView.svelte](/C:/Projects/Textbook%20agent/frontend/src/lib/components/studio/GenerationView.svelte) owns in-studio generation progress.

## Live Flow

1. The teacher enters a topic, grade level, subtopics, class profile, outcome, resource type, supports, and depth in `TeacherBriefBuilder`.
2. The frontend calls `POST /api/v1/brief/resolve-topic` to tighten the topic and propose subtopics.
3. The frontend calls `POST /api/v1/brief/validate` for deterministic readiness checks.
4. If the brief is ready, the frontend calls `POST /api/v1/brief/review` for pedagogical warnings plus deterministic feasibility.
5. The frontend calls `POST /api/v1/brief/plan` and receives a full `PlanningGenerationSpec` as JSON.
6. The teacher reviews that plan in the plan-review step and commits it through `POST /api/v1/brief/commit`.
7. The returned `GenerationAcceptedResponse` is passed into `GenerationView`, which immediately shows startup metadata and then hydrates live generation state from `/generations/{id}`, `/document`, `/report`, and `/events`.

## Backend Ownership

- [backend/src/planning/routes.py](/C:/Projects/Textbook%20agent/backend/src/planning/routes.py) owns the public planning endpoints:
  - `POST /api/v1/brief/resolve-topic`
  - `POST /api/v1/brief/validate`
  - `POST /api/v1/brief/review`
  - `POST /api/v1/brief/plan`
  - `POST /api/v1/brief/commit`
  - `GET /api/v1/contracts`
- [backend/src/planning/service.py](/C:/Projects/Textbook%20agent/backend/src/planning/service.py) produces `PlanningGenerationSpec`.
- [backend/src/generation/service.py](/C:/Projects/Textbook%20agent/backend/src/generation/service.py) persists the generation, stores the committed planning spec, and launches the pipeline job.

## Frontend Ownership

- `TeacherBriefBuilder` manages the staged brief-building UI.
- `PlanReviewStep` is the teacher approval screen for the returned `PlanningGenerationSpec`.
- `GenerationView` is generation-centric. It does not wait for planning events. It uses the accepted response metadata for the pre-SSE loading state, then follows runtime updates.
- `frontend/src/lib/stores/studio.ts` is now generation-focused shared state, not a legacy planning state machine.

## Current Contracts

- Planning input is `TeacherBrief`.
- Planning output is `PlanningGenerationSpec`.
- Commit response is `GenerationAcceptedResponse`, including:
  - `section_count`
  - `sections_with_visuals`
  - `subtopics_covered`
  - optional `warning`

## Endpoints That Are No Longer Live

These should not be used in new code or docs:

- `POST /api/v1/brief`
- `POST /api/v1/brief/stream`
- `POST /api/v1/generations`

## Notes for Future Changes

- Keep the planning-to-generation bridge in `planning/routes.py` authoritative for `PlanningGenerationSpec -> generation` adaptation.
- Treat `source_brief` inside committed planning specs as the current `TeacherBrief` shape.
- If you need a quick end-to-end cutover check, use [backend/scripts/phase5_smoke.py](/C:/Projects/Textbook%20agent/backend/scripts/phase5_smoke.py).
