# Shared Document Overhaul Runbook

## Execution record — 2026-09-24

- Branch: `codex/shared-document-overhaul`
- Starting `main` SHA: `d75d19125dfd6c849c5363b63f0269074faf53d1`
- Phase 0 baseline correction commit: `f8f99b5a`.
- Migration-code head: `20260913_0042`
- Applied local PostgreSQL migration head: `20260913_0042` (`uv run alembic current`)
- Applied local PostgreSQL migration head after Phase 1A: `20260924_0043` (`uv run alembic upgrade head`; `uv run alembic current`). The 0043 migration is additive; no probe rows persisted.
- Target: local/staging proof; production rollout is separate.
- Repository state at start: clean.
- Baseline validation: `scripts/verify-phase.ps1 -Phase full` ran. Page tests 64/64 PASS; page check PASS; backend 1 failed, 1358 passed, 5 skipped, 2 deselected; frontend check PASS with 5 existing warnings; frontend tests and build PASS; page PDF fixture gate PASS. The wrapper hung after the PDF gate and was interrupted, so its final clean-tree step was run separately (`git diff --check`, PASS).
- Backend baseline failure: `tests/reliability/test_correction_pass.py::test_t04_concurrent_claims_admit_one_owner` allowed two SQLite claimants with token 1. Reproduce and resolve or explicitly replace with a PostgreSQL concurrency gate before Phase 0 PASS.
- Baseline domain guards: `pnpm program:domain-guards` FAILS on current `main` with three pre-existing curriculum→print imports (`curriculum/items/diagnostics.py:36`, `curriculum/planning/persistence.py:14,312`). This is a baseline architecture defect to resolve before the final guard gate; it is not a regression from this branch.
- Phase 0 backend correction: SQLite Learn lease claims now acquire a write lock before reading; curriculum failure classification uses the infrastructure policy; Print lease validation for item-journal writes moved to the application layer so validation and append share a transaction. Focused reliability/planning/generation run: 45 passed, 1 deselected. `pnpm program:domain-guards`: PASS, including 8 guard tests. `uv run pytest -q --tb=short -o log_cli=false`: PASS, 1359 passed, 5 skipped, 2 deselected, 25 warnings (629.10s). `git diff --check`: PASS. The existing concurrent-claim failure test now passes. No migration or deletion in this correction.
- Full phase verification rerun: `scripts/verify-phase.ps1 -Phase full` PASS and exited 0 after fixing the PDF fixture preview subprocess cleanup. Page tests 64/64; page check 0 errors/warnings; backend 1359 passed, 5 skipped, 2 deselected, 25 warnings; frontend check 0 errors/5 existing warnings; frontend tests 57 files/225 tests; frontend build PASS; PDF fixtures 6/5/5 pages; `git diff --check` PASS. A standalone `pnpm --filter @lectio/page pdf:fixture` also exited 0 after the startup-failure cleanup and left no listener on port 4173.
- Local UI access: frontend dev server was down; restarted on `127.0.0.1:5173`. Its ignored local `.env` pointed `PUBLIC_API_URL` at `localhost:8001` while the backend listens on `127.0.0.1:8000`; corrected to `http://127.0.0.1:8000`. Same-origin proxy now returns the same authenticated `401` as the backend, instead of a proxy error. The in-app `/units` page now redirects to login rather than showing the 500. Google sign-in reports the local origin is not authorized for the configured client in an isolated browser.
- Phase 0 live-smoke recheck: frontend/backend listeners respond at `127.0.0.1:5173`/`:8000`, `/units` and `/login` return 200, `/health` responds, and direct/proxied `/api/v1/auth/me` return the expected unauthenticated 401. Backend and frontend Google client IDs match (values not recorded). The configured backend `FRONTEND_ORIGIN` is `http://localhost:5173`; the Google OAuth client's Authorized JavaScript origins must include that exact origin. There is no repository-supported local auth bypass. User action for the external OAuth client was requested; authenticated smoke remains pending.
- Live current-flow smoke: pending; no live generation has been claimed.
- Pack comparison: checked against current `main`; Teaching Plan hashing, shared tasks, six primitives, AuthoringEngine and three model slots exist; Learn and Print still invoke ordinary composition independently. No material SHA drift found.
- Phase status (2026-09-25): Phase 0 IN PROGRESS (authenticated local smoke pending); Phases 1–6 PASS. Phase 7 continuity, assembly, bounded boundary repair, and draft/READY persistence are integrated but Phase 7 remains IN PROGRESS pending semantic document QA, trusted composer-shape handoff, orchestration, and full gate. Phase 8 early media contract and generic active-leaf replacement are integrated; durable media execution and its full gate remain IN PROGRESS. Phase 10A Learn and Phase 11A Print pure adapters are isolated; no route cutover has occurred. Phase 9 and remaining Phase 10–16 cutovers are NOT STARTED. The external OAuth-origin setup remains open for the live Phase 0 smoke.

