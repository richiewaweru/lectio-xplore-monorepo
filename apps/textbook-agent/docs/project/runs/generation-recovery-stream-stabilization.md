## Bugfix: Generation Recovery, Stream Lifecycle, and Rate-Limit Stabilization

**Classification**: major  
**Scope**: backend recovery and retry behavior, frontend generation stream lifecycle, regression coverage  
**Root cause**:
- The generation viewer kept reopening and closing its SSE connection in a way that could retrigger page loading and leave completed generations showing `Stream: reconnecting`.
- Interrupted jobs were not persisted as terminal failures because `asyncio.CancelledError` bypassed the existing `except Exception` path, leaving orphaned `running` generations with no readable terminal event.
- Startup recovery only existed as an idea in Claude’s side worktree and had not been integrated into the main branch.
- Shared LLM retries were still too aggressive for the observed provider `429` pattern, and draft fan-out could stampede the provider with too many concurrent calls.
- Draft retry semantics and `quality_passed` semantics no longer matched the intended inline-QC flow.

### Progress
- [x] Confirmed the stuck-generation symptoms against the latest logs and reports
- [x] Compared Claude’s side-worktree recovery edits against the current branch and folded in the good parts
- [x] Implemented backend timeout, retry, cancellation, stale-generation, and draft retry updates
- [x] Implemented the frontend stream lifecycle fix and terminal QC-failed state
- [x] Added regression coverage for timeout/backoff, stale recovery, cancellation, draft retry routing, quality coverage, and page stream behavior
- [x] Ran targeted validation and full repo validation
- [x] Self-reviewed the diff and recorded git/worktree follow-up notes

### Validation Evidence

| Command | Result |
| --- | --- |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts uv run --project backend pytest backend/tests/pipeline/test_llm_runner.py backend/tests/pipeline/test_pipeline_integration.py backend/tests/interface/test_api.py` | Passed (`65 passed`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts uv run --project backend pytest backend/tests/application/test_generation_report_recorder.py backend/tests/interface/test_generation_tracing.py` | Passed (`6 passed`) |
| `npm test -- src/lib/generation/error-messages.test.ts src/routes/textbook/[id]/page.test.ts` | Passed (`6 passed`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts python tools/agent/check_architecture.py --format text` | Passed (`No architecture violations found.`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts python tools/agent/validate_repo.py --scope all` | Passed |

## Summary

This pass stabilizes the generation experience in three places at once:
- backend jobs now fail cleanly when interrupted or discovered stale at startup
- draft-mode LLM usage is more conservative under rate limiting
- the textbook page no longer mistakes a finished generation for a reconnecting stream

The result is a tighter end-to-end story for the incident the user described: later draft sections should stop stampeding the provider as hard, stale `running` rows no longer survive restarts or cancellations, and completed-but-QC-failed runs now show a terminal UI state instead of polling forever.

## What Changed

| Area | Outcome | Primary files |
| --- | --- | --- |
| Shared LLM runner | Added a generic `120s` call timeout, raised retry attempts to `3`, switched `429` handling to header-aware exponential backoff with jitter, and added a draft-only semaphore cap for FAST/STANDARD slots. | `backend/src/pipeline/llm_runner.py` |
| Draft retry semantics | Draft now allows one targeted retry but refuses to escalate multi-blocking failures into full rerenders. | `backend/src/pipeline/types/requests.py`, `backend/src/pipeline/routers/qc_router.py` |
| Quality semantics | `quality_passed` now requires full planned-section QC coverage instead of treating partial report coverage as success. Failed report finalization also stamps `quality_passed=False`. | `backend/src/pipeline/run.py`, `backend/src/textbook_agent/application/services/generation_report_recorder.py` |
| Interrupted job handling | `_run_generation_job` now catches `asyncio.CancelledError`, persists a failed document/report/generation row, emits a terminal error event, and clears node attempts. | `backend/src/textbook_agent/interface/api/routes/generation.py` |
| Startup stale recovery | Added a dedicated recovery helper and invoked it from FastAPI lifespan so `pending`/`running` generations become terminal `failed` rows on restart, with document/report snapshots updated in sync. | `backend/src/textbook_agent/interface/api/generation_recovery.py`, `backend/src/textbook_agent/interface/api/app.py` |
| Frontend stream lifecycle | Reworked the textbook page so `EventSource` is not tracked as reactive state, terminal stream events refresh exactly once, and completed QC-failed generations show a terminal label instead of `reconnecting`. | `frontend/src/routes/textbook/[id]/+page.svelte` |
| User-facing error copy | Added a specific `stale_generation` message so interrupted runs have readable UI output. | `frontend/src/lib/generation/error-messages.ts` |
| Regression coverage | Added tests for timeout handling, 429 backoff, draft concurrency caps, cancellation, stale recovery, draft retry routing, quality coverage, stale error messaging, and page stream lifecycle. | `backend/tests/pipeline/test_llm_runner.py`, `backend/tests/pipeline/test_pipeline_integration.py`, `backend/tests/interface/test_api.py`, `frontend/src/lib/generation/error-messages.test.ts`, `frontend/src/routes/textbook/[id]/page.test.ts` |

## Public Contract Changes

No new endpoint and no new public generation status enum were introduced.

Semantic changes in existing payloads:
- `error_code="stale_generation"` can now appear on failed generations
- `quality_passed=true` now requires full planned-section QC coverage
- draft mode now permits one targeted retry for a single blocking issue

## Key Implementation Notes

1. Claude’s side-worktree ideas were kept, but hardened:
   - the generic call timeout and startup stale-generation sweep made sense
   - the raw `1s/2s` 429 sleeps were not enough for the observed provider behavior
   - DB-only stale cleanup was not enough because document/report files would still lie

2. `CancelledError` needed its own path:
   - in Python 3.11 it does not inherit from `Exception`
   - without an explicit branch, interrupted jobs stay persisted as `running`

3. The page loop came from lifecycle coupling:
   - the stream object did not need to be reactive
   - separating terminal close/refresh behavior from general load behavior stops the request storm pattern

4. Full validation still needs the contracts directory set from repo root:
   - `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts`

## Git / Worktree Notes

- The current branch is `fix/pipeline-inline-qc-stabilization`.
- The main worktree now contains the full recovery + stream stabilization implementation and validation.
- Two Claude worktrees still exist:
  - `.claude/worktrees/hopeful-johnson`
  - `.claude/worktrees/gallant-banzai`
- Both Claude worktrees still contain uncommitted changes, so they should not be removed blindly.

## Remaining Risks / Deferred Work

| Area | Follow-up |
| --- | --- |
| Multi-process deployment | Startup stale recovery is acceptable for the current local/dev model. If the service later runs multiple workers, stale detection should move to a lease/heartbeat approach. |
| Rate-limit tuning | The new draft cap and backoff should reduce the current storm, but the right production defaults may still need tuning from fresh traces once more generations are run. |
| True cancel UX | This pass handles interruption cleanup, not a full user-facing cancel endpoint or explicit cancel status. |

## Start Here Next Time

1. `backend/src/pipeline/llm_runner.py`
2. `backend/src/textbook_agent/interface/api/generation_recovery.py`
3. `backend/src/textbook_agent/interface/api/routes/generation.py`
4. `frontend/src/routes/textbook/[id]/+page.svelte`
5. `backend/tests/interface/test_api.py`
6. `frontend/src/routes/textbook/[id]/page.test.ts`
