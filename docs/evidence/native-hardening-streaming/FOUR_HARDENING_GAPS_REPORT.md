# Four Native Hardening Gaps — Completion Report

Branch: `pageobject-integration`  
Base contracts preserved from `615425b`.  
Evidence date: 2026-08-08

## Verdict

All four gaps closed with deterministic proofs. Required suites: **84 passed / 0 failed**. No real LLM 3–5 sample. Live browser E2E remains blocked (Docker/providers).

## Files changed

### Source
- `apps/textbook-agent/backend/src/planning/whole_lesson/states.py` — pre-worker legal failure transitions
- `apps/textbook-agent/backend/src/planning/whole_lesson/repository.py` — `persist_native_failure`, locked `assemble_and_persist_streaming_snapshot`, `persist_visual_dispatch_failure`, `clear_visual_last_error`
- `apps/textbook-agent/backend/src/planning/whole_lesson/worker.py` — failure path delegates to `persist_native_failure`
- `apps/textbook-agent/backend/src/planning/whole_lesson/executor.py` — locked streaming publish; durable visual dispatch exception path
- `apps/textbook-agent/backend/src/planning/whole_lesson/visual_dispatch.py` — collect `failed_recoverable`; per-figure failure capture; repo redispath records last_error
- `apps/textbook-agent/backend/src/planning/whole_lesson/native_status.py` — `next_action=retry_visuals` + error_detail while `awaiting_visuals`
- `apps/textbook-agent/backend/src/generation/v3_studio/router.py` — native stage2 failure sync; item attempt flush; `POST .../visuals/retry`
- `apps/textbook-agent/backend/src/v3_blueprint/planning/persistence.py` — `append_item_attempt_records`
- `apps/textbook-agent/backend/src/v3_execution/executors/item_diagnostics.py` — `retryable` on attempt records
- `apps/textbook-agent/backend/src/v3_execution/executors/item_executor.py` — pass `retryable` into journals

### Tests added
- `tests/planning/test_pre_worker_failure_sync.py`
- `tests/v3_execution/test_item_attempt_durability.py`
- `tests/planning/test_streaming_monotonic.py`
- `tests/planning/test_visual_dispatch_failure.py`

### Not part of this fix
- Pre-existing migration logging edits (`env.py` / `runner.py`) left untouched for commit decisions.
- `docs/evidence/whole-lesson-runs/` unrelated browser artifacts.

## Verification counts

| Suite set | Result |
|---|---|
| Core hardening batch (fail-sync, item durability/observability, streaming mono/events, visual fail/dispatch, fencing, worker failure, resume, visual PDF, contract hardening, doc_version) | **74 passed** |
| Terminology/legality + parallel sections | **10 passed** |
| **Total required** | **84 passed / 0 failed** |

## Deterministic proofs

### 1. Teaching failure → no status drift
Before: `GenerationModel.status` could remain on an earlier value while chunked only wrote `stage2_error`.  
After (`persist_native_failure`): status, chunked/page stage, `execution.last_error`, failure event, and status API `error_detail` agree on `failed_recoverable`/`failed_terminal`.

Example transition: `awaiting_teaching_approval` / pre-worker teaching raise → atomic `failed_recoverable` (or terminal per classification) with synced stage + last_error.

### 2. Failed item attempts inspectable after stage failure
Append-only flush after each card + `finally` flush. Example persisted record shape:

```json
{
  "correlation_id": "item:<generation_id>:<card_id>",
  "card_id": "card-…",
  "attempt": 1,
  "class": "SEMANTIC",
  "retryable": true,
  "error": "fail-1",
  "latency_ms": 0
}
```

All three exhausted attempts remain in `chunked_state.item_generation.attempts[]` after gather failure.

### 3. Stale partial snapshot cannot replace newer
Newer two-section streaming persist (`orient`,`explain`) then stale one-section assemble → `rejected=non_monotonic_section_set`, revision unchanged, document still contains both sections.

### 4. Visual dispatcher exception visible + retryable
`persist_visual_dispatch_failure` keeps `awaiting_visuals`, sets retryable `execution.last_error` (`stage=awaiting_visuals`), marks figure asset `failed` / outcome `failed_recoverable`, appends `visual_dispatch_failed` event. Status API `next_action=retry_visuals`.

### 5. Ready/visual_pending blocks not recomputed on visual retry
`POST /api/v1/v3/generations/{id}/visuals/retry` only calls `dispatch_and_patch_from_repo`. Ready prose block content/status unchanged; only failed/pending figures redispatched. Does **not** transition via `failed_recoverable → queued`.

### 6. Final SHA/reload fencing still passes
`tests/planning/test_phase02_document_fencing.py` green under the new locked streaming path (streaming still does not set final SHA/reload fence fields).

## Remaining live browser E2E blockers

- Docker Desktop / local DB identity path used by prior Phase 07 browser smoke is unavailable in this environment.
- Live image/provider credentials not exercised; visual redispath proved with mocked `execute_visual` only.
- No 3–5 real LLM whole-lesson sample requested or run.

## Operator notes

- Visuals-only recovery: poll native status for `next_action=retry_visuals`, then `POST .../visuals/retry`.
- Item diagnostics after item-stage failure: inspect `chunked_state.item_generation.attempts` / `failed_cards` (no need to recover only from raised exception journals).