## Parallel work allocation

| Stream | Owner | Isolated scope | Handoff gate |
| --- | --- | --- | --- |
| Phase 3 full verifier | Luna | Main worktree, read-only verification of integrated contract | Full script exits 0; Sol records phase decision. |
| Phase 4A shared task meaning | Luna | `shared-task-contract` worktree; `curriculum/shared_tasks/` and focused tests | Closed response/evaluation and action-coverage tests; integrated after Phase 3 gate, full Phase 4 verifier running. |
| Phase 5 Section Composer | Luna | `section-composer` worktree; new shared section composition/validation and focused tests | Closed node shape and deterministic invalid-state tests; Sol integrates after Phase 4 contract review. |
| Phase 6A Section Writer contract | Luna | `section-composer` worktree after composer commit; generic ordinary-content writer and focused tests | Fixed shape, bounded repair and fail-closed semantic validation; Sol integrates after Phase 5 gate. |
| Phase 6B Durable section execution | Luna | `shared-document-runtime` worktree based on composer/writer commits; new document runtime adapter and focused tests | Four-call concurrency cap, fenced section work, targeted retry and sibling preservation; Sol integrates after Phase 6A review. |
| Phase 7A Continuity and document QA | Luna | `continuity-qa` worktree; new pure validation modules and focused tests | Typed issues, boundary checks and targeted repair contract; Sol integrates after writer contract review. |
| Phase 10A Learn realization adapter | Luna | `learn-shared-realizer` worktree; new adapter and focused tests | Exact SharedDocument/source verification and Learn interactions; no route cutover until Phase 9. |
| Phase 11A Print realization adapter | Luna | `print-shared-realizer` worktree; new adapter and focused tests | Exact SharedDocument/source verification and Print treatments/answer key; no route cutover until Phase 9. |
| Phase 8A Media adapter | Luna | `continuity-qa` worktree after QA commit; new figure media adapter and focused tests | Required media failure blocks READY; generated assets bind to exact frozen figure semantics. |

The Phase 4 and Phase 5/6A streams preserve current `SharedTaskSpec` outer fields and do not edit each other's modules. Durable writer execution and Learn/Print cutovers wait for integrated contracts. Sol owns the main runbook, cross-stream review, merge order, and phase PASS decisions.

## Phase 1A — generic runtime persistence

- Starting SHA: `f8f99b5a`.
- Ending SHA for package 1A: `d72fbf5f`.
- Implementation: added Build/Run/WorkItem/Event ORM, closed status contracts, owner-scoped Build admission and Run reads, idempotent Run admission, stable WorkItem keys, sequenced append-only events, ready immutability, and migration `20260924_0043`. No product cutover or deletion.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (11); `pnpm program:domain-guards` PASS (8 guard tests); scoped Ruff check/format and `git diff --check` PASS; `uv run alembic heads` reports `20260924_0043`.
- Failure proof: duplicate admission, conflicting source identity/hash, WorkItem key conflict, cross-owner Build rejection, invalid status, incomplete ready output, direct SQL ready-row update/delete, Event update/delete, lineage deletion rejection, and post-ready Event append.
- PostgreSQL proof: `uv run alembic current` changed from `20260913_0042` to `20260924_0043`; four tables, 29 constraints, six triggers observed. In a rolled-back transaction, queued-to-ready succeeded and ready Run/WorkItem UPDATE/DELETE and Event UPDATE/DELETE were rejected.
- Status: package PASS; Phase 1 remains IN PROGRESS pending fenced execution, retries/checkpoints, APIs, and its full phase gate.

## Phase 1B — work-item execution core

- Starting SHA: `d72fbf5f`.
- Ending SHA for package 1B: `15e1f378`.
- Implementation: source-verified WorkItem claim, PostgreSQL `FOR UPDATE SKIP LOCKED` plus SQLite conditional claim, monotonic lease fencing, bounded attempt accounting, heartbeat, and fenced checkpoint read/write with exact schema/source/input/definition/composition compatibility. First claim starts the Run atomically; inactive Run races roll back the item claim. No product cutover, provider calls, migration, or deletion.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (29); scoped Ruff check/format, `pnpm program:domain-guards` (8 tests), architecture guard (0 violations), and `git diff --check` PASS.
- Failure proof: competing claims, stale heartbeat/checkpoint writes, source-hash conflict, expired-lease recovery, bounded attempts, checkpoint compatibility and integrity rejection, and Run terminal-state race. Ready siblings remain unchanged.
- PostgreSQL proof: a disposable two-session probe at DB head `20260924_0043` passed 10 checks: SKIP LOCKED contention, pre-expiry rejection, source conflict before mutation, expired takeover at attempt/token 2, stale worker rejection, and compatible checkpoint persistence. Both probe attempts cleaned up their exact fixture rows; zero fixture Build/Run/WorkItem/Event rows remained. The first attempt had a temporary probe timestamp-conversion error, corrected before the passing rerun.
- Status: package PASS. Phase 1 remains IN PROGRESS; later packages cover outcomes, finalization, cancellation, HTTP, and the full phase gate.

