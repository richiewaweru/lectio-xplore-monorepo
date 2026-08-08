# Lease Fencing Correction — Completion Report

Branch: `pageobject-integration`  
Base: `2f33bf2` (+ evidence `f67baf0`)  
Evidence date: 2026-08-08

## 1. Commit SHA

`61809c0671f0ebde33aa3ccbecce1fdffc4e0340`

## 2. Files changed

### Source
- `apps/textbook-agent/backend/src/planning/whole_lesson/repository.py` — `require_execution_lease`; lease args on `save_lesson_packet` / `save_lesson_legality` / `save_catalogue_meta`
- `apps/textbook-agent/backend/src/v3_blueprint/planning/persistence.py` — lease-fenced `append_item_attempt_records`
- `apps/textbook-agent/backend/src/generation/v3_studio/router.py` — lease through `_generate_shared_pack_items` / `_persist_item_results`
- `apps/textbook-agent/backend/src/planning/whole_lesson/native_retry.py` — atomic item summary+checkpoint; teaching chunked stage folded into fenced release
- `apps/textbook-agent/backend/src/planning/whole_lesson/service.py` — every teaching write receives lease args

### Tests / evidence
- `tests/planning/test_native_retry_lease_fencing.py` — F01–F07
- `docs/evidence/native-hardening-streaming/LEASE_FENCING_REPORT.md`
- `docs/evidence/native-hardening-streaming/lease-fencing-pytest.txt`

## 3. Exact test commands

```text
cd apps/textbook-agent/backend
.\.venv\Scripts\python.exe -m pytest tests/planning/test_native_retry_lease_fencing.py -q --tb=short

.\.venv\Scripts\python.exe -m pytest ^
  tests/planning/test_phase01_terminology_legality.py ^
  tests/v3_execution/test_phase02_item_observability.py ^
  tests/v3_execution/test_item_attempt_durability.py ^
  tests/planning/test_pre_worker_failure_sync.py ^
  tests/planning/test_native_retry_pre_worker.py ^
  tests/planning/test_native_retry_durability.py ^
  tests/planning/test_native_retry_lease_fencing.py ^
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

## 4. Pass / fail count

**126 passed / 0 failed** (prior 119 + F01–F07).

## 5. F01–F07 results

| ID | Result |
|---|---|
| F01 | PASS — stale item worker `LeaseLostError`; no PackItems / OK attempts; worker-2 owns token |
| F02 | PASS — PackItem stems only `Stem from worker 2` |
| F03 | PASS — stale teaching cannot persist plan/ready/awaiting after reclaim |
| F04 | PASS — final arc `worker-2-arc`, catalogue hash `hash-w2` |
| F05 | PASS — stale token cannot append success events |
| F06 | PASS — healthy leased path → approval; failed_cards retained |
| F07 | PASS — current-worker TIMEOUT persists journal + aliases + `failed_recoverable` |

## 6. Stale item worker race trace

```text
accept → claim w1 token N → enter blocked item LLM
age heartbeat → reclaim w2 token N+1
unblock w1 valid items → LeaseLostError at fenced append/PackItem write
PackItems=0; no OK attempt rows; execution.worker_id=w2
```

## 7. Worker-2 PackItems vs rejected worker-1

F02: worker-2 persists stems `Stem from worker 2 *`; after unblock, worker-1 cannot overwrite. Final stems contain only worker-2 prefixes.

## 8. Stale teaching worker race trace

```text
accept → claim w1 → packet+legality under lease → blocked planner LLM
reclaim w2 → unblock w1 planner output
→ LeaseLostError on save_catalogue_meta / subsequent fenced writes
teaching_plan empty; no teaching_plan_ready / awaiting_teaching_approval
```

## 9. Worker-2 teaching plan vs rejected worker-1

F04: final `teaching_plan.arc == worker-2-arc`; `catalogue.teaching_projection_hash == hash-w2`; worker-1 arc never lands.

## 10. Stale success events blocked

F05: `append_event(teaching_plan_ready|awaiting_teaching_approval|native_retry_items_complete)` with old token → `LeaseLostError`.

## 11–12. D01–D07 and H01–H03

Included in the 126 suite; all still green (durability file unchanged for D/H/I).

## 13. Prior 119 + new tests

Prior hardening 119 + 7 fencing = **126 passed**.

## 14. Static mutation audit (leased retry paths)

### `_run_items_under_lease` / `_generate_shared_pack_items`

| Mutation | Leased? | Boundary |
|---|---|---|
| ConceptCard / PackItem reads | n/a | read-only |
| `append_item_attempt_records` (attempts / failed_cards) | yes | FOR UPDATE + `require_execution_lease` + journal write + commit |
| PackItem upsert/stale/delete | yes | FOR UPDATE + `require_execution_lease` + PackItem writes + commit |
| item summary merge + `planning_teaching` checkpoint + `native_retry_items_complete` | yes | single `mutate_state(worker_id, lease_token)` |

### `_run_teaching_under_lease` / `run_and_persist_teaching_plan`

| Mutation | Leased? | Boundary |
|---|---|---|
| `teaching_plan_started` event | yes | `append_event(..., worker_id, lease_token)` → `mutate_state` |
| `save_lesson_packet` | yes | `mutate_state` |
| `save_lesson_legality` | yes | `mutate_state` |
| LLM planner | n/a | external; may finish after reclaim |
| `save_catalogue_meta` | yes | `mutate_state` |
| `save_teaching_plan` | yes | `mutate_state` |
| `teaching_plan_ready` event | yes | `append_event` → `mutate_state` |
| `awaiting_teaching_approval` event | yes | `append_event` → `mutate_state` |
| chunked stage flags + lease release | yes | fenced release `mutate_state` |

**Unfenced worker-owned writes found: zero.**

Non-leased callers omit lease args and keep prior behavior.

---

# Final gate

```text
[x] every item retry DB mutation is lease-fenced
[x] every teaching retry DB mutation is lease-fenced
[x] fencing occurs inside same transaction as mutation
[x] stale item worker cannot persist generated items
[x] stale item worker cannot overwrite newer PackItems
[x] stale teaching worker cannot persist planner output
[x] stale teaching worker cannot append success events
[x] worker-2 wins stale-worker races
[x] current healthy worker path still works
[x] failure diagnostics still persist
[x] item checkpoint remains durable
[x] restart reclaim still works
[x] teacher approval gate remains mandatory
[x] failed_cards remains append-only
[x] visual retry remains isolated
[x] existing 119-test suite remains green
[x] all new adversarial fencing tests pass
[x] static mutation audit reports zero unfenced leased-retry writes
```

## Next step (out of scope)

Live browser E2E. No further architecture hardening rounds.
