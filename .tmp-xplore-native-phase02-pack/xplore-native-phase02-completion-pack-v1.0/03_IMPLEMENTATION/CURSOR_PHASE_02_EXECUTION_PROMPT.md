You are implementing **Phase 02 — Native Completion and Resilience**.

Repository: `richiewaweru/lectio-xplore-monorepo`  
Branch: `pageobject-integration`  
Baseline: `00cc3c7eea7c8d3bf5e56b4988f261e07aa247d6`

Read and follow, in order:

1. `00_READ_ME_FIRST.md`
2. `01_ARCHITECTURE/PHASE_02_RESOLVED_ARCHITECTURE.md`
3. `01_ARCHITECTURE/STATE_MACHINE_AND_WORKER_DESIGN.md`
4. `02_PATCH/PATCH_02_NATIVE_COMPLETION_AND_RESILIENCE.md`
5. `04_VERIFICATION/PHASE_02_VERIFICATION_PROTOCOL.md`
6. `04_VERIFICATION/FAILURE_INJECTION_MATRIX.md`
7. `04_VERIFICATION/PHASE_02_CHECKLIST.md`

## Mission

Patch 01 proved multiple lesson shapes reach `awaiting_teaching_approval`. Make the back half durable:

```text
approve teaching
→ durable queue
→ form plan
→ resumable block writers
→ DB-first assembly
→ persist/reload LectioDocumentV2
→ teacher PDF
→ student PDF
```

## Browser constraint

Do not depend on browser automation. Browser evidence is optional.

Use:

- local API drivers;
- real DB inspection;
- logs/events;
- deterministic failure injection;
- backend restart/reclaim;
- fresh-session document reload;
- direct PDF calls;
- PDF text assertions.

## Non-negotiables

1. `GenerationModel.status` is canonical.
2. Only one repository transition method writes status/stage.
3. Approval returns HTTP 202 and never runs the back half inline.
4. Worker ownership is DB-backed with lease and heartbeat.
5. Restart leaves work reclaimable.
6. Persisted valid form plan is reused.
7. Execution key is `section_id:block_id:variant_id`.
8. Ready blocks never regenerate.
9. One failed block does not cancel siblings.
10. Max writer concurrency is 3.
11. Do not share one SQLAlchemy session concurrently.
12. Assembly reloads from DB, never from process-local results.
13. Failed blocks prevent final completion.
14. Required pending visuals prevent final PDF export.
15. Teacher/student PDFs derive from one native document.
16. No new generation invokes `resume_stage2`.
17. Do not tune prompts, pedagogy, model tiers, or item budgets.
18. Do not introduce an external queue unless DB leasing is demonstrably impossible.

## Required work

### 1. Map current code

Before changing code, create `docs/evidence/whole-lesson-runs/phase-02/IMPLEMENTATION_MAP.md` listing exact routes/functions for approval, executor, repository, stage writes, startup hooks, document retrieval, PDF, and visual callbacks.

### 2. Canonical transition API

Implement atomic transition of canonical status, compatibility stage, heartbeat, event, and structured error. Add all legal/illegal transition tests. Remove direct assignments in the Phase 02 path.

### 3. Fast approval

Validate revision, persist approval, transition to queued, return 202. Duplicate approval is idempotent. Measure response latency.

### 4. DB-leased worker

Implement atomic claim, worker ID, lease, periodic heartbeat, stale reclaim, worker-owned session, graceful shutdown. Test two-worker contention.

### 5. Form-plan resume

Reuse persisted valid form plans. Do not regenerate them after restart.

### 6. Composite block outcomes

Persist full outcomes using `section_id:block_id:variant_id`, including attempts/timestamps/status/content/request ID/structured error.

### 7. Bounded concurrency and isolation

Run at most 3 writers concurrently. Every task returns an outcome. One failure does not cancel siblings. Persist safely.

### 8. Retry classification

Transport: 3 attempts with backoff/jitter. Validation: original plus one targeted repair. Keep prompt meaning unchanged.

### 9. Resume

Schedule only missing, retryable failed, or stale-started blocks. Skip ready and visual-pending. Do not auto-retry terminal failures.

### 10. DB-first assembly

Reload form plan and outcomes. Validate exact expected keys and object/intent identity. Reconstruct order. Do not pass the current writer list into assembly.

### 11. Persist and reload

Persist native document, commit, open a fresh session, reload and validate, then transition to `awaiting_visuals` or `ready`.

### 12. Direct native PDF proof

Use HTTP/API calls, not browser clicks. Save teacher/student PDFs, verify page counts, extract text, and assert a known answer phrase exists only in teacher output. Pending required visuals must produce a clear conflict.

### 13. Forced failure/restart proof

Add safe test-only failure injection, disabled by default. Required scenario:

1. start generation;
2. approve teaching;
3. fail one middle writer once;
4. prove later siblings finish;
5. stop backend;
6. restart backend;
7. reclaim stale job;
8. prove ready blocks skip;
9. retry only failed/missing work;
10. assemble from DB;
11. reload native document;
12. produce PDFs.

### 14. One conceptual run first

Do not start four official runs until one conceptual lesson passes the complete resilience and PDF gate.

### 15. Four official runs

Freeze one commit. Run Science, Mathematics, Economics, and English. Record exact inputs, prompts/responses, retries, events, latency, tokens/cost where available, DB state, document, and PDFs. Do not tune prompts between runs.

### 16. Legacy shutdown

Only after all four pass: remove new-generation `resume_stage2`/silent fallback; retain historical read-only v1; tag rollback.

## Evidence

Create `docs/evidence/whole-lesson-runs/phase-02/` with:

```text
IMPLEMENTATION_MAP.md
PHASE_02_REPORT.md
test-results.txt
state-transition-tests.txt
worker-claim-tests.txt
failure-restart-log.txt
db-verification.json
block-execution-report.json
native-document.json
native-document-reloaded.json
pdf-assertions.json
teacher.pdf
student.pdf
four-runs/
```

## Stop conditions

Stop and report if safe DB claim needs an unplanned migration, the native document endpoint is absent, PDF accepts only legacy packs, required visual semantics are ambiguous, page-object contracts must change, or a question-wall decision is required.

## Completion report

Report exact commits/files/tests/commands; state machine; worker lease; failure/restart evidence; ready-block skip evidence; DB-first assembly; fresh reload; PDF assertions; four generation IDs; stage latency; limitations; deviations.

Do not call Phase 02 complete until the forced failure/restart proof and teacher/student PDF assertions pass.