## Phase 1C — work-item outcomes and recovery

- Starting SHA: `15e1f378`.
- Ending SHA for package 1C: `7f960861`.
- Implementation: fenced completion with canonical output hash and read-only duplicate acceptance; typed safe failure with explicit recovery action; targeted retry that preserves healthy siblings and compatible checkpoints; expired max-attempt reconciliation; serialized Run aggregation under the parent Run lock. No migration or product cutover.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (41 in 83.55s); scoped Ruff check/format PASS; `pnpm program:domain-guards` PASS (8 tests); `uv run python ../tools/agent/check_architecture.py --format text` PASS (0 violations); `git diff --check` PASS.
- Failure proof: wrong output hash, stale completion/failure after takeover, inactive parent Run, invalid recovery action, exhausted and nonretryable failure, targeted retry race, expired-lease reconciliation race/restart, and mixed sibling status. Ready sibling output remains immutable.
- Status: package PASS. Phase 1 remains IN PROGRESS; whole-Run validation/finalization, cancellation, status/retry/cancel HTTP, and the full phase gate remain pending.

## Phase 1D — whole-Run completion and cancellation

- Starting SHA: `7f960861`.
- Ending SHA for package 1D: `29e08bec`.
- Implementation: finalization uses trusted source and artifact loaders in the same transaction, recomputes durable hashes, checks every ready WorkItem output, rechecks the complete child set after locking the Run, and commits ready with output identity/hash. Cancellation fences non-ready items and preserves ready siblings. Dynamic WorkItem admission is legal while a Run is queued/running, serialized with terminal transitions; SQLite refreshes identity-map state after its write lock.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (52); scoped Ruff check/format PASS; `pnpm program:domain-guards` PASS (8 tests); architecture guard PASS (0 violations); `git diff --check` PASS.
- Failure proof: missing/mismatched stored source or artifact, invalid artifact JSON/hash, unfinished or changed child set, duplicate finalization, cancel-after-ready and finalize-after-cancel, stale worker after cancellation, add-after-terminal, and SQLite stale identity-map admission. Healthy ready siblings remain unchanged.
- PostgreSQL proof: disposable two-session terminal race passed both orderings. Finalization first committed ready and rejected cancellation; cancellation first committed cancelled and rejected finalization. Each Run had exactly one terminal event. Exact probe fixtures were removed; all six event/ready guard triggers were confirmed enabled. Initial fixture cleanup was blocked by the append-only Event trigger; scoped transactional cleanup disabled only relevant delete guards for exact fixture rows and restored them.
- Status: repository package PASS. Phase 1 remains IN PROGRESS. A separate additive migration must reject direct SQL WorkItem insertion under a ready Run; this cannot be enforced by repository admission alone. HTTP and full phase verification remain pending.

## Phase 1E — database terminal-state guards

- Starting SHA: `29e08bec`.
- Ending SHA for package 1E: `dbb615b2`.
- Implementation: additive migration `20260924_0044` in both migration trees. PostgreSQL and SQLite reject WorkItem INSERT unless the parent Run is queued/running, and reject Run ready transition without at least one child and all children ready. Existing immutability and append-only guards remain.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (53 in 128.67s); Ruff check/format PASS; `pnpm program:domain-guards` PASS; architecture guard PASS (0 violations); `git diff --check` PASS. Both migration copies are identical and LF-only.
- PostgreSQL proof: `uv run alembic heads` and `uv run alembic current` both report `20260924_0044 (head)`. Two-session insert-versus-ready and insert-versus-terminal probes serialized correctly; the ready transition rejected an unfinished newly inserted child, and later insert under terminal Run rejected. Exact fixtures cleaned to zero rows; all eight generation triggers enabled.
- Status: package PASS. Phase 1 remains IN PROGRESS pending generic HTTP status/action APIs and full phase verification.

## Phase 1F — generic status and legal action HTTP

