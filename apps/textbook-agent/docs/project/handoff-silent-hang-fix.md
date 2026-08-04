# Handoff: Fix Silent Hangs on Internal Pipeline Failures

**Branch:** `claude/epic-merkle`
**Commit:** `d80e97b` — `fix(generation): prevent silent hangs on internal pipeline failures`
**Date:** 2026-03-23
**Tests:** 112 passed, 0 failed

---

## Problem

A 2-page generation hung for 30+ minutes. The UI showed "Sections ready: 1/2, Stream: connected" indefinitely. Investigation revealed:

1. `content_generator` (s-02) failed LLM output validation → soft `PipelineError(recoverable=True)`
2. `section_assembler` (s-02) had no content → `PipelineError(recoverable=False)`
3. `qc_agent` (s-02) logged `node_started` but **never logged `node_finished`**
4. The `GenerationReportRecorder` consumer task crashed during event processing
5. `wait_for_idle()` → `asyncio.Queue.join()` blocked forever (dead consumer, unconsumed items)
6. `CompleteEvent` was published *after* `wait_for_idle()`, so it was never reached
7. SSE subscriber waited indefinitely; report stuck at `status="running"` with leftover `.tmp` file

**Root cause:** No crash isolation in the recorder consumer, no timeout on `wait_for_idle()`, no safety net for orphaned generations, and terminal events published too late.

---

## What Changed

### 1. Crash-resilient recorder consumer (`generation_report_recorder.py`)

- `_consume_events()` now wraps each `apply_event()` call in try/except — one bad event no longer kills the loop
- `wait_for_idle()` detects a dead consumer task, drains the queue, and has a 30-second timeout
- New `_drain_dead_queue()` helper marks all pending items as done so `join()` unblocks

### 2. Generation job lifecycle hardening (`generation.py`)

- **5-minute timeout** wrapping `run_pipeline_streaming()` via `asyncio.wait_for()`
- **Reordered terminal events:** `CompleteEvent`/`ErrorEvent` published *before* `wait_for_idle()`, so SSE subscribers get the signal promptly
- **Reordered finalization:** `recorder.finalize_success()`/`finalize_failure()` called *before* `wait_for_idle()`, so the persisted report reflects the final state immediately
- **`finally` safety net:** If status is still `pending`/`running` after all handlers, forces `status="failed"` with `error_code="orphaned_generation"`, publishes `ErrorEvent`, and cleans up `.tmp` files

### 3. SSE race condition fix (`generation.py`)

- Changed from check-then-subscribe to **subscribe-then-check** pattern
- Subscribe to event bus first, then re-read DB status — if already terminal, yield synthetic event and return
- Eliminates the window where a terminal event fires between the DB check and the subscription

### 4. Content-missing short-circuit (`section_runner.py`)

- After `content_generator`, checks if the section actually produced content
- If not, `break` — skips diagram, interaction, assembler, and QC nodes
- Prevents cascade errors and wasted LLM calls on doomed sections

### 5. `.tmp` file cleanup (`file_generation_report_repo.py` + port)

- New `cleanup_tmp(generation_id)` method removes leftover `.tmp` files from interrupted atomic writes
- Called from the `finally` block in `_run_generation_job`
- Abstract port has a default no-op so existing implementations don't break

---

## Files Modified

| File | What changed |
|------|-------------|
| `backend/src/generation/report_recorder.py` | Crash-resilient consumer, timeout + drain for `wait_for_idle()` |
| `backend/src/generation/routes.py` | Job timeout, event reordering, `finally` safety net, SSE race fix |
| `backend/src/pipeline/nodes/section_runner.py` | Short-circuit when content_generator produces nothing |
| `backend/src/generation/repositories/file_generation_report_repo.py` | `cleanup_tmp()` implementation |
| `backend/src/generation/ports/generation_report_repository.py` | `cleanup_tmp()` abstract method (default no-op) |
| `backend/tests/application/test_generation_report_recorder.py` | Added `cleanup_tmp` to in-memory repo |
| `backend/tests/interface/test_api.py` | Added `cleanup_tmp` to in-memory repo |
| `backend/tests/interface/test_generation_provider_failures.py` | Added `cleanup_tmp` to in-memory repo |
| `backend/tests/interface/test_generation_tracing.py` | Added `cleanup_tmp` to in-memory repo |

---

## Verification Steps

1. **Tests:** `cd backend && uv run pytest` — 112 passed
2. **Restart server** — the stale `c65add44` generation should be swept by the existing startup recovery (`_mark_stale_generations_failed`)
3. **New generation** — should complete or fail cleanly within 5 minutes; frontend should show correct final state
4. **Timeout test** (optional) — temporarily set `_GENERATION_JOB_TIMEOUT_SECONDS = 5`, trigger a generation, confirm it fails with "timed out" error within seconds

---

## Design Decisions

- **Policy:** LLM failures are *quality* failures (retry/degrade). Internal logic failures are *structural* failures (catch, mark failed, clean up). The cost of a clean failure is small; the cost of a silent hang is large.
- **Event ordering:** Terminal SSE events are published before recorder finalization. This means the UI unblocks immediately even if recorder persistence is slow or fails.
- **Timeout value:** 300s (5 minutes) is generous for a 2–8 section generation. Can be tuned via `_GENERATION_JOB_TIMEOUT_SECONDS`.
- **Safety net is last-resort:** The `finally` block only fires if all normal success/failure paths were skipped. It logs at ERROR level so these are visible for investigation.

---

## Known Limitations

- The architecture validation tools (`validate_repo.py`, `check_architecture.py`) couldn't run in the worktree due to a missing `jinja2` dependency — this is an environment issue, not a code issue.
- The short-circuit in `section_runner.py` logs a warning but doesn't emit a dedicated pipeline event for the skip. A future enhancement could emit a `SectionSkippedEvent` for richer diagnostics.
