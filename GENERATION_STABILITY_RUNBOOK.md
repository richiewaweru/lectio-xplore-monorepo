# Generation Stability Runbook

Current phase: P10 commit, push, and final report
Overall status: IN PROGRESS
Orchestrator: Sol
Implementer: Luna
Starting commit: 57177e66ce6b1d1e89c0e912b77212c7e138365b
Current commit: 57177e66ce6b1d1e89c0e912b77212c7e138365b (task changes ready for commit)

## Progress

- [x] P0 — Baseline, topology, protection
- [x] P1 — Canonical workspace truth
- [x] P2 — Teaching Plan review + immutable approval
- [x] P3 — Detach Print from shared preparation (PASS — accepted by Sol)
- [x] P4 — Learn/Print lifecycle symmetry (PASS — accepted by Sol)
- [x] P5 — One correction boundary per authored work item (PASS — accepted by Sol)
- [x] P6 — Frontend consumes backend truth (PASS — accepted by Sol)
- [x] P7 — Failure injection + concurrency proof (PASS — accepted by Sol)
- [x] P8 — Native local application proof (live Learn/Print ready and refresh proof complete)
- [x] P9 — Cleanup + compatibility (artifact/secrets audit and expanded tests complete)
- [ ] P10 — Commit, push, final report

## Active task

Owner: Luna
Task: P10 — complete the acceptance record, review/stage task files only, commit, and push `codex/generation-stability`.
Why: P8 live proof and P9 audit/regressions are complete; preserve unrelated user files while delivering the tested work.
Expected evidence: exact changed-file/test record, hygiene scan, final commit SHA, and remote push result. Never include `.gitignore`, the diagnosis note, env files, or private runtime logs.

### P2b progress checklist
- [x] Render pedagogical Teaching Plan fields separately from review status/revision in Units and Studio
- [x] Disable approval unless visible content, current pending state, verified hash, and matching revision are present
- [x] Submit the loaded pending content hash from both active approval callers and require it in the backend route
- [x] Re-fetch and verify the exact approved revision/hash/content before showing approval
- [x] Reject Print creation while a newer Teaching Plan draft is pending; prove no approval mutation
- [x] Run focused backend/frontend tests, frontend check/build, backend Ruff; record evidence
- [x] Self-review P2b scope and send to Sol for review

## Latest result

What changed: P8 found and fixed a missing success commit in the disposable-session Learn worker. Two old Learn outputs were recovered safely; one explicit third retry completed, and source approval/Print remained unchanged. Authenticated Learn and Print pages both rendered ready after refresh. P9 compatibility, hygiene, and failure-injection gates are complete.
Tests: Final expanded backend regression: 323 passed, 14 existing warnings in 197.77s. P04 worker fresh-session/finalization gate: 16 passed, 1 existing warning in 59.50s. Frontend canonical suite: 85 passed across 7 files. `npm run check`: 0 errors, 5 existing warnings; `npm run build`: passed with existing warnings. Scoped Ruff across all changed backend Python paths passed; architecture guard: `No architecture violations found`; CRLF-aware diff check passed.
Evidence: [P8 local proof](evidence/P8-local-proof-preparation.md) and [P9 cleanup/compatibility audit](evidence/P9-cleanup-compatibility-audit.md); prior P0–P7 evidence remains in phase files.
Open issues: No P8/P9 technical blocker remains. P10 task-only staging, final report, commit, and push are in progress. PostgreSQL two-worker competing completion remains the documented P8 live-proof boundary from P4; existing SQLite dispatch-CAS and single-worker completion regressions pass.

## Sol review

Decision: P0 PASS; P1 PASS; P2a PASS; P2b PASS; P2 PASS; P3 PASS; P4 PASS; P5 PASS; P6 PASS; P7 PASS; P8/P9 evidence complete and handed to Sol with final acceptance record.
Next instruction: Finish P10 task-only commit/push and final report; preserve `.gitignore`, diagnosis document, and private logs.

### P2a — Backend approval identity