- Starting SHA: `dbb615b2`.
- Ending SHA for package 1F: `28e87455`.
- Implementation: owner-scoped `/api/v1/generation` Build and Run status, targeted WorkItem retry, and Run cancellation. Status projects authoritative persisted state, active stages, ready-only completion, failed/cancelled counts, safe errors, allowed actions, and source/output identity and hashes. No generic creation endpoint is exposed before product source authorization/materialization is wired. Retry checks ownership before disclosing item state.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (60 in 178.22s); HTTP module 7 PASS; Ruff check/format PASS; `pnpm program:domain-guards` PASS (8 tests); architecture guard PASS (0 violations); `git diff --check` PASS.
- Failure proof: unauthenticated calls, cross-owner/unknown indistinguishable 404, illegal transitions 409, targeted retry preserving ready sibling, cancellation idempotency and ready rejection, empty and mixed Build projection. Response excludes output payloads, checkpoints, and leases.
- Status: package PASS.

## Phase 1 full gate

- Starting SHA: `f8f99b5a`; implementation ending SHA: `28e87455`.
- `scripts/verify-phase.ps1 -Phase full`: PASS, exit 0. Page tests 64/64 and page check 0 errors/warnings; backend 1419 passed, 5 skipped, 2 deselected, 24 warnings; frontend check 0 errors/5 existing warnings, frontend tests 225/225, frontend build PASS; PDF fixture 6/5/5 pages PASS; diff check PASS.
- Phase 1 status: PASS. Generic persistence, fenced WorkItems, finalization/cancellation, database integrity guards, and owner-scoped status/actions are additive; no product creation path has cut over yet.

## Phase 2A — enriched Teaching Plan contract and identity

- Starting SHA: `b32a6044`.
- Ending SHA for package 2A: `17626133`.
- Implementation: explicit strict `TeachingPlanDraftV2` and v2 Teaching Plan fields for learner title, starting/target state, and section display title, entry/must-establish/avoid-repeat/bridge/exit state. V1 drafts and persisted approved snapshots remain readable; v1 serialization excludes v2-only defaults so their approval content identity is preserved. V2 materialization uses exact code-owned slot IDs and hashes all new pedagogical fields.
- Tests: 81 focused contract, draft, approval/hash, shared-plan and consumer tests PASS; Ruff check/format PASS; `pnpm program:domain-guards` PASS (8 tests); architecture guard PASS (0 violations); `git diff --check` PASS. Fixed v1 content hash fixture remains `79121d3b333a001c5023de3f5d7959066002dd5615b62c9b9e9e11ac13013698`.
- Failure proof: missing/blank/duplicate v2 state, malformed section bridge, invalid/duplicate/changed slot identity, and each new field changing the v2 hash. Semantic progression and target coverage were deferred to Phase 2C.
- Status: package PASS. Phase 2 remains IN PROGRESS pending planner prompt, validation, approval/review integration, and full phase gate.

## Phase 2B — enriched shared planner output

- Starting SHA: `17626133`.
- Ending SHA for package 2B: `b902c16b`.
- Implementation: active shared planner structured output now requires `TeachingPlanDraftV2` and materializes v2 plans. The prompt requires learner title, starting/target state, section entry/must-establish/avoid-repeat/bridge/exit state, exact code-owned slot/block identities, and continuity self-checks while retaining source/assessment/visual policy. Two-attempt repair and existing model/provider infrastructure remain.
- Tests: planner prompt/contract/V2 batch 77 PASS; pre-worker/V2/prompt batch 58 PASS; Print P05 production 7 PASS; Print/Learn P08 integration 5 PASS; targeted v1 rejection/V2 repair/code-owned identity PASS; Ruff PASS; `pnpm program:domain-guards` PASS (8 tests); architecture guard PASS (0 violations); `git diff --check` PASS.
- Failure proof: v1-shaped or missing-continuity provider output rejects at the planner boundary; bounded repair remains two attempts; exact slot/block identity stays code-owned in production integration fixtures.
- Status: package PASS. Phase 2 remains IN PROGRESS. Prompt self-checks and deterministic shape validation do not prove semantic progression, target coverage, or absence of duplicated responsibility; draft-level semantic QA is the Phase 2C gate and teacher review presentation is Phase 2D.

## Phase 2C — draft-level semantic continuity QA

