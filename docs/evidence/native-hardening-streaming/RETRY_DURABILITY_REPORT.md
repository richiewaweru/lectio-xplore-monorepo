# Native Retry Durability Patch — Completion Report

Branch: `pageobject-integration`  
Base: `ab79633` (+ evidence `2b1f7df`)  
Evidence date: 2026-08-08

## 1. Commit SHA

`2f33bf26be1e9b7d926a9d3a3063596075629959`

## 2. Files changed

### Source
- `apps/textbook-agent/backend/src/planning/whole_lesson/states.py` — `PRE_WORKER_RETRY_STATUSES`, `work_kind` constants
- `apps/textbook-agent/backend/src/planning/whole_lesson/repository.py` — `work_kind` on execution meta; `claim_pre_worker_retry`; claim-next polls pre-worker first (id-only queries); lease-fenced `save_teaching_plan`; clear `work_kind` on failure/recovery
- `apps/textbook-agent/backend/src/planning/whole_lesson/native_retry.py` — `accept_native_retry` (HTTP) vs `run_pre_worker_retry` (worker); item→teaching checkpoint under lease
- `apps/textbook-agent/backend/src/planning/whole_lesson/worker.py` — dispatch on `work_kind` without forcing `planning_forms`
- `apps/textbook-agent/backend/src/planning/whole_lesson/service.py` — optional lease args on teaching persist
- `apps/textbook-agent/backend/src/v3_blueprint/planning/persistence.py` — `merge_item_generation_summary` / `merge_failed_card_records` (append-only)
- `apps/textbook-agent/backend/src/generation/v3_studio/router.py` — `POST .../retry-native` → **202** accept-only; chunked retry-section uses accept

### Tests
- `tests/planning/test_native_retry_pre_worker.py` — R01–R07 updated for 202 + worker completion
- `tests/planning/test_native_retry_durability.py` — **new** D01–D07, H01–H03, I01–I02
- `tests/planning/test_native_only_routing.py` — patches `accept_native_retry`

### Evidence
- `docs/evidence/native-hardening-streaming/RETRY_DURABILITY_REPORT.md` (this file)
- `docs/evidence/native-hardening-streaming/retry-durability-pytest.txt`

## 3. Exact pytest commands

```text
cd apps/textbook-agent/backend
.\.venv\Scripts\python.exe -m pytest tests/planning/test_native_retry_pre_worker.py tests/planning/test_native_retry_durability.py -q --tb=short

.\.venv\Scripts\python.exe -m pytest ^
  tests/planning/test_phase01_terminology_legality.py ^
  tests/v3_execution/test_phase02_item_observability.py ^
  tests/v3_execution/test_item_attempt_durability.py ^
  tests/planning/test_pre_worker_failure_sync.py ^
  tests/planning/test_native_retry_pre_worker.py ^
  tests/planning/test_native_retry_durability.py ^
  tests/planning/test_phase02_resume_and_assembly.py ^
  tests/planning/test_phase02_worker_failure_policy.py ^
  tests/planning/test_streaming_monotonic.py ^
  tests/planning/test_parallel_section_execution.py ^
  tests/planning/test_phase02_document_fencing.py ^
  tests/planning/test_phase05_visual_dispatch.py ^
  tests/planning/test_visual_dispatch_failure.py ^
  tests/planning/test_phase02_visual_pdf_routes.py ^
  tests/planning/test_native_status_payload.py ^
  tests/planning/test_native_only_routing.py ^
  tests/planning/test_phase04_streaming_events.py ^
  tests/planning/test_phase06_doc_version.py ^
  tests/planning/test_contract_hardening.py ^
  tests/planning/test_section_resume.py ^
  -q --tb=line
```

## 4. Pass / fail counts

| Suite | Result |
|---|---|
| R01–R07 + D/H/I durability | **20 passed / 0 failed** |
| Full hardening regression (incl. durability) | **119 passed / 0 failed** |

Prior hardening baseline was 105; this patch adds durability + R05 coverage → 119.

## 5. D01–D07 results

| ID | Result | Proof |
|---|---|---|
| D01 | PASS | HTTP 202 while teaching blocked; status stays `planning_teaching` until worker release → `awaiting_teaching_approval` |
| D02 | PASS | Accept then drop client; worker alone completes |
| D03 | PASS | Worker-1 claim; age heartbeat (no cleanup); worker-2 reclaim `lease_token > N`; old token `LeaseLostError` |
| D04 | PASS | Items under lease → `planning_teaching` + teaching `work_kind`; abandon; reclaim → teaching only; item call count == 1 |
| D05 | PASS | Concurrent claim → exactly one winner; one teaching call |
| D06 | PASS | Stale worker `run_pre_worker_retry` → `LeaseLostError` |
| D07 | PASS | Seed abandoned `planning_teaching` + `work_kind` (no HTTP); poller discovers and completes |

