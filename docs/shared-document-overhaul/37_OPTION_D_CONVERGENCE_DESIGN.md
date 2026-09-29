# Option D: plan generation and Learn/Print jobs on the shared job system

Status: **implemented** (closeout: `38_OPTION_D_CLOSEOUT.md`); originally design, approved scope (2026-09-29). This implements items 3 and 4 from `36_DEFERRED_CONVERGENCE_REPORT.md`.
Scope decision (user): **new lessons only.** Nothing is backfilled or dual-run. Old in-flight lessons get a clear "re-prepare / regenerate" state.
Order: **item 4 (Learn/Print jobs) first, then item 3 (plan generation).**

## 0. Principles
1. **One job system.** Every step that runs in the background is a `generation_runs` Run with `generation_work_items`, leased, attempt-bounded (max 3) and typed-failure. There are no bespoke JSON leases, in-memory task registries, heartbeat reapers or progress stores.
2. **Change who runs the steps, not where results live.** The outputs keep their current storage: `page_document_v2` teaching revisions, `pack_items`, output `generations` rows, `editable_lessons` and `native_realizations` identity. As a result, `approved_source.py`, the hash-bound approval, publish lineage and the adapters stay unchanged. No data migration is needed.
3. **Product records are not job trackers.** `native_realizations` (what the teacher asked for) and the teaching revision store (what the teacher approved) remain product records. Their *status* becomes a projection of the Run. It is written in one place only.
4. **Teacher approval is not a job.** A Run finishes when its work is done. Waiting for a teacher is a durable product state: `teaching_review.status = pending` in the revision store, which is already hash-bound. The runtime needs no "paused Run" semantics.
5. **One status vocabulary to the UI:**
   - `status`: `queued / running / awaiting_review / ready / failed_recoverable / failed_terminal / cancelled`
   - `recovery_action`: `retry / review / regenerate / none`
   - `run_id`

## 1. Item 4: Learn/Print realization Runs

