# Phased Implementation Plan

## Phase 0 — Freeze baseline
Record main SHA/migration head, run full tests/build, live smoke, architecture baseline.
**Exit:** baseline reproducible.

## Phase 1 — Generic runtime persistence
Build Build/Run/WorkItem/Event persistence and APIs; reuse leases/checkpoints/budgets/error policy.
**Exit:** runtime contract/failure tests green; no product cutover yet.

## Phase 2 — Enriched Teaching Plan
Add continuity/title/state fields, planner schema/prompt, validation, hashing and review payload.
**Exit:** plan generates, approves and verifies exact hash.

## Phase 3 — SharedDocument contracts
Add SharedLessonDocument, SharedSection, TaskAnchor and hash/version rules.
**Exit:** serialization/hash/invalid-contract tests green.

## Phase 4 — Shared task convergence
Finalize task prompt/response/evaluation meaning before fork.
**Exit:** each supported action maps to valid shared task/passive semantics.

## Phase 5 — Section Composer
Closed section structure with deterministic validation.
**Exit:** diverse sections produce valid fixed shapes.

## Phase 6 — Parallel Section Writer
Generic section writer, dynamic exact output validation, bounded repair, durable section work items.
**Exit:** bounded parallel execution and sibling-preserving retry proven.

## Phase 7 — Continuity + document QA
Boundary validator, targeted repair, deterministic assembly, final QA/hash.
**Exit:** truthful ready SharedDocument.

## Phase 8 — Media integration
Concurrent required figure generation from validated figure semantics.
**Exit:** media readiness/failure behaviour proven.

## Phase 9 — Shadow SharedDocument
Generate on real lessons without replacing paths yet; inspect quality.
**Exit:** shadow quality/stability acceptable.

## Phase 10 — Learn cutover + deletion
Consume SharedDocument only, prove runtime/publish, route all new Learn, zero-call/delete old Learn ordinary authoring, add guards.
**Exit:** one Learn generation architecture.

## Phase 11 — Print cutover + deletion
Consume SharedDocument only, prove editor/PDF/answer key, zero-call/delete old Print ordinary authoring, add guards.
**Exit:** one Print generation architecture.

## Phase 12 — Runtime convergence + deletion
Move active product runs to generic runtime; delete superseded state/retry/checkpoint/worker logic.
**Exit:** one lifecycle vocabulary.

## Phase 13 — API/frontend convergence
Move UI/routes to new build/run status; delete obsolete status/adapters/routes.
**Exit:** current UI has no historical generation dependency.

## Phase 14 — Database cleanup
After proof/backups, drop obsolete schema/state.
**Exit:** DB reflects target architecture.

## Phase 15 — Full live quality proof
Complete 12-lesson / 20-run program.
**Exit:** quality report PASS.

## Phase 16 — Final convergence
Full zero-caller sweep, final deletions, full suite/build, guards, docs convergence, closeout.
**Exit:** one obvious current lesson-generation architecture.
