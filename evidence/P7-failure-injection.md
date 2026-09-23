# P7 — Failure injection evidence

Status: implementation and deterministic test gate complete; awaiting Sol review. P8 has not started.

## Implemented proofs

- **Persisted Teaching Plan repair:** `tests/planning/test_pre_worker_failure_sync.py::test_teaching_repair_success_persists_only_valid_plan_and_waits_for_review` drives the real persistence boundary with a deterministic repair response. It asserts two provider calls, persists only the corrected plan, leaves review pending with no approved revision, and projects `awaiting_review`. Existing pre-worker schema and semantic exhaustion tests prove bounded calls, recoverable typed failure, no invalid plan persistence, and `retry_teaching` recovery. The structural-planner retry/exhaustion contract remains covered by the existing bounded Stage1 helper tests; the retired legacy structural route is not claimed as a live persistence path.
- **Actual provider dispatch accounting:** `tests/authoring_correction/test_a02_shared_authoring_engine.py::test_actual_dispatch_budget_covers_repeated_invalid_5xx_and_auth` patches `run_llm`, not the higher-level provider abstraction. Three repeated malformed outputs consume exactly three dispatch slots and exhaust repair; HTTP 503 and HTTP 401 each consume one slot, with transport exhaustion and terminal provider failure respectively. Model-correctable invalid output is the only case fed into correction.
- **Independent Learn/Print state:** `tests/curriculum/test_workspace_projection.py::test_p07_learn_print_state_truth_table_is_independent` covers eight representative state pairs. Path-specific output IDs and typed errors stay attached to their own path.
- **Expired Learn execution and sibling preservation:** `tests/application/test_p04_learn_worker.py::test_p07_expired_worker_is_parked_without_touching_ready_print_sibling` seeds a persisted expired execution lease, reconciles it to recoverable failure, then calls the worker again. The parked Learn row is not reclaimed; its checkpoint/budget remain, and the ready Print realization and approval stay unchanged. This is a deterministic persisted-state interruption simulation, not a process-kill test.
- **Corrupt/foreign output identity:** `test_p04_worker_parks_corrupt_foreign_output_without_mutating_it` runs five cases: foreign owner, wrong path, wrong preparation, wrong revision, and wrong hash. Each case proves the referenced output state is byte-for-byte unchanged while the realization is parked.
- **Detached Print export failure:** `tests/application/test_p03_realization_gates.py::test_p07_detached_print_export_failure_preserves_approval_and_ready_learn` injects a controlled export timeout at the Print repository failure-persistence boundary after output admission. Only the detached Print output/realization fails; source preparation approval and ready Learn remain unchanged, and workspace projection reports the Print error. This does not invoke the live PDF renderer itself.
- **Typed error and UI contract:** `tests/curriculum/test_workspace_projection.py` verifies typed failure fields survive projection; frontend `lesson-context.test.ts` covers invalid model output, provider terminal failure, and stale realization recovery. The Plan route test confirms a typed stale displayed-hash conflict cannot render approved state. A new Print page test exposed that preview-fetch 503 text could mask the canonical recoverable realization error; Print now prioritizes the canonical error and shows Retry only for that recoverable state.
- **Poll stop/restart:** `serialized-poll.test.ts` covers queued-to-ready refresh, stop at awaiting review/ready/recoverable/terminal states, and explicit retry restart.

## Commands and results

Backend, from `apps/textbook-agent/backend`:

```text
uv run pytest tests/planning/test_pre_worker_failure_sync.py tests/planning/test_contract_hardening.py tests/authoring_correction/test_a02_shared_authoring_engine.py tests/curriculum/test_workspace_projection.py tests/application/test_p04_learn_worker.py tests/application/test_p03_realization_gates.py tests/planning/test_phase02_queue_and_lease.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/planning/test_phase02_failure_classification.py tests/print_learn/test_p08_integration_gates.py -q
217 passed, 9 warnings in 115.34s

uv run ruff check tests/application/test_p03_realization_gates.py tests/application/test_p04_learn_worker.py tests/authoring_correction/test_a02_shared_authoring_engine.py tests/curriculum/test_workspace_projection.py tests/planning/test_contract_hardening.py tests/planning/test_pre_worker_failure_sync.py
All checks passed!

uv run python ../tools/agent/check_architecture.py --format text
No architecture violations found. (exit 0)
```

Frontend, from `apps/textbook-agent/frontend`:

```text
npm test -- src/lib/curriculum/lessons/lesson-context.test.ts src/lib/curriculum/lessons/serialized-poll.test.ts 'src/routes/units/[id]/lessons/[lessonId]/plan/page.test.ts' 'src/routes/units/[id]/lessons/[lessonId]/print/page.test.ts' 'src/routes/units/[id]/lessons/[lessonId]/learn/page.test.ts' src/routes/units/[id]/page.test.ts src/routes/studio/page.test.ts
7 files passed; 84 tests passed.

npm run check
svelte-check found 0 errors and 5 existing warnings in unrelated editor/canvas files.

npm run build
passed; existing Svelte warnings and optional dependency notices for canvas, bufferutil, utf8-validate, and supports-color.
```

Repository, from the workspace root:

```text
git -c core.whitespace=cr-at-eol diff --check
passed.
```

The broad backend command `uv run ruff check src ...` reported lint findings only in unchanged files (`curriculum/lesson_review/issue_projection.py`, `learn/generation/native_selection.py`, and `media/storage/image_store.py`) plus the P7 test-file findings subsequently fixed. Scoped Ruff over all P7-touched backend tests passes. No P7 product-code backend change was required.

## Limits and deferred proof

- No browser navigation E2E was run; it remains in P8.
- Docker/PostgreSQL competing-worker completion and row-lock race proof remain deferred to P8. P7 does not claim SQLite as proof of PostgreSQL behavior.
- Print failure is injected at repository persistence after a controlled export timeout, not by running the PDF renderer and forcing its internal failure.
- Worker interruption is represented through persisted expired-lease state and restart invocation; no OS process termination was injected.
- No product defect appeared in owner/corrupt identity, worker parking, or path-isolation assertions. The Print UI precedence issue described above was corrected and covered.
