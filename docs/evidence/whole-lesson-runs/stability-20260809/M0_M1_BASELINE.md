# M0/M1 baseline evidence (2026-08-09)

## Starting state

- Repository: `C:\Projects\lectio`
- Starting SHA: `26741d0866cb0910504f4092c3f4a3eb19f32c4c`
- Branch: `main`
- Production tree: clean at start; pre-existing untracked orchestration files were `PLAN.md` and `.codex/agents/sol-reviewer.toml`.
- Scope: deterministic candidate-fix verification and native hardening regression only. No production/test edits, browser/provider calls, or service restarts.

## Candidate-fix review

1. **Form planner exception preservation** — `apps/textbook-agent/backend/src/planning/whole_lesson/form_agent.py` retains the final `BaseException` and re-raises it after two attempts. This preserves typed transport/timeout classification for the native failure policy; the generic `RuntimeError` remains only for a non-exception/empty error fallback.
2. **Native retry UI** — `apps/textbook-agent/frontend/src/routes/studio/+page.svelte` adds `handleNativeRetry`, calls `retryNativeGeneration`, refreshes authoritative chunked status, and labels the action from `next_action` (`retry_teaching`, `retry_visuals`, otherwise lesson items). Recoverable and terminal rendering are distinct.
3. **Completed V2 PDF status** — `apps/textbook-agent/frontend/src/routes/studio/generations/[id]/+page.svelte` projects a detected `LectioDocumentV2` to `final_ready`, enabling the final PDF export controls.

## Exact commands and results

### Backend candidate-fix suite

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\\.venv\\Scripts\\python.exe -m pytest tests\\planning\\test_contract_hardening.py -q --tb=short
```

Result: **20 passed**, 0 failed, 1 warning (`GenerationFieldContract.schema` shadows a Pydantic parent attribute), 27.69s.

### Frontend candidate-fix suites (PowerShell path quoting corrected)

```powershell
cd C:\Projects\lectio
pnpm --dir apps/textbook-agent/frontend test -- "src/routes/studio/page.test.ts" "src/routes/studio/generations/[id]/page.test.ts"
```

Result: **2 files passed, 28 tests passed**, 0 failed, 81.25s. One expected diagnostic line was emitted by the SSE failure test (`[chunked] section failed model [ 'boom' ]`).

### Native hardening/recovery regression (PowerShell line continuations corrected to one line)

```powershell
cd C:\Projects\lectio\apps\textbook-agent\backend
.\\.venv\\Scripts\\python.exe -m pytest tests\\planning\\test_native_only_routing.py tests\\planning\\test_native_status_payload.py tests\\planning\\test_native_retry_pre_worker.py tests\\planning\\test_native_retry_durability.py tests\\planning\\test_native_retry_lease_fencing.py tests\\planning\\test_phase02_queue_and_lease.py tests\\planning\\test_phase02_worker_failure_policy.py tests\\planning\\test_phase05_visual_dispatch.py tests\\planning\\test_visual_dispatch_failure.py tests\\planning\\test_phase02_visual_pdf_routes.py -q --tb=short
```

Result: **138 passed, 2 failed**, 1 warning, 76.55s. The two failures reproduce in the focused queue/lease file:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests\\planning\\test_phase02_queue_and_lease.py -q --tb=short
```

Result: **72 passed, 2 failed**, 37.84s.

Failures: `test_two_workers_cannot_both_claim_queued` and `test_stale_active_contention_one_winner` both observe zero winners. The test helper seeds `teaching_review.status="pending"`; `claim_next_native_job` intentionally skips `pending`/`rejected` review states in `src/planning/whole_lesson/repository.py` (guard around lines 1607–1618), even when `GenerationModel.status` is `queued` or an active writing stage. Therefore no claim is attempted. This is a deterministic fixture/contract mismatch: the production approval path should persist an approved review before queueing. It is unrelated to the three M1 candidate fixes. No production or test changes were made.

## Remaining proof

Deterministic tests do not provide the mandatory browser proofs: form-timeout checkpoint retry, native-only Home/New Lesson reachability, automatic ready-to-viewer navigation, live visual provider/asset patch and both PDFs, worker restart/reclaim, telemetry attribution, or final persistence/reload hashes. These remain for later milestones and SOL acceptance.