Status: PASS — accepted by Sol. P2b is also accepted; P2 overall is PASS.
Findings: The digest excludes only `teaching_plan_id`, `revision`, `preparation_hash`, and `approval_status`; all other validated TeachingPlan fields participate. Approval validates revision and optional browser hash, recording `submitted` or transitional `server_current_compat`. Learn and Print verify/pin the same digest; explicit superseded snapshots are admitted only by pinned revision and verified digest. Historical hashless approvals fail closed for new work and expose `reprepare`, while existing output remains readable. Consumer admission and workspace projection apply the same rule to an omitted embedded plan revision. Shared-task/sourcebook identities now follow pedagogical content independently of upstream preparation identity. Full commands/results are recorded in [evidence/P2-approval-backend.md](evidence/P2-approval-backend.md).
Tests: Focused suite: 48 passed, 1 warning. Final expanded regression suite: 145 passed, 10 warnings, 156.63 s. Ruff passed. `uv run python ../tools/agent/check_architecture.py --format text`: `No architecture violations found` (exit 0; Sol run).
Next: P2a accepted; proceed with bounded P2b frontend/API review and strict hash binding only.

### P2b — Frontend Teaching Plan review

Status: PASS — accepted by Sol after the final follow-up regression/check. P2 overall is PASS.
Findings: The shared Teaching Plan view displays arc, sections/blocks, evidence and source scope, anchor usage, misconception focus, and learner actions. It separately displays review status/revision and the verified pending/approved content hash. Current pending hash verification plus exact plan/review/identity revision equality gates approval in both Units and Studio. Both callers POST the loaded hash, reload the review, and require verified approved revision/hash identity before continuing. Hashless active approval returns typed 409. When an older approved snapshot exists under a newer pending draft, Create Print returns typed 409 and leaves the pending ledger unchanged; it cannot auto-approve.
Commands: Backend from `apps/textbook-agent/backend`: `uv run pytest tests/curriculum/test_p2_approval_content_identity.py tests/curriculum/test_p02_shared_plan_gates.py tests/curriculum/test_smart_lesson_contracts.py tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py tests/application/test_p03_realization_gates.py -q`; `uv run ruff check src/application/unit_lesson/realize_print_handoff.py src/print/http/v3_studio/router.py tests/application/test_p03_realization_gates.py tests/curriculum/test_p2_approval_content_identity.py`. Frontend from `apps/textbook-agent/frontend`: focused `npm test -- src/lib/curriculum/lessons/teaching-plan-review.test.ts src/lib/curriculum/lessons/TeachingPlanReview.test.ts src/lib/api/v3.test.ts src/routes/studio/page.test.ts 'src/routes/units/[id]/lessons/[lessonId]/plan/page.test.ts'`; `npm run check`; `npm run build`.
Tests: Backend: 69 passed, 1 existing Pydantic warning, 84.28 s. Final focused frontend rerun: 55 passed across 5 files, including stale worker `ready` with valid current pending review. Check: 0 errors and 5 existing warnings in unrelated editor/canvas files. Build completed successfully with existing Svelte warnings and optional-dependency notices for canvas, utf-8-validate, bufferutil, and supports-color.
Files changed: active approval API/hash payload, shared Teaching Plan review component and predicates, Units and Studio review surfaces and route tests, Print pending-review guard and regression, and this runbook/worklog/evidence. P2a backend implementation and evidence remain unchanged.
Next: P2 accepted. P3 implementation is active and awaiting Sol's gate review.

### P3 — Print detachment

Status: PASS — accepted by Sol.
Findings: Create Print verifies the source's immutable approved Teaching Plan without mutating preparation state, admits a distinct queued output, and binds its ID/identity to the realization. Output state starts empty plus an explicit allowlist of immutable plan/semantic inputs, so legacy Print documents, writer state, checkpoints, visuals, and errors are not inherited. Worker status sync follows the output and does not resurrect stale/read-only realizations. Retry locks/rechecks the owned failed realization, pins the prior verified snapshot into a new output, and preserves the old output. Studio active ID/query/polling follows the detached output and reloads the verified approved plan on refresh/retry. Standalone Studio is supported only with the explicit native Studio marker; Unit/path provenance loss fails closed. Old preparation-linked ready Print output remains readable; non-ready legacy links remain read-only.
Commands and exact outcomes: See [P3 Print detachment evidence](evidence/P3-print-detachment.md).
Tests: Final P3 backend gate after the ready-artifact acceptance regression: 18 passed, 1 existing warning. Expanded queue/lease, native retry, Print production, route, and P3 suite: 161 passed, 7 existing warnings. Studio frontend suite: 34 passed. `npm run check`: 0 errors, 5 existing Svelte warnings. `npm run build`: passed with existing Svelte warnings and optional-dependency notices. Ruff passed; architecture checker reported `No architecture violations found`; scoped `git diff --check` passed.
Files changed: detached Print admission/retry and output lifecycle, workspace retry route, Studio approval/status polling, focused backend/frontend regressions, runbook/worklog, and P3 evidence. Earlier P0/P1/P2 changes remain in the shared uncommitted branch; unrelated `.gitignore` and diagnosis document are preserved.
Next: P3 accepted. P4 implementation is complete and awaiting Sol's gate review.

