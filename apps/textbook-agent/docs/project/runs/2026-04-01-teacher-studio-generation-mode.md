# Teacher Studio Generation Mode Wiring

**Date:** 2026-04-01  
**Classification:** minor  
**Subsystems:** frontend, backend, pipeline, persistence

## Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation
- [x] Self-reviewed against `agents/standards/review.md`
- [ ] Wrote commit message(s) following `agents/standards/communication.md`
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted follow-up work or open questions

## Summary

This change restores generation mode as a real end-to-end setting in the live Teacher Studio flow.

The selected mode now travels through:
- Teacher Studio draft state and form submission
- planning stream and planning commit payloads
- generation creation and persisted generation records
- pipeline request execution and downstream read models

Mode behavior is now explicit:
- `draft`: fastest profile, interactions disabled, rerender budget `1`
- `balanced`: standard profile, rerender budget `2`
- `strict`: highest-quality text profile, rerender budget `3`

## Key Changes

### Frontend

- Added `mode` to the Teacher Studio draft and generation/planning types.
- Defaulted new Teacher Studio drafts to `balanced`.
- Added a visible generation mode selector to the current Teacher Studio intent form.
- Wired mode through `/api/v1/brief/stream` and the review/commit flow.
- Kept the legacy `TeacherStudio.svelte` flow type-compatible by defaulting planning to `balanced` and forwarding reviewed mode on generation submit.

### Backend planning and generation

- Added `mode` to `StudioBriefRequest`, planning specs, legacy brief DTOs, and generation DTOs.
- Ensured planning fallback and planning service echo mode in generated specs.
- Forwarded committed planning mode into `enqueue_generation`.
- Included mode in generation detail/history/document payloads and normalized missing legacy values to `balanced`.

### Pipeline runtime

- Restored `GenerationMode` and `PipelineRequest.mode`.
- Added mode-specific rerender budgets and `interactions_enabled()`.
- Made provider selection mode-aware so draft uses faster defaults and strict upgrades text generation.
- Updated node call sites to resolve models/specs with the active generation mode.
- Disabled interaction generation in draft mode, including sections that would otherwise request `simulation-block`.

### Persistence

- Added `mode` to the SQLAlchemy generation model with a `balanced` server/default value.
- Persisted and hydrated mode in the SQL generation repository.
- Added a migration for the `generations.mode` column.

## Validation Evidence

### Frontend

- `cd frontend && npm run check`
- `cd frontend && npm run build`
- `cd frontend && npm run test -- src/lib/api/brief.test.ts src/lib/api/client.test.ts src/lib/stores/studio.test.ts src/lib/components/studio/IntentForm.test.ts src/lib/components/studio/TeacherStudioFlow.test.ts src/lib/components/studio/GenerationView.test.ts src/lib/components/studio/PlanReview.test.ts src/lib/components/TeacherStudio.test.ts src/lib/generation/viewer-state.test.ts src/lib/studio/template-swap.test.ts`

Result: passed

### Backend

- `cd backend && uv run python -m pytest tests/pipeline/test_partial_rerun.py tests/pipeline/test_providers_registry.py tests/pipeline/test_composition_planner.py -q`
- `cd backend && uv run python -m pytest tests/routes/test_brief.py tests/routes/test_api.py tests/repositories/test_generation_repo.py tests/repositories/test_document_repository.py -q`

Result: passed

### Repo guard

- `python tools/agent/check_architecture.py --format text`

Result: passed

## Risks And Follow-up

- Database rollout still requires applying the new Alembic migration in deployed environments.
- Existing persisted generations without mode are intentionally interpreted as `balanced`; no backfill job was added.
- The workspace already contained an unrelated modification to `backend/tests/routes/test_blocks_generate.py`; that file is intentionally excluded from this change.
