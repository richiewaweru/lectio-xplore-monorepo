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
- Live current-flow smoke: pending; no live generation has been claimed.
- Pack comparison: checked against current `main`; Teaching Plan hashing, shared tasks, six primitives, AuthoringEngine and three model slots exist; Learn and Print still invoke ordinary composition independently. No material SHA drift found.
- Phase status: Phase 0 IN PROGRESS (authenticated local smoke pending); Phase 1 PASS (additive generic runtime); Phase 2 IN PROGRESS; Phases 3–16 NOT STARTED. The external OAuth-origin setup remains open for the live Phase 0 smoke; no phase is marked PASS without its own gate.

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
- Implementation: the teacher review shows v2 learner title, starting and target state, each section's title/entry/must-establish/avoid-repeat/bridge/exit commitments, and existing blocks/evidence alongside verified pending or approved identity. V1 historical rendering remains readable. The approval helper rejects incomplete visible v2 content and still requires matching current pending revision and verified content hash.
- Tests: focused frontend Vitest 6 PASS; `pnpm check` PASS (0 errors, 5 existing unrelated warnings); `pnpm build` PASS; `pnpm program:domain-guards` PASS (zero violations, 8 guard tests); `git diff --check` PASS.
- Failure proof: blank v2 title, missing exit state or blocks, invalid first bridge, blank hash, and mismatched revision disable approval.
- Decision: `03_INVARIANTS_AND_NON_GOALS.md` excludes arbitrary field-level Teaching Plan editing from first cut. Approval HTTP requires the displayed exact content hash. `edit_teaching_plan` has no active backend caller, so the active approval path receives a planner-reviewed candidate. Any future edit entrypoint must not bypass semantic review.
- Status: package PASS. Phase 2 remains IN PROGRESS pending full phase verification and a zero-caller guard for the dormant edit entrypoint.

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
- [ ] 2 Teaching Plan (IN PROGRESS)
- [ ] 3 SharedDocument contract
- [ ] 4 Shared tasks
- [ ] 5 Section Composer
- [ ] 6 Section Writer
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
