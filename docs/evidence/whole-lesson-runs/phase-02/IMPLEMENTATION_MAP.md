# Phase 02 Implementation Map

**Branch:** `pageobject-integration`  
**Baseline:** `00cc3c7`  
**Date:** 2026-08-05

## Approval

| Piece | Location |
|---|---|
| HTTP route | `apps/textbook-agent/backend/src/generation/v3_studio/router.py` — `post_lesson_approach_approve` |
| Orchestrator (pre-Phase-02) | `apps/textbook-agent/backend/src/planning/whole_lesson/service.py` — `approve_teaching_and_execute` |
| Frontend client | `apps/textbook-agent/frontend/src/lib/api/v3.ts` — `approveLessonApproach` |
| Studio UI | `apps/textbook-agent/frontend/src/routes/studio/+page.svelte` |

## Executor / writers

| Piece | Location |
|---|---|
| Back half | `apps/textbook-agent/backend/src/planning/whole_lesson/executor.py` — `execute_after_teaching_approval`, `write_form_blocks` |
| Form planner | `apps/textbook-agent/backend/src/planning/whole_lesson/form_agent.py` — `run_form_planner` |
| Writer dispatch | `apps/textbook-agent/backend/src/generation/page_objects/__init__.py` — `dispatch_writer_async` |
| Assembly | `apps/textbook-agent/backend/src/generation/page_objects/document_assembly.py` |

## Repository / state

| Piece | Location |
|---|---|
| Page document repo | `apps/textbook-agent/backend/src/planning/whole_lesson/repository.py` — `PageDocumentRepository` |
| Chunked persistence | `apps/textbook-agent/backend/src/v3_blueprint/planning/persistence.py` |
| Generation model | `apps/textbook-agent/backend/src/core/database/models.py` — `GenerationModel` |

## Startup

| Piece | Location |
|---|---|
| Lifespan | `apps/textbook-agent/backend/src/app.py` — `lifespan` |
| Stale sweep (legacy) | `V3GenerationWriter.fail_stale_running` |

## Document / PDF / visuals

| Piece | Location |
|---|---|
| Document GET | `apps/textbook-agent/backend/src/generation/v3_studio/router.py` — generation document routes |
| PDF export | `POST /api/v1/v3/generations/{id}/export/pdf` → `generation/pdf_export/service.py` |
| Figure helper (unwired) | `apps/textbook-agent/backend/src/generation/page_objects/visual_completion.py` — `apply_figure_asset_update` |
| Stable figure ID | `apps/textbook-agent/backend/src/planning/whole_lesson/figure_ids.py` |

## Phase 02 targets (new)

| Piece | Target location |
|---|---|
| Transitions / lease | `planning/whole_lesson/states.py`, `repository.py` |
| Worker loop | `planning/whole_lesson/worker.py` (started from `app.py` lifespan) |
| Queue approval | `planning/whole_lesson/service.py` `approve_teaching_and_queue` + router HTTP 202 |
| Resilient executor | `planning/whole_lesson/executor.py` |
| Failure injection | `planning/whole_lesson/failure_injection.py` |
| Visual callback route | `POST .../generations/{id}/visuals/callback` in `generation/v3_studio/router.py` |
| Legacy shutdown | stage2 pipeline returns error instead of `resume_stage2` for new lessons |
| Four-run driver | `backend/tools/phase02_four_runs_driver.py` |
| Evidence | `docs/evidence/whole-lesson-runs/phase-02/` |
