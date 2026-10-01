# Option D closeout: one job system for the whole lesson

Date: 2026-09-30. This closes items 3 and 4 from `36_DEFERRED_CONVERGENCE_REPORT.md`, built to the design in `37_OPTION_D_CONVERGENCE_DESIGN.md`.
**Result: DONE.** New lessons run end to end on the shared generation runtime. Old in-flight lessons get a clear "re-prepare / regenerate" state. Nothing was backfilled.

## What changed, in plain terms
| Before | Now |
|---|---|
| Plan generation was an in-memory background task inside the web server. A heartbeat patch caught crashes. Status lived in three places. | A **`preparation` Run** holds one work item per concept card plus a `teaching_plan` item. It is leased and retried per item (max 3), and its failures are typed. |
| Learn and Print each had their own polling worker with a home-made JSON lease. | A **`learn` / `print` Run** runs one `realize` item. It starts only once the lesson document is READY, so there is no busy-waiting. |
| Three status vocabularies (plan page, realization progress store, document runs). | **One:** `queued / running / awaiting_review / ready / failed_* / cancelled` + `recovery_action`. The pages read it from the lesson-status data only. |
| A lesson's jobs were unrelated rows. | **One build per lesson:** preparation → document → Learn → Print, all on the same `generation_builds` row. |
| The planner lived in the Print folder. | The planner lives in `application/unit_lesson/teaching_planner.py` and `teaching_plan_service.py`. A guard keeps it out of Print, and the curriculum layer stays free of Print imports. |

Unchanged by design:
- Teacher approval is still the hash-bound teaching-revision store.
- Documents, pack items, outputs and publish lineage stay where they were.
- The approved-source and hash guarantees are therefore untouched.

## Packages
| Pkg | Merge | Content |
|---|---|---|
| 4A | `e6ef0959` | `RealizationWorker`, the single status projection, `realization_retry`, migration 0049 (`native_realizations.generation_run_id`). Deleted the Learn worker and its fencing, and the Print output lease path. |
| 4B | `6bb00011` | Retired the realization progress routes and the visuals-retry route. Learn and Print pages derive their state from `workspace.learn/print`, including a Regenerate action. |
| 3A | `3d68d9a2` | Added the preparation Run, `PreparationWorker`, `/api/v1/preparations/{id}/plan[:regenerate]` and the `legacy_unsupported` state. Deleted the stage-2 task, the P12A heartbeat and reaper, the old retry path and worker, the boot sweep, the chunked event, start and regenerate routes, and the variant fan-out. |
| 3B | `08c21119` | Moved the plan page onto the new endpoints: progress text, Retry, Regenerate plan, re-prepare. Deleted the chunked approve and retry-native routes. |
| 3C | `f5275842` | Moved the planner out of the Print folder into the application layer. The first attempt, into curriculum, was abandoned because of the domain guard; no allowlist was added. |
| 3D | `bcaf6665` | Added `GET /api/v1/preparations/{id}/structure` and `document_revision` on the generation detail. Deleted `/v3/chunked/{id}/plan|status`, `native_status.py`, `native_retry.py` and `retry_preparation_run`. |
| Test hygiene | `d1126fa4` | Handoff unit tests no longer call the live semantic-QA provider. |

Also merged in this stretch: item 2 (`0fd95850`), which retired the old Learn LLM-authoring engine (-8.7k lines).

## Live proof
- **Learn/Print on runtime (Shadows `9df8aaf9`):** the document Run `53b6da28` reached READY. The `learn` and `print` Runs then ran on the same build, each READY on attempt 1.
- **Full chain on one build (Convection `a124fcb0`, freshly prepared over HTTP):**
  1. `:prepare`, then structural review.
  2. `/plan` started preparation Run `c9c3a741`.
  3. The card item was ready on attempt 1.
  4. `teaching_plan` failed recoverably twice (truncated DeepSeek JSON, then a planner-reviewer rejection) and was retried through the generic work-item route. It was ready on attempt 3.
  5. The status showed `awaiting_review(teaching_plan)`.
  6. The plan was approved with its hash binding. The first approve, sent with the wrong hash, was correctly refused.
  7. Build `b339daa8` ended with **preparation, shared_document, learn and print all READY**.

## Verification (final, main checkout at `bcaf6665`)
- Backend: `uv run pytest -q` 1916 passed / 5 skipped / 7 deselected (count lower than earlier runs because 3D deleted tests of removed code).
- Live smoke on restarted backend: `/api/v1/preparations/{id}/structure` 200; retired `/v3/chunked/{id}/status` 404; lesson-status shows preparation approved, Learn ready, Print ready.
- Frontend: `pnpm check` 0 errors (5 existing warnings); `pnpm test` 60 files / 257 tests.
- Domain guards: PASS.
- Database: migration 0049 applied on the dev Postgres, and a downgrade/upgrade round-trip succeeded. Backup: `.tmp/textbook_agent_db_pre_0049_20260929_202004.dump`.

## Deliberately kept
- `generation.status` / `chunked.stage` are still written by `save_teaching_plan` for approved-source and reuse readers. The UI no longer reads them, and a guard test enforces that.
- The stage-1 structural planner still runs synchronously in `:prepare`. It is out of Option D scope.
- PDF export is a synchronous download, not a job. `RunType.PDF` stays unused.
- `application/unit_lesson/native_pipeline.py` has shrunk to 178 lines of live ownership helpers.

## Follow-ups (not blockers)
1. **Planner quality:** the V2 Teaching Plan planner needed all 3 attempts on Convection. The failures were output truncation on DeepSeek and a reviewer rejection of a duplicated scenario. Worth a focused look at the planner's max output tokens and its prompt.
2. **Old queued Print requests:** two `legacy-rz-*` Print realizations from 2026-09-18 remain `queued` with no output row. The worker ignores them. Delete them or show them as legacy if they ever surface.
3. **Stale dev script:** `tools/run_native_e2e_fixture.py` status timeline now returns `[]`. Delete the script or rework it on runtime events.
4. **Legacy `generations.status` column:** after a Learn-path approval, the prep row keeps `awaiting_teaching_approval` (the approve route never rewrote it). The UI reads the projection, not this column; `try_reuse_existing_preparation` still does - review when touching reuse.
5. **Phase 0:** the user's own signed-in inspection is still pending.
