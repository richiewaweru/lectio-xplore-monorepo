# Teacher Studio Generation Mode Handoff

**Extends**: `docs/project/runs/2026-04-01-teacher-studio-generation-mode.md`  
**Status**: ready to merge  
**Branch**: `feat/teacher-studio-generation-mode`

---

## What Changed

- Added a generation mode selector to the live Teacher Studio flow in [`IntentForm.svelte`](C:/Projects/Textbook agent/frontend/src/lib/components/studio/IntentForm.svelte).
- Defaulted new Teacher Studio drafts to `balanced` in [`studio.ts`](C:/Projects/Textbook agent/frontend/src/lib/stores/studio.ts).
- Propagated mode through planning models, fallback, and commit flow in [`models.py`](C:/Projects/Textbook agent/backend/src/planning/models.py), [`fallback.py`](C:/Projects/Textbook agent/backend/src/planning/fallback.py), and [`routes.py`](C:/Projects/Textbook agent/backend/src/planning/routes.py).
- Restored pipeline mode handling in [`requests.py`](C:/Projects/Textbook agent/backend/src/pipeline/types/requests.py), [`registry.py`](C:/Projects/Textbook agent/backend/src/pipeline/providers/registry.py), and the node call sites.
- Persisted mode on generations and added the DB migration [`20260401_0007_add_generation_mode.py`](C:/Projects/Textbook agent/backend/src/core/database/migrations/versions/20260401_0007_add_generation_mode.py).
- Updated read models and tests so history/detail/document payloads expose mode consistently.

## What Was Validated

- `frontend`: `npm run check`
- `frontend`: `npm run build`
- `frontend`: focused studio/type/viewer Vitest suite passed
- `backend`: focused pipeline, route, and repository pytest suites passed
- `repo`: `python tools/agent/check_architecture.py --format text`

## What Is Left

- Apply the new generation-mode migration in each deployed environment.
- If we want mode editing after review or during regeneration, that remains future work.

## Where To Start Next Time

1. [`TeacherStudioFlow.svelte`](C:/Projects/Textbook agent/frontend/src/lib/components/studio/TeacherStudioFlow.svelte) and [`IntentForm.svelte`](C:/Projects/Textbook agent/frontend/src/lib/components/studio/IntentForm.svelte) for the live UI flow.
2. [`routes.py`](C:/Projects/Textbook agent/backend/src/planning/routes.py) for the planning-to-generation bridge.
3. [`service.py`](C:/Projects/Textbook agent/backend/src/generation/service.py) for generation creation, planning-spec persistence, and detail/history shaping.
4. [`requests.py`](C:/Projects/Textbook agent/backend/src/pipeline/types/requests.py) and [`registry.py`](C:/Projects/Textbook agent/backend/src/pipeline/providers/registry.py) for mode behavior.
5. [`test_brief.py`](C:/Projects/Textbook agent/backend/tests/routes/test_brief.py), [`test_api.py`](C:/Projects/Textbook agent/backend/tests/routes/test_api.py), and the studio frontend tests for the expected contracts.

## Notes

- The pre-existing local modification in `backend/tests/routes/test_blocks_generate.py` was left untouched and should not be included in this merge.