- Starting SHA: `b902c16b`.
- Ending SHA for package 2C: `b367b96d`.
- Implementation: one structured semantic review per structurally valid v2 planner candidate, using the existing authoring provider and `ModelSlot.STANDARD` under the architecture-neutral `TEACHING_PLAN_SEMANTIC_REVIEWER` capability. Its closed findings cite exact materialized section/block IDs and cover lesson progression, adjacent exit-to-entry plausibility, target coverage, duplicated section responsibility, and task evidence. Blocking findings enter the existing second planner attempt; a second blocked candidate rejects. A clean result is bound to the candidate content hash before the planner returns an approval-ready plan. Invalid/unbound findings and provider/config/auth failures fail closed.
- Tests: combined focused reviewer, planner, model-policy, prompt, P05 and P08 integration batch 87 PASS; `pnpm program:domain-guards` PASS (zero violations and 8 guard tests); scoped Ruff PASS; `git diff --check` PASS.
- Failure proof: all five blocking finding families, invalid reviewer code or section binding, provider failure, hash mismatch, repair success, and two-attempt exhaustion. No unreviewed candidate returns from the active planner.
- Status: package PASS. Phase 2 remains IN PROGRESS pending teacher review presentation, approval-boundary resolution, and the full phase gate. The existing `edit_teaching_plan` domain method has no active backend caller but could create a pending draft without this review; do not claim that every possible edited draft is semantically reviewed.

## Phase 2D — teacher review presentation and approval boundary

- Starting SHA: `b367b96d`.
- Ending SHA for package 2D: `7c70a1d7`.
- Implementation: the teacher review shows v2 learner title, starting and target state, each section's title/entry/must-establish/avoid-repeat/bridge/exit commitments, and existing blocks/evidence alongside verified pending or approved identity. V1 historical rendering remains readable. The approval helper rejects incomplete visible v2 content and still requires matching current pending revision and verified content hash.
- Tests: focused frontend Vitest 6 PASS; `pnpm check` PASS (0 errors, 5 existing unrelated warnings); `pnpm build` PASS; `pnpm program:domain-guards` PASS (zero violations, 8 guard tests); `git diff --check` PASS.
- Failure proof: blank v2 title, missing exit state or blocks, invalid first bridge, blank hash, and mismatched revision disable approval.
- Decision: `03_INVARIANTS_AND_NON_GOALS.md` excludes arbitrary field-level Teaching Plan editing from first cut. Approval HTTP requires the displayed exact content hash. `edit_teaching_plan` has no active backend caller, so the active approval path receives a planner-reviewed candidate. Any future edit entrypoint must not bypass semantic review.
- Status: package PASS. Phase 2 remains IN PROGRESS pending full phase verification and a zero-caller guard for the dormant edit entrypoint.

## Phase 2E — Teaching Plan edit zero-caller guard

- Starting SHA: `7c70a1d7`.
- Ending SHA for package 2E: `9be72b86`.
- Implementation: AST architecture guard rejects production references to the dormant `edit_teaching_plan` helper and `TeachingRevisionStore.edit_plan` method, including aliases and module-qualified access; permits only the helper's own wrapper call. The first-cut edit non-goal is now executable.
- Tests: focused architecture guard and existing approval-content-identity tests 13 PASS; scoped Ruff PASS; `pnpm program:domain-guards` PASS (zero violations, 8 guard tests); `git diff --check` PASS.
- Failure proof: synthetic aliased import is rejected; existing HTTP approval tests reject missing submitted hash, stale revision, and mismatched content hash.
- Status: package PASS. Phase 2 remains IN PROGRESS pending the full phase verification script.

## Phase 2 full gate

- Starting SHA: `9be72b86`.
- First `scripts/verify-phase.ps1 -Phase full` run: FAIL, exit 1 solely in backend pytest (1479 passed, 2 failed, 5 skipped, 2 deselected, 25 warnings). Page tests 64 PASS and page check PASS; frontend check 0 errors/5 existing warnings, frontend tests 227 PASS, frontend build PASS; PDF fixture and final diff check PASS. The two R04 tests import P08's mocked teaching helper, but P08's clean reviewer fixture was module-local. Those R04 tests unintentionally called the external reviewer, which emitted progression/target findings with invalid block IDs; the strict review contract correctly rejected them. Keep production validation unchanged; move the fake reviewer into the shared test helper and rerun.
- Correction: P08's shared `_approve_shared_teaching` helper now scopes the clean reviewer fake alongside its planner fake; removed the module-local autouse fixture. Combined P08, both R04 regressions, and semantic-review tests 21 PASS (6 warnings); scoped Ruff and `git diff --check` PASS. Production reviewer and failure tests unchanged.
- Full verifier rerun from `0e47cac5`: `scripts/verify-phase.ps1 -Phase full` PASS, exit 0. Page tests 64 PASS and page check 0 errors/warnings; backend 1481 passed, 5 skipped, 2 deselected, 24 warnings; frontend check 0 errors/5 existing warnings, frontend tests 227 PASS, build PASS; PDF fixture 5 PDFs with page counts 6/6/5/5/5 PASS; final `git diff --check` PASS.
- Post-gate: `pnpm program:domain-guards` PASS (0 violations, 8 guard tests); backend architecture guard 0 violations; applied local Alembic head `20260924_0044`; only this runbook was modified in the main worktree.
- Phase 2 status: PASS. Active generated v2 Teaching Plans are structurally validated, semantically reviewed with bounded repair, shown completely to the teacher, approved against the displayed revision/content hash, and verifiable by consumers. Dormant field-level edit API has zero production callers and an executable guard. Production provider behavior still requires Phase 9 shadow quality proof.

