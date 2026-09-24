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
- Phase status: Phase 0 IN PROGRESS (authenticated local smoke pending); Phase 1 IN PROGRESS (additive persistence work only); Phases 2–16 NOT STARTED. Phase 1 additive work proceeds while the external OAuth-origin setup remains open; no phase is marked PASS without its own gate.

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
- Implementation: source-verified WorkItem claim, PostgreSQL `FOR UPDATE SKIP LOCKED` plus SQLite conditional claim, monotonic lease fencing, bounded attempt accounting, heartbeat, and fenced checkpoint read/write with exact schema/source/input/definition/composition compatibility. First claim starts the Run atomically; inactive Run races roll back the item claim. No product cutover, provider calls, migration, or deletion.
- Tests: `uv run pytest tests/generation_runtime -q --tb=short -o log_cli=false` PASS (29); scoped Ruff check/format, `pnpm program:domain-guards` (8 tests), architecture guard (0 violations), and `git diff --check` PASS.
- Failure proof: competing claims, stale heartbeat/checkpoint writes, source-hash conflict, expired-lease recovery, bounded attempts, checkpoint compatibility and integrity rejection, and Run terminal-state race. Ready siblings remain unchanged.
- PostgreSQL proof: a disposable two-session probe at DB head `20260924_0043` passed 10 checks: SKIP LOCKED contention, pre-expiry rejection, source conflict before mutation, expired takeover at attempt/token 2, stale worker rejection, and compatible checkpoint persistence. Both probe attempts cleaned up their exact fixture rows; zero fixture Build/Run/WorkItem/Event rows remained. The first attempt had a temporary probe timestamp-conversion error, corrected before the passing rerun.
- Status: package PASS. Phase 1 remains IN PROGRESS; Phase 1C must reconcile expired max-attempt items to truthful failure state and add retry/cancel/final completion. HTTP and full phase verification follow.

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
- [ ] 1 Generic runtime (IN PROGRESS: additive persistence)
- [ ] 2 Teaching Plan
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