### P4 — Learn/Print lifecycle symmetry

Status: PASS — accepted by Sol.
Findings: Learn admission commits a distinct queued output before provider work. The Learn-owned lifespan worker rechecks source, path, approval, output owner, and pinned plan, then executes under the existing output-scoped lease. Ready output and editable lesson are linked to the same output ID. Explicit retry accepts only `failed_recoverable`, verifies the pinned snapshot, and uses a conditional update so one retry output is allocated while the failed output remains. Unit workspace polling is serialized and consumes canonical status/error. Pathless Studio Learn returns a typed recovery conflict because a Learn realization requires a PathLesson. Full concurrent PostgreSQL worker completion remains deferred to P8; Docker daemon is unavailable.
Commands: See [P4 evidence](evidence/P4-learn-lifecycle.md) for exact commands. Focused P4 backend: 33 passed, 1 existing warning. Final overlapping backend suite after the retry CAS: 77 passed, 5 existing warnings. Frontend focused suite: 61 passed; `pnpm run check`: 0 errors/5 existing warnings; `pnpm run build`: passed. Ruff and architecture guard passed; scoped diff check passed.
Tests: Admission replay and Unit HTTP 202, worker completion/editable linkage, foreign-output protection, ready completeness, explicit/concurrent retry with no orphan, stale status, Learn/Print isolation, and serialized queued-to-ready polling. Existing reliability tests cover competing Learn lease claim denial. PostgreSQL two-worker completion has not been established in this environment and is deferred to P8.
Files changed: Learn admission/worker execution and lifespan hook, Learn retry/status/error projection, Unit/Studio Learn routing and polling, focused backend/frontend tests, P4 evidence, this runbook, and worklog. `.gitignore` and the diagnosis document are preserved.
Next: P4 accepted. P5 read-only design checkpoint is active; wait for Sol review before product edits.

## P8/P9 final gate record

P8 live proof: authenticated Teaching Plan approval, PostgreSQL-backed Learn/Print admission, two interrupted Learn attempts reconciled to recoverable failure, and one explicit third retry completed with a linked editable output. The authenticated Learn and Print previews both showed ready; the Learn preview interaction returned correct feedback without saving attempts; both pages remained ready after refresh. Approval hash/revision and sibling output identity remained unchanged. Full IDs/states are in [P8 evidence](evidence/P8-local-proof-preparation.md).

P8 defect: the disposable-session Learn worker lacked a success commit after producer finalization. Session close rolled back final ready/document/editable-link writes. The worker now commits successful finalization; escaped failures park only under verified output owner, pinned approval, and current lease. Fresh-session success and injected finalization failure tests pass.

P9 final validation: expanded backend regression: 323 passed, 14 existing warnings, 197.77s; P04 worker suite: 16 passed, 1 warning; frontend canonical suite: 85 passed across 7 files; frontend check: 0 errors/5 existing warnings; frontend build passed; changed-backend Ruff passed; architecture guard reports no violations; CRLF-aware staged diff check passed. One D01 timing assertion failed in the first aggregate, then passed in isolation, its containing file, and the final aggregate. A resume fixture was updated to include its revision-bound persisted artifacts; no product behavior changed for either prior test failure.

P10 acceptance checklist:

- [x] Canonical backend state and frontend consumption verified.
- [x] Approval bound to displayed Teaching Plan revision/hash; approved snapshot remains immutable.
- [x] Learn/Print output identity, idempotency, retry and failure isolation verified.
- [x] Provider repair/error budget and typed recovery gates pass.
- [x] Authenticated native walkthrough covers approval, Learn, Print, interaction, and refresh.
- [x] Backend/frontend tests, frontend check/build, Ruff, architecture guard, and diff checks pass.
- [x] No secrets, env files, database files, browser profiles, or private runtime logs are included.
- [x] Unrelated `.gitignore` and diagnosis-note edits remain excluded.
- [ ] Task-only commit/push and final SHA recorded.