## Phase 3A — SharedLessonDocument v1 contract

- Starting SHA: `7b3f7290`.
- Integrated commits: `7a55b7f4` (closed contract, hash, package wiring), `8c45598a` (required figure alt text and canonical shared-task fixture).
- Implementation: path-neutral `document.shared_lesson` defines six typed ordinary nodes with separate display/accessibility fields plus TaskAnchor; closed SharedSection/SharedLessonDocument v1, immutable SharedTaskSpec snapshot, exact approved Teaching Plan lineage, canonical learner-content/task/source hash, and consumer source verification. The backend wheel now packages `src/document`.
- Focused tests: 13 shared document contract tests PASS on integrated main branch; isolated-worktree Ruff, domain/architecture guards and built-wheel membership check PASS.
- Failure proof: unknown/path-specific fields, bad section order/IDs, missing or misbound TaskAnchor, task lineage mismatch, missing/blank figure alt text, stale content hash, source mismatch, and nested mutation reject.
- Full gate on integrated `8c45598a`: `scripts/verify-phase.ps1 -Phase full` PASS (`Verification passed for phase: full`, exit 0). Backend pytest: 1,494 passed, 5 skipped, 2 deselected, 24 warnings; frontend check 0 errors/5 existing warnings; frontend tests 57 files/227 tests; frontend build PASS with existing Svelte/optional-dependency warnings; page fixture PDF 5 outputs at 6/6/5/5/5 pages. The verifier also ran its page tests/check and diff gate successfully.
- Post-gate: `pnpm program:domain-guards` PASS (0 violations, 8 guard tests); `uv run python ../tools/agent/check_architecture.py` PASS (0 violations); applied local Alembic head `20260924_0044`; `git diff --check` PASS, with only this runbook modified.
- Phase 3 status: PASS. Phase 4 nested task semantics remain in a separate worktree; its strict finalization gate is staged separately from current Learn/Print validation.

## Phase 4A — finalized shared task semantics

- Starting SHA: `050aa127` after Phase 3 gate record.
- Integrated commits: `2da6cf03` (canonical action/response/evaluation matrix, strict task and plan/source finalizer), `df618c92` (preserve permissive active-path validation during staged cutover), `d22a3539` (enforce strict per-task semantics at immutable SharedLessonDocument boundary).
- Focused integrated evidence: document/task tests 35 PASS; active Print/Learn compatibility selection 43 PASS (10 existing warnings); Ruff PASS on touched task/document modules; `git diff --check` PASS.
- Failure proof includes incomplete choice options, incompatible action/response or evaluation, unknown answer key, stale Teaching Plan lineage, mismatched binding/source, and legacy aliases accepted only by old validators until cutover.
- Full gate attempt on `d22a3539`: page tests 64 PASS, page check 0 errors/warnings, then backend pytest failed due host `ENOSPC` (C: reached 0 bytes free) around 80–90% execution. The run reported 1,440 passed, 5 skipped, 2 deselected, 4 failed and 63 errors after logging/temp SQLite writes failed; it cannot establish a Phase 4 regression result. Focused 35/43-test checks above passed before disk exhaustion. Automatic review blocked removal of old test temp databases; user action to free storage is pending. Phase 4 remains IN PROGRESS, not PASS.
- Clean rerun on `d22a3539`/`68d6b9e5`: `scripts/verify-phase.ps1 -Phase full` PASS (`Verification passed for phase: full`, exit 0). Page tests 64 PASS; page check 0 errors/warnings; backend pytest 1,507 passed, 5 skipped, 2 deselected, 24 warnings; frontend check 0 errors/5 existing warnings; frontend tests 57 files/227 tests; frontend build PASS; PDF fixture gate 5 files at 6/6/5/5/5 pages; diff gate PASS.
- Post-gate: `pnpm program:domain-guards` PASS (0 violations, 8 guard tests); `uv run python ../tools/agent/check_architecture.py` PASS (0 violations); applied local Alembic head `20260924_0044`; clean main worktree and `git diff --check` PASS. C: remained above 2 GB free through completion.
- Phase 4 status: PASS. Strict final task meaning is enforced at the immutable SharedLessonDocument boundary; active Learn/Print legacy validators retain compatibility until their cutovers. Phase 5/6 implementation remains isolated until its own gate.

## Phase 5A — Section Composer

