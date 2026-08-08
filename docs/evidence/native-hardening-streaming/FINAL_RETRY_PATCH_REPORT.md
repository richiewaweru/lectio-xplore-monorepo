# Final Native Hardening Patch — Completion Report

Branch: `pageobject-integration`  
Base: `e8d6b76`  
Evidence date: 2026-08-08

## 1. Commit SHA

Filled after commit on `pageobject-integration` (message includes retry-native / error sync).

## 2. Changed files

### Source
- `apps/textbook-agent/backend/src/planning/whole_lesson/states.py` — `item_generation` / `planning_teaching` legal edges; `NATIVE_STATUSES`
- `apps/textbook-agent/backend/src/planning/whole_lesson/repository.py` — GenerationModel error aliases sync/clear; visual alias sync
- `apps/textbook-agent/backend/src/planning/whole_lesson/native_retry.py` — **new** decision + `execute_native_retry`
- `apps/textbook-agent/backend/src/planning/whole_lesson/native_status.py` — precise `next_action`
- `apps/textbook-agent/backend/src/generation/v3_studio/router.py` — `POST .../retry-native`; retry-section delegates

### Tests
- `tests/planning/test_pre_worker_failure_sync.py` — alias sync + `retry_teaching`
- `tests/planning/test_native_retry_pre_worker.py` — **new** R01–R07
- `tests/planning/test_native_only_routing.py` — updated for shared retry path

### Evidence
- `docs/evidence/native-hardening-streaming/FINAL_RETRY_PATCH_REPORT.md` (this file)

## 3. Tests run

Full hardening regression (terminology, item observability/durability, pre-worker sync, native retry, resume, worker failure, streaming mono, parallel sections, fencing, visual dispatch/failure/PDF, native status, streaming events, doc_version, contract hardening, native-only routing):

**105 passed / 0 failed**.

## 4. State-machine changes

```text
failed_recoverable → {queued, item_generation, planning_teaching, cancelled}
item_generation    → {planning_teaching, failed_recoverable, failed_terminal, cancelled}
planning_teaching  → {awaiting_teaching_approval, failed_recoverable, failed_terminal, cancelled}
```

`item_generation` / `planning_teaching` are in `NATIVE_STATUSES` but **not** `CLAIMABLE_STATUSES` / `ACTIVE_STATUSES`.

## 5. Item failure → recovery trace

```text
TimeoutError during items
  → persist_native_failure(stage=item_generation)
  → status=failed_recoverable
  → generation.error/type/code == last_error.message/type/code
  → next_action=retry_items
POST /retry-native
  → claim → item_generation (pre_worker_retry_active)
  → _generate_shared_pack_items (skips ready cards; append-only attempts)
  → planning_teaching
  → teaching planner
  → awaiting_teaching_approval + clear error aliases
```

## 6. Teaching failure → recovery trace

```text
TimeoutError during teaching
  → failed_recoverable + stage=planning_teaching
  → next_action=retry_teaching
POST /retry-native
  → planning_teaching
  → run_and_persist_teaching_plan only
  → awaiting_teaching_approval
  → form planner not invoked
```

## 7. Items not regenerated on teaching retry

R02 patches `execute_items_with_diagnostics` to assert if called; teaching retry path never imports/calls item generation. Ready PackItems remain untouched.

## 8. Duplicate retries cannot double-execute

R04: first retry sets `pre_worker_retry_active` under lock; second request raises `NativeRetryConflict(RETRY_IN_PROGRESS)` / HTTP 409. Teaching planner ran once.

## 9. Generation error aliases match structured error

R01 + extended pre-worker sync assert:

```text
generation.error == last_error.message
generation.error_type == last_error.type
generation.error_code == last_error.code
generation.status == chunked.stage
```

## 10. Successful recovery clears stale error state

R07: after teaching retry success → `generation.error*` NULL, `execution.last_error` NULL, status `awaiting_teaching_approval`.

## 11. Visual-only retry still works

R06: `next_action=retry_visuals`; `/retry-native` → 409 `USE_VISUALS_RETRY`; `/visuals/retry` succeeds without items/teaching/forms/writers.

## 12. Remaining live browser E2E blocker

Docker Desktop / local Postgres + real LLM/visual providers still required for:

```text
UI → Docker Postgres → real LLMs → teacher gates → streaming → visual provider → reload → PDFs
```

No 3–5 real LLM reliability sample was run in this patch.
