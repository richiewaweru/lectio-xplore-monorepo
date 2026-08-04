# Generation Recovery + Stream Stabilization Handoff

**Runbook**: `docs/project/runs/generation-recovery-stream-stabilization.md`  
**Status**: validated  
**Scope**: backend recovery/rate-limit stabilization plus frontend SSE lifecycle fixes

## What Was Fixed

- Shared LLM calls now have a `120s` ceiling, `3` retry attempts, better `429` backoff, and a draft-only concurrency cap.
- Interrupted generations are no longer left as orphaned `running` rows; they now persist as terminal failures with `error_code="stale_generation"`.
- Startup recovery now reconciles stale `pending`/`running` generations across the DB row, saved document, and saved report.
- Draft mode now allows one targeted retry for a single blocking issue but does not escalate into repeated full rerenders.
- `quality_passed` now requires full QC coverage across planned sections.
- The textbook page now closes terminal streams once, refreshes once, and shows `completed with QC issues` instead of `Stream: reconnecting`.

## Validation

- Targeted backend retry/pipeline/API suites passed
- Recorder and tracing suites passed
- Frontend regression tests for error messaging and textbook page stream lifecycle passed
- Architecture check passed
- Full repo validation passed

Validation note:
- Repo-root validation in this workspace still requires `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts`

## Git / Worktree State

- Main branch: `fix/pipeline-inline-qc-stabilization`
- Claude worktrees still exist and are **not safe to delete yet**:
  - `.claude/worktrees/hopeful-johnson` has uncommitted `llm_runner.py` and `app.py` edits
  - `.claude/worktrees/gallant-banzai` has uncommitted pipeline speed/retry edits

## Pickup Path

If follow-up debugging is needed, start with:
1. `backend/src/pipeline/llm_runner.py`
2. `backend/src/textbook_agent/interface/api/routes/generation.py`
3. `backend/src/textbook_agent/interface/api/generation_recovery.py`
4. `frontend/src/routes/textbook/[id]/+page.svelte`
5. `backend/tests/interface/test_api.py`
6. `frontend/src/routes/textbook/[id]/page.test.ts`