- Starting SHA: `531c31f8` after Phase 4 PASS record.
- Integrated commits: `f670df2b` (closed provider-selected section shape, deterministic IDs and code-owned TaskAnchors), `b9428886` (policy default/lint/format correction).
- Focused integrated evidence: composer/document/task selection 38 PASS; composer-only rerun 12 PASS; scoped Ruff and architecture guard PASS; `git diff --check` PASS.
- Full gate attempt: page tests 64 PASS and page check 0 errors/warnings; backend run was stopped after C: fell to about 205 MB free. The prior full gate had left about 2 GB free; this phase attempt began with about 2.3 GB and dropped below a safe threshold before backend progress. No Phase 5 full-gate result is claimed. User request to free more disk space is pending.
- Clean full rerun after user freed disk: `powershell -ExecutionPolicy Bypass -File scripts/verify-phase.ps1 -Phase full` exited 0. Page tests 64 PASS; page check 0 errors/warnings; backend 1,519 passed, 5 skipped, 2 deselected, 24 warnings; frontend check 0 errors/5 existing warnings; frontend tests 57 files/227 tests; frontend build PASS; PDF gate 5 files at 6/6/5/5/5 pages; script clean-worktree gate PASS. The run began at `29c96ab0`; a Learn cutover audit documentation-only commit `26b4ba5f` landed during the run. Source and tests were unchanged, and the worktree remained clean at the final gate.
- Post-gate: `pnpm program:domain-guards` PASS (0 violations, 8 guard tests); `uv run python ../tools/agent/check_architecture.py` PASS (0 violations); applied local Alembic head `20260924_0044`; `git diff --check` PASS and main worktree clean. C: remained above 10 GB free at completion.
- Status: PASS. Phase 6 package remains isolated pending its approval-boundary correction and own full gate.

## Phase 6 — Section Writer and durable execution

- Writer commit `5c17a42a` integrated as `b38e138a`, with repository lint correction `afbb0809`; writer/composer focused tests 26 PASS, scoped Ruff/format and architecture guard PASS. Runtime commits `22f97b93` and `e929fdb0`, and real SQLite integration-test commit `f4cd41f8` remain isolated. Runtime focused tests 35 PASS before the database package; database/runtime regression subset 60 PASS with the deliberate pending-plan failure excluded. Ruff and architecture guard PASS in the isolated runtime worktree.
- Approval-boundary failure: `test_shared_document_admission_rejects_hashed_pending_teaching_revision` fails with `DID NOT RAISE SectionRuntimeError`. A correctly hashed pending `TeachingRevisionRecord` currently admits a queued shared-document run because `TeachingPlanSource` checks ID/revision/hash but carries no approval record or status. Sol assigned a bounded runtime/source correction; Phase 6 cannot PASS until this test and the full gate pass.
- Isolated correction `ad86a657` requires an approved TeachingRevisionRecord and recomputes the record/source plan hashes. The strict pending-revision test and 12 focused runtime/SQLite tests pass. Sol identified a separate post-claim checkpoint error path that can leave an item running until lease expiry; a bounded correction and failure test are in progress before integration.
- Integrated runtime, concurrency, SQLite integration, approved-source, and post-claim checkpoint corrections: `7719c3f0`, `21c9564f`, `63b7b030`, `1c2b9749`, `2f5b7245`, and formatting `0cb80401`. The approved-source gate requires an approved `TeachingRevisionRecord`, recomputes record and source plan hashes, and rejects v1 plans. An invalid checkpoint after claim records terminal failure while healthy sibling output remains intact. Focused combined suite: 95 passed; Ruff, format, architecture, and diff checks PASS.
- First full verifier attempt: page tests 64 PASS, page check PASS, backend 1,552 passed/5 skipped/2 deselected, frontend check 0 errors/5 existing warnings, frontend build and PDF fixture gate PASS. Frontend Vitest failed when its worker exhausted native memory, so the command exited 1. A stale local Vite dev process with approximately 25 GB private committed memory was stopped; standalone frontend tests then passed 57 files/227 tests. The dev server was restarted under a supervised session and `/login` returned HTTP 200. This attempt does not count as a phase gate.
- Clean full rerun at `0cb80401`: `powershell -ExecutionPolicy Bypass -File scripts/verify-phase.ps1 -Phase full` exited 0 (`Verification passed for phase: full`). Page tests 64 PASS and page check 0 errors/warnings; backend 1,552 passed, 5 skipped, 2 deselected, 24 warnings; frontend check 0 errors/5 existing warnings; frontend tests 57 files/227 tests; frontend build PASS; PDF fixtures 6/6/5/5/5 pages PASS; clean-worktree check PASS.
- Post-gate: `pnpm program:domain-guards` PASS (0 violations, 8 tests); `uv run python ../tools/agent/check_architecture.py` PASS (0 violations); `uv run alembic current` reports applied PostgreSQL head `20260924_0044`; `git diff --check` PASS and main worktree clean. C: had approximately 11.0 GB free. Phase 6 status: **PASS**. No Phase 7 or 8 package is counted as integrated by this gate.