### Run layout
| | Learn | Print |
|---|---|---|
| `run_type` | `learn` | `print` |
| build | the shared-document Run's `build_id`, so the lesson has one timeline | same |
| source identity | the READY SharedLessonDocument: `source_artifact_type="shared_lesson_document"`, id, revision, content hash (exactly the doc Run's output identity) | same |
| `request_key` | `learn-realization:{realization_id}:{realization_revision}` | `print-realization:{realization_id}:{realization_revision}` |
| work items | `learn:realize` | `print:realize`. Figure media is already produced by the document Run. There is no separate `print:visuals` item. |
| output artifact (finalize) | output `generations` row: `artifact_type="learn_output"`, id = `output_id`, revision = `realization_revision`, `output_json` = `document_json` | `artifact_type="print_output"`, same pattern |

### Flow
1. **Admission is unchanged** (`realize_learn_from_preparation` / `realize_print_from_preparation`).
   - It still creates the realization row, calls `ensure_shared_document_run` and creates the output `generations` row.
   - Remove the bespoke lease keys (`learn_execution`, Print `execution` lease/worker fields).
   - New column `native_realizations.generation_run_id` (nullable, FK `generation_runs.id`, migration `0049`).
2. **Dispatch** is done by one `RealizationWorker` (new `application/unit_lesson/realization_worker.py`) on the shared runtime. Each tick:
   - It scans `native_realizations` where `status='queued' AND generation_run_id IS NULL` (bounded, oldest first). It loads the shared doc Run via `load_realization_source`.
   - If the doc is READY, it admits the learn/print Run plus its one work item and stores `generation_run_id`. Admission is idempotent through `request_key`.
   - If the doc is not READY, it only projects: doc awaiting review becomes `needs_shared_review`, doc failed becomes the realization's failed state. It does not take a lease and never busy-loops.
   - It claims eligible `learn:realize` / `print:realize` items via `claim_work_item` (queued, or running with an expired lease).
3. **Execute** by calling the existing deterministic adapters, stripped of their own state machines:
   - `realize_shared_document_for_learn`: writes the output doc and `editable_lessons`.
   - `execute_print_realization_from_shared_document`: writes the output doc.
   - Then `complete_work_item` (output = `{output_id, document_hash}`), `finalize_run` (source verifier = doc still READY with the same hash; artifact loader = output row), and project `realization.status = ready`.
4. **Failure** calls `fail_work_item` with a typed failure. Adapter contract errors are `validation` and terminal. DB/transport errors are retryable. The realization status is projected from the Run.
5. **Retry** keeps the existing product route `POST .../realizations/{rid}:retry`:
   - If the Run is `failed_recoverable`, it calls `retry_work_items`.
   - If the Run is `failed_terminal` or `cancelled`, it bumps `realization_revision`. That produces a new output row and a new Run attempt, which is today's CAS behaviour.
   - It is bounded by the runtime attempts plus the existing revision CAS.

### Status projection (single function `project_realization_status`)
| Shared doc Run | Realization Run | `native_realizations.status` | UI (`workspace.learn/print`) |
|---|---|---|---|
| queued / running | none | `queued` | `queued` "waiting for document" |
| failed_recoverable + review | none | `needs_shared_review` | `needs_review` → /review |
| failed_* (other) / cancelled | none | `failed_recoverable` | failed; action from doc Run (`retry`/`regenerate`) |
| ready | queued / running | `queued` / `running` | same |
| ready | ready | `ready` | ready (`output_id`) |
| ready | failed_recoverable | `failed_recoverable` | retry |
| ready | failed_terminal | `failed` | regenerate |
| (any) | stale marking (prep regenerated / plan changed) | `stale` | unchanged behaviour |

### Deleted in item 4
- `learn/generation/worker.py` and `learn/generation/fencing.py` (and their startup wiring).
- The Print output lifecycle in `print/generation/whole_lesson/worker.py`, including `claim_next_native_job` for Print outputs. **Keep the pre-worker preparation retry path until item 3.**
- `_apply_non_ready_print_shared_document_state` and `_sync_print_realization_status` side effects.
- Unused visuals: `awaiting_visuals`, `reopen_flagged_visuals`, `POST /visuals/retry`, and `retryNativeVisuals`.
- `progress_routes.py` realization status/events/stream plus the `ProgressStore` realization sync (it was wrong-id and 404-swallowed).
- Frontend `reliability.ts` / `unit-workspace.svelte.ts:271-289` calls into it. `path-job-state.ts` reads `allowed_actions` from the lesson-status DTO instead.
- `stale_learn` startup sweep and `legacy_prep_link` skip.

### Legacy (no backfill)
- A realization with `generation_run_id IS NULL` and `status` not in `{ready, stale, read_only}` is treated as legacy after deploy.
  - The projection shows `failed_terminal` with `recovery_action=regenerate` and the safe summary "Created before the job update: regenerate this output."
  - Retry creates a new revision on the new path.
- READY outputs keep working. They are only read.

### Kept as is
- PDF export stays a synchronous download endpoint (not a job). `RunType.PDF` stays unused.
- Publish lineage is unchanged.

## 2. Item 3: Preparation Runs (plan generation)

### Scope boundary
- Stage 1 (structural planner, synchronous in `:prepare`) and the structural review stay as they are.
- The Run starts where the background task starts today: when the teacher approves the structure (today `POST /v3/chunked/{id}/approve`).

### Run layout
| Field | Value |
|---|---|
| `run_type` | `preparation` |
| build | a new `generation_builds` row for the path lesson. It is reused by the document and realization Runs of this preparation, so there is one timeline. |
| source identity | `source_artifact_type="lesson_structural_plan"`, id = prep generation id, revision = `lesson_provenance.path_lesson_revision`, hash = canonical hash of `{structural_plan, context, planning_spec_json, objective_hash}`. The verifier recomputes it and requires valid, un-invalidated provenance. |
| `request_key` | `preparation:{generation_id}:{source_hash}[:attempt-N]` (bounded at 3 like documents) |
| work items | `items:{concept_card_id}`, one per card (independent retry; replaces `_items_job`). Then `teaching_plan` (planner + semantic reviewer, bounded 2 internal attempts as today), admitted by the worker once every `items:*` item is ready. |
| output artifact (finalize) | the draft teaching revision: `artifact_type="teaching_plan_revision"`, id = `teaching_plan_id`, revision = N, `output_json` = the revision's plan, hash = canonical. The loader reads `page_document_v2.teaching_revisions[N]`. |

### Flow
1. `POST /api/v1/preparations/{generation_id}/plan` (replaces `/v3/chunked/{id}/approve`):
   - Checks ownership and that the stage is structural-approved.
   - Creates the build, admits the Run and the `items:*` items, and returns `{run_id, status}`.
   - It is idempotent.
2. `PreparationWorker` (new `application/unit_lesson/preparation_worker.py`), written in the same style as `SharedDocumentWorker`:
   - It claims `items:*`, runs `execute_items_with_diagnostics` for that one card, writes `pack_items` (same `_write_pack_item_rows` rules), and completes the item.
   - When all items are ready, it admits `teaching_plan`.
   - `teaching_plan` runs `run_and_persist_teaching_plan` unchanged. It writes `page_document_v2` and the revision with `teaching_review.status = pending`.
   - It completes the item and finalizes the Run to `ready`.
3. **Teacher approval / reject** stay on the existing hash-bound routes (`lesson-approach/approve|reject`, `save_teaching_review`). No Run is involved.
   - "Awaiting approval" in the UI is `run ready ∧ teaching_review.status == pending`.
   - After approval, the existing flow runs: `ensure_shared_document_run` on the same build.
4. **Retry** uses the generic runtime routes:
   - `POST /api/v1/generation/work-items/{id}/retry` retries one card.
   - `POST /api/v1/generation/runs/{id}/retry` retries the failed leaves.
   - Terminal failure: "Regenerate plan" admits `attempt-N` (bounded at 3).
5. **Reject** sets `teaching_review` rejected, as today. "Regenerate plan" then admits a new attempt Run.

### Status projection (lesson-status `workspace.preparation`)
| Condition | UI state |
|---|---|
| No Run and stage 1 awaiting structure review | `awaiting_review` (structural), as today |
| Run queued / running | `planning` (+ per-card progress from work items) |
| Run failed_recoverable | `failed_recoverable`, `retryable=true`, `run_id` |
| Run failed_terminal | `failed_terminal`, action `regenerate` |
| Run ready ∧ review pending | `awaiting_review` (teaching_plan) |
| review approved | `approved` |
| **Legacy:** prep row whose plan is not approved and has no preparation Run | `legacy_unsupported`: "Prepared before the planning update: re-prepare this lesson." The action is `:regenerate`, the existing stage-1 regenerate route. |

Already-approved old lessons keep working: everything downstream reads only the approved revision store.

### Deleted in item 3
- `_run_chunked_stage2_pipeline`, `_items_job`, the `asyncio.create_task` launch and `_chunked_stage2_tasks`.
- The in-memory `/chunked/{id}/events` SSE and the dead `/chunked/plan/start` and `/chunked/{id}/regenerate`.
- The P12A heartbeat, reaper loop and `prep_pipeline_*` settings. `PIPELINE_ORPHANED` remains only if still referenced.
- `native_retry.py` pre-worker retry, the rest of `NativeExecutionWorker` and `claim_next_native_job`.
- The `fail_stale_running` boot sweep for prep rows.
- `/v3/chunked/{id}/status|plan` and `native_status.project_native_status` once the plan page reads lesson-status.
- Frontend: `approveChunkedPlan`, `regenerateChunkedPlan`, the `plan-status.ts` legacy stage list and `LEGACY_PREPARATION_STAGES`.
- **Move** the planner out of the Print folder: `print/generation/whole_lesson/{teaching_agent,service}.py` → `curriculum/teaching_plan/`. Tests follow the move, and a guard forbids the old paths.

### Kept on purpose
- `generation.status` / `chunked.stage` are still written by `save_teaching_plan` for the approved-source and reuse readers. They are **no longer read for UI status**.
- A guard test asserts that no UI projection reads them.

## 3. Work packages (Sonnet workers; Sol reviews and merges each)
| Pkg | Content | Depends on |
|---|---|---|
| **4A** | Migration 0049, `RealizationWorker`, admission lease-key removal, projection function, retry route rewiring, legacy projection, deletion of the Learn worker/fencing and the Print output worker path, and app wiring. Tests: dispatch waits without busy loop, doc review, READY → ready, typed failure → retry, terminal → new revision, legacy projection, idempotent admission. | item 2 merged |
| **4B** | Deletion of `progress_routes` / `ProgressStore` realization sync, the visuals retry path and the frontend `reliability.ts` / wrong-id calls. Learn/Print pages read `workspace.learn/print` only. Frontend tests. | 4A |
| **3A** | Preparation Run: source/artifact adapters, `PreparationWorker`, the new plan endpoint, projection including `legacy_unsupported`, and deletion of the stage-2 task, heartbeat/reaper, pre-worker retry and boot sweep. Tests: per-card retry, teaching_plan admitted only after items, finalize → awaiting approval, restart-safety (expired lease reclaimed), bounded attempts, legacy state. | 4A |
| **3B** | Plan page on the lesson-status + runtime retry routes. Delete the chunked API client and legacy stage maps. Frontend tests. | 3A |
| **3C** | Move the planner out of the Print folder and add a guard. | 3A |

Every package must:
- Base on `origin/codex/shared-document-overhaul` and preserve mixed line endings.
- Pass `uv run pytest -q`, `ruff check` and `pnpm -C apps/textbook-agent/frontend check && test`.
- Record a runbook entry.

**Live proof after 4A+4B:** a fresh lesson goes through Learn and Print to READY, with realization Runs visible in `/api/v1/generation/builds/{id}`.
**Live proof after 3A+3B:** prepare → plan Run → per-card items → approve → document → Learn/Print, all on one build.
