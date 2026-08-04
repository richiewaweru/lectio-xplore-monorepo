# Bugfix: blocked-state resilience

**Classification**: minor
**Root cause**: generic stage-2 exceptions were persisted as `assembly_blocked` without failed section IDs, leaving the teacher without a recovery action and relying on SSE to discover the state.

## Progress

- [x] Reproduced the bug (identified the generic stage-2 exception persistence path)
- [x] Identified root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran validation
- [x] Self-reviewed the diff

## Validation Evidence

- Backend lifecycle tests: `uv run pytest tests/generation/test_v3_chunked_lifecycle.py` — 18 passed.
- Frontend focused tests: `npx vitest run src/lib/components/studio/V3PlanActions.test.ts src/routes/studio/page.test.ts` — 26 passed.
- Frontend suite: `npm run test` — 198 passed.
- Frontend type check: `npm run check` — 0 errors, 0 warnings.
- Frontend production build: `npm run build` — passed.
- Architecture guard: `python tools/agent/check_architecture.py --format text` — no violations.
- Full backend suite: 374 passed, 1 pre-existing unrelated failure in `tests/v3_execution/test_v3_execution_core.py::test_runner_emits_skeleton_ready_before_component_events` (missing `components` key in the generated skeleton assertion).

## Risks

The status contract is additive. SSE events and the planning resume/retry mechanisms remain unchanged.