## Phase 7/8 integration — in progress

- Integrated continuity/QA `b38a4482`, deterministic assembly `f2f63bca`, document persistence/migration 0045 `3e018f1d`, approved-source assembly correction `57069668`, figure media adapter `9f4fa11f`, early media contract `ca110678`, bounded boundary validation and corrections `3ec25900`/`2594badf`/`8caa95d9`, draft/READY promotion and media-identity corrections `3c2f7c84`/`fb9f352a`, and final QA recomputation `0cd8dea0`. Integration fixture, boundary error classification, and lint corrections are `808b1cea`/`c716ad9a`.
- The READY promotion recomputes deterministic QA from the approved plan and caller supplied accepted composer shapes, and derives required figures from the immutable document. The orchestration caller must provide the exact accepted composer output; that trusted handoff is not yet implemented. Semantic document QA and the full Phase 7 gate are pending. A forged assembly QA result is covered by a deliberate failure test.
- Integrated generic active-leaf replacement and migration 0046 in `5a77f59d`/`9d8f167f`. A replacement preserves ready history, while finalization/status count only active leaves. The retry-reopen guard requires a fresh retry event after the latest failure. `uv run pytest tests/generation_runtime tests/document -q --tb=short -x`: **193 passed**, 1 existing warning. Scoped Ruff/format, architecture guard, and `pnpm program:domain-guards` PASS (0 violations, 8 guard tests). Phase 7 and 8 remain IN PROGRESS.
- Applied local PostgreSQL heads: 0045, then 0046 (`uv run alembic upgrade head`; `uv run alembic current` reports `20260925_0046 (head)`). Docker Desktop was briefly stopped between these checks and was restarted by the user. A rollback-only PostgreSQL probe passed ready WorkItem immutability, linked replacement of a failed item, and recoverable Run reopening; it left no probe rows. PostgreSQL concurrency and full phase verification remain pending.

## Phase 9/15 quality-proof preflight

- Read-only local PostgreSQL inventory: 35 non-skipped lessons on active paths; only 2 have both a verified approved Teaching Plan snapshot and current lesson provenance. Both are Science/conceptual (Grades 6 and 7). The other 33 cannot count until normal preparation and approval establish current provenance. No staging database URL is configured locally, and no authenticated SharedDocument shadow admission/dispatch endpoint exists yet.
- Proof bar remains 12 unique lessons across six archetypes (two each) plus eight regenerations. Current local data is insufficient for the 20-run program. Phase 9/15 proof has not started; lesson preparation, selection, and a gated shadow entry point are required.

## Baseline
- [x] branch recorded
- [x] starting SHA recorded
- [x] DB migration head recorded
- [x] backend full suite (baseline failure corrected; 1359 passed)
- [x] frontend tests/check/build
- [x] full phase verification script exits 0
- [ ] live current-flow smoke
- [x] clean working tree at starting baseline

## Phases
- [ ] 0 Baseline
- [x] 1 Generic runtime (PASS: additive persistence and HTTP)
- [x] 2 Teaching Plan (PASS: v2 contract, semantic review, hash-bound approval, full gate)
- [x] 3 SharedDocument contract
- [x] 4 Shared tasks
- [x] 5 Section Composer
- [x] 6 Section Writer (PASS: durable execution and full gate)
- [ ] 7 Continuity/QA
- [ ] 8 Media
- [ ] 9 Shadow proof
- [ ] 10 Learn cutover/deletion
- [ ] 11 Print cutover/deletion
- [ ] 12 Runtime convergence/deletion
- [ ] 13 API/frontend
- [ ] 14 DB cleanup
- [ ] 15 Live quality
- [ ] 16 Final convergence

## Per-phase record

```text
PHASE:
STATUS: NOT STARTED | IN PROGRESS | BLOCKED | PASS
GOAL:
STARTING SHA:
ENDING SHA:

IMPLEMENTATION:
TESTS:
FAILURE TESTS:
LIVE PROOF:
DELETION:
ARCHITECTURE GUARDS:
KNOWN LIMITATIONS:
EVIDENCE/IDS:
DECISIONS:
```

## Blocker protocol

Stop and escalate if:
- target contracts conflict;
- repository reality conflicts with an invariant;
- destructive migration is needed before replacement proof;
- an expected abstraction is absent;
- cross-phase architecture change is needed;
- shortcut would create a second architecture;
- provider limitation makes the closed contract impossible.

Do not silently invent a new architecture.