Restart proofs age `heartbeat_at` into the past and start a new worker identity **without** release/cleanup paths.

## 6. H01–H03 results

| ID | Result |
|---|---|
| H01 | PASS — success summary cannot wipe historical `failed_cards` |
| H02 | PASS — dedupe by `(card_id, correlation_id)` |
| H03 | PASS — multi-correlation failures retained |

## 7. HTTP 202 response example

```json
{
  "generation_id": "<uuid>",
  "status": "planning_teaching",
  "retry_target": "planning_teaching",
  "next_action": "wait",
  "accepted": true,
  "work_kind": "pre_worker_teaching_retry"
}
```

Item path uses `status=item_generation`, `work_kind=pre_worker_item_retry`. Post-approval accept returns `status=queued` with `work_kind=post_approval_execution`.

## 8. Persisted state before retry

```text
GenerationModel.status = failed_recoverable
execution.last_error.stage = planning_teaching | item_generation
execution.work_kind = null
execution.worker_id = null
generation.error* synced to last_error
```

## 9. Persisted claimed state (after accept + claim)

```text
status = item_generation | planning_teaching
execution.work_kind = pre_worker_item_retry | pre_worker_teaching_retry
execution.worker_id = <claimer>
execution.lease_token = N  (incremented)
event = native_retry_accepted then pre_worker_retry_claimed
```

HTTP accept alone leaves `worker_id=null` (claimable); worker claim sets ownership.

## 10. Simulated dead-worker state

```text
execution.worker_id = d03-w1 (or equivalent)
execution.lease_token = N
execution.heartbeat_at = now - 120s
execution.lease_seconds = 30
# no release_execution / no except cleanup
```

## 11. Reclaimed state with higher lease token

```text
execution.worker_id = d03-w2
execution.lease_token = N+1 (or greater)
event = pre_worker_retry_reclaimed
status unchanged (still planning_teaching / item_generation)
```

## 12. Final `awaiting_teaching_approval` state

```text
status = awaiting_teaching_approval
teaching_review.status = pending
execution.last_error = null
execution.work_kind = null
execution.worker_id = null
generation.error / error_type / error_code = null
```

## 13. Proof old worker was fenced

D03/D06: after reclaim, `assert_lease(worker_id=old, lease_token=N)` and/or `run_pre_worker_retry(old_lease)` raise `LeaseLostError`. Teaching persist is lease-fenced via `save_teaching_plan(worker_id=..., lease_token=...)`.

## 14. Proof item executor not called after item checkpoint

D04 / I02: after `_run_items_under_lease` checkpoints to `planning_teaching`, reclaim runs teaching with item executor patched to `AssertionError`; item call list length remains 1.

## 15. Proof `failed_cards` survived success

H01: `merge_item_generation_summary` with empty incoming `failed_cards` retains prior failure row; attempts remain append-only (timeout + success).

## 16. Prior hardening suite remains green

**119 passed / 0 failed** on the full regression command above (includes terminology, items, failure sync, streaming, fencing, visuals, PDF, native status, native-only routing, R + D/H/I).

---

# Final gate

```text
[x] /retry-native returns before LLM work finishes
[x] request cancellation cannot stop accepted retry
[x] abandoned item retry is discoverable after restart
[x] abandoned teaching retry is discoverable after restart
[x] stale leases are reclaimable
[x] stale workers are fenced
[x] item success checkpoint prevents item recomputation
[x] teacher gate remains mandatory
[x] duplicate workers cannot double-execute
[x] failed_cards is append-only
[x] attempts remains append-only
[x] GenerationModel error aliases remain synchronized
[x] successful recovery clears current error state
[x] visual retry remains separate
[x] final SHA/reload fencing remains green
[x] all previous hardening regression tests pass
```

## Scope preserved

No LessonPacket / legality / form / writer / streaming / visual redesign. No legacy stage2 recovery. Teacher approval still required before post-approval execution. Visuals remain on `/visuals/retry`.

## Next step (out of scope)

Real browser E2E: UI → Docker Postgres → real LLMs → teacher gates → streaming → visual provider → reload → PDFs.
