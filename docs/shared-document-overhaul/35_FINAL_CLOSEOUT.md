# Final Closeout — Shared Document Overhaul

## Repository
Branch: `codex/shared-document-overhaul`
Starting SHA (Claude takeover, 2026-09-27): `3d577b10`
Final SHA: see the last commit on the branch (this document is committed with it)
Date: 2026-09-29
Result: **PARTIAL.** The architecture converged for lesson content. Named deferrals are listed below; each has a current product reason.

Since the takeover: 79+ commits, 366 files changed, +23.0k / −36.9k lines.

## Canonical architecture

```text
Preparation → Enriched Teaching Plan → Approval → SharedLessonDocument → Learn / Print
```

- **Preparation / Teaching Plan.** The V2 planner and semantic reviewer run on DeepSeek with thinking. Approval is teacher-approved and hash-bound.
- **SharedLessonDocument.** One generic Run/WorkItem runtime (`infra/generation_runtime`, tables `generation_builds/runs/work_items/events`) runs these stages in order:
  1. sourcebook
  2. shared tasks
  3. compose:\*
  4. write:\*
  5. boundary:\*
  6. media:\* (Gemini)
  7. document QA
  8. finalization
- **Reviewer path.** A QA issue opens an immutable review draft. Edits are limited to an allowlist. Submit revalidates the exact edited revision, then promotes it to READY. The UI is at `units/[id]/lessons/[lessonId]/review`.
- **Learn and Print.** Both are deterministic adapters over a verified READY document, via `document/shared_lesson/realization_source.py`. There is no LLM authoring in either.

## Runtime convergence
- **Lesson content:** one status vocabulary (`queued/running/ready/failed_recoverable/failed_terminal/cancelled` + `recovery_action`), one work-item mechanism, leases and fencing, bounded attempts (max 3), typed failure codes, and durable events.
  - Source and output hashes are verified at every boundary.
  - Auto-retry covers provider failures.
- **Preparation pipeline (P12A):** a crash-safety heartbeat plus an orphan reaper. It is not yet on `generation_runs` (deferred, see below).
- **Learn/Print realization rows:** still `native_realizations` + `progress_routes` (deferred, see below).

## Deleted old architecture

| Subsystem | Evidence | Commit |
|---|---|---|
| Ordinary Learn authoring (native_execution, document_realizer, compose/write loop, interaction selection) | rg zero-caller + P10E guard | `65fb197d` / merge `b0abb042` |
| Standalone Print + ordinary Print authoring (composition_bridge, whole-lesson executor/form planner, dual_native, …) | rg zero-caller + P11B guard | `5648c52a`, `45ba01c7` / merge `3bee49d0` |
| Whole-lesson `writing_sections/writing_blocks` lifecycle, `/retry-section` | unreachable transitions + P12B guard | `6c76ed32` |
| Learn units `generation*` routes, `application/builder_print`, `core/routes/shares.py`, dead frontend pack/ai-client | FE/BE rg + ASGI-level P13C guard | `f2005baf`, `ff0fac68` |
| `lesson_shares`, `unit_capability_declarations` tables; dead `src/core/database/migrations` tree | no ORM/code readers; migration `20260929_0048` (up/down/up verified); pg_dump backup first | `916c655e` |
| 50+ unreachable backend modules and shims, `document.composer` + its prompt | static import-graph reachability from `app` + P16 guard | `32261dd2` |

## Tests
`scripts/verify-phase.ps1 -Phase full` **PASS** (exit 0) at `32261dd2`, 2026-09-29.
- **Backend:** 2037 passed, 5 skipped, 8 deselected, 0 failed (34m12s).
- **Frontend:** svelte-check 0 errors (5 pre-existing warnings); vitest 59 files / 246 tests passed; build PASS.
- **Build/check:** page package 11 files / 64 tests passed; page check 0 errors / 0 warnings; PDF fixtures 6/6/5/5/5 pages; `git diff --check` PASS.
- **DB migrations:** single head `20260929_0048`; upgrade → downgrade → upgrade verified on dev.
- **Failure injection:** media provider failure, boundary exhaustion, lease loss/expiry reclaim, orphaned pipeline reaper, stale hash, and retry of a terminal Run are all covered by focused tests.
- **Architecture guards:**
  - Phase guards: P10E, P11B, P12B, P13C, P16.
  - v3 retirement guards.
  - `check_architecture.py` and `pnpm program:domain-guards`.

## Live proof
- **Unique lessons:** 12/12 human quality PASS across 6 archetypes (Phase 9).
- **Repeated generations:** 8/8 READY (4 clean, 4 reviewer-fixed).
- **Stability rule:** closed at ≥80% stability per the user's rule; the last batch was 6/6 READY.
- **Final-code check (P16, 2026-09-29):**
  - Water Cycle fresh Run READY.
  - Fable document READY → Learn READY → Print READY. The Print output has 5 sections, question blocks, an answer key and a hosted figure.
  - Shadows was QA-flagged into review. Its defect is inside a generated task prompt, which the reviewer allowlist cannot edit (see deferred item 4).
- **Two bugs found and fixed by the check:**
  - The Learn worker busy-looped on runs waiting for their document (`b7d2cbb2`).
  - Print rejected produced images that carried a quality warning (`05992a7e`).
- **Major defects open:** none in the generation path.

## Learn
- **SharedDocument hash:** pinned on the realization, the output, the editable lesson and the release. Verified at publish (P10C).
- **Learn output:** a deterministic adapter; TaskAnchors map to Learn interactions.
- **Publish:** lineage verification against the pinned document hash.
- **Retry proof:** `retry_learn_realization`; runs waiting on their document no longer starve the worker.

## Print
- **SharedDocument hash:** pinned on the realization and the output; the adapter re-verifies it.
- **Print output:** a deterministic adapter covering treatments, figures and tables.
- **Answer key:** proven equal to the shared task evaluations (P11).
- **PDF:** v3 studio export; the fixture PDF gate is part of the full verification.
- **Retry proof:** `retry_print_realization` (exercised live on the Fable lesson).

## Remaining historical adapters/names

| Item | Current product reason |
|---|---|
| `print/http/v3_studio` chunked plan/status/approve endpoints + `application/unit_lesson/native_pipeline.py` | The live Preparation/Teaching-Plan pipeline used by the plan page. Migrating it onto `generation_runs` is deferred (1–2 weeks, needs a DB migration). Crash-safe via P12A. |
| `native_realizations` + `progress_routes` + `learn/generation/fencing.py` + whole-lesson `worker/repository/states` | The live Learn/Print realization job rows and status. They are thin now, because realization is a deterministic adapter. Convergence onto `generation_runs` is deferred with the item above. |
| `v3_blueprint` / `v3_execution` package names (compiler, models, booklet_status, prompts.formatting) | Still imported by the live prep pipeline; they are named by history. |
| Learn LLM-authoring engine: `learn/generation/interaction_writer` write path, `work_orders.compile_learn_work_orders`, `document.writer` (+ `document-writer` prompt), `preparation_context`, `reliability_persist`, `learn.interactions.action_map`, `v3_execution.llm_helpers` | Zero production callers, but about 6 policy test files use them as a regression harness. Decision pending: retire the engine, or keep it for Builder teacher-editing. |
| `core.{auth,health,llm,storage}` alias shims | Still imported under the `core.*` path by live code. |

## Engineer test
Can current generation be explained without V1/V2/V3 history?
**PARTIAL.** Lesson *content* can: one SharedLessonDocument runtime with deterministic Learn/Print. The *preparation* step and realization job rows still carry v3/native naming and their own lifecycle; see the table above.
