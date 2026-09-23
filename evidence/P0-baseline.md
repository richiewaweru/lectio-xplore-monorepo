# P0 baseline — topology, state, and protection

Date: 2026-09-22 (Africa/Nairobi)
Branch: `codex/generation-stability`
HEAD: `57177e66ce6b1d1e89c0e912b77212c7e138365b`

## Repository protection

Initial `git status --short --branch` was:

```text
## codex/generation-stability
 M .gitignore
?? docs/architecture/generation-reliability-diagnosis-2026-09-22.md
```

These pre-existing changes were preserved. P0 changed documentation only and did not touch product code, migrations, tests, `.gitignore`, or the diagnosis file. `git log -8 --oneline` and `git remote -v` were inspected. HEAD remains the assigned starting SHA. No database service was started and no local env files were read or changed.

No backend/frontend build SHA or build identity was found in the status/health surfaces inspected in this P0 code review. The local repository SHA is recorded above; deployment identity is unverified.

## Persisted and runtime state map

```text
Unit / PathVersion
  └─ PathLessonModel
       ├─ pack_id ──────────────────────────────┐
       └─ provenance (lesson + objective revision)│
                                                  ▼
                                    GenerationModel (preparation)
                                      ├─ status / error
                                      ├─ chunked_state_json
                                      │    ├─ teaching_plan
                                      │    ├─ teaching_review
                                      │    ├─ teaching_revisions[] (approved snapshot ledger)
                                      │    └─ stage/checkpoint metadata
                                      ├─ GenerationStepModel[] (append-only parts)
                                      └─ GenerationModel document/output data
                                                  │
                      ┌───────────────────────────┴────────────────────────────┐
                      ▼                                                        ▼
       NativeRealizationModel(path=learn)                       NativeRealizationModel(path=print)
       pinned plan id/revision/hash                            pinned plan id/revision/hash
       separate status/output_id                               separate status; currently output_id = prep id
       Learn output/editable lesson                            Print executes/reuses preparation generation
```

`GenerationModel` persists preparation/output generation status, errors, content, and chunked state. `PathLessonModel.pack_id` points at the preparation record; `LessonProvenanceModel` verifies lesson/objective linkage. `TeachingRevisionStore` persists draft and approved teaching snapshots inside chunked state (`teaching_revisions`), with `teaching_review.approved_revision` as the approval pointer. `NativeRealizationModel` stores path, plan ID/revision/hash, lifecycle status, realization revision, output ID, error summary, and preparation reference. `GenerationStepModel` stores append-only per-part generation artifacts. Shared checkpoint and lease primitives live under `infra.execution`; checkpoints carry compatibility keys and ready/failed/ambiguous states, while execution leases and `ResumeDecision` govern resume decisions. The realization DB row itself has no current-stage, attempt/max-attempt, or heartbeat fields; detailed progress is in generation/checkpoint state.

## Current teacher/UI state sources

- `GET /units/{unit_id}/path/lessons/{lesson_id}/status` (`curriculum/routes.py:get_path_lesson_status`) returns preparation `generation_id`, raw `generation_status`, raw chunked `workflow_stage` (or `stale`), lesson freshness/eligibility fields, and realization identity rows/compatibility fields. It does not normalize preparation into the complete product lifecycle proposed by the pack.
- `lesson-context.ts:preparationUiState` derives teacher preparation state from substrings of `workflow_stage`/`generation_status` (`fail`, `generat`, `pending`, `queued`, `running`, `prepar`, `ready`, `approved`, `complete`) plus output presence.
- `lesson-context.ts:lessonArtifactUi` reads per-path realization rows/IDs/output links, then maps realization strings to UI states. A missing realization maps to `not_created`; realization errors/status affect the separate Learn/Print UI.
- `plan/+page.svelte` reads `teaching_review` for review metadata and currently iterates that object to display instructional content. It does not render `teaching_plan` in that review block. Status logic also checks internal stage strings.
- Learn and Print workspace paths use prepared status plus path-specific realization ID/output/open link; Learn routes load realization-linked output when present. Print output identity presently resolves back to the preparation ID.

## Diagnosis-era changes present on this HEAD

Current source is not identical in all relevant respects to the earlier diagnosis:

- Present: `native_realizations` persist independent `learn`/`print` path identity and plan revision/hash; route projection returns realizations; retry code pins path and approved teaching identity; admission supports idempotency keys and payload conflicts.
- Present: `TeachingRevisionStore` stores revision snapshots, preserves prior approved snapshots as superseded, and can normalize a legacy approved plan into a stable ledger record. Both consumer handoffs call `accept_approved_teaching_revision`.
- Present: Learn consumes an approved plan and creates a Learn output/realization identity independently.
- Still present: Print admission (`realize_print_handoff.py`) sets both `pack_id` and `output_id` to `preparation_generation_id`; Print's realization is therefore not yet fully detached semantically from shared preparation/output identity.
- Still present: status API exposes raw worker status/stage and frontend preparation state infers product truth from stage substrings.
- Still present: Plan review block uses `teaching_review` as display content rather than rendering `teaching_plan`; this retains the diagnosis-era blank/misleading review risk when review contains only metadata.
- The observed deployed symptoms in the diagnosis are not independently reproducible from this source-only P0; deployment SHA remains unverified.

## Known confusing boundaries / risks for later phases

1. **Preparation vs realization state:** status API exposes generation-stage strings while frontend creates a product state, so contradictory underlying rows may be resolved differently by backend and UI.
2. **Print source vs output identity:** a Print realization row exists, but its output ID and pack link are set to the shared preparation ID; retry logic preserves this legacy/checkpoint pointer.
3. **Teaching content vs review metadata:** API has separate `teaching_plan` and `teaching_review`, but Plan page renders the latter as content. Approval affordance and displayed revision/content binding need focused review in P2.
4. **Approval side effect:** Print handoff calls `save_teaching_review(status="approved", queue=True, ...)` after accepting the approved revision. Determine in P2/P3 whether this mutates shared plan/review state in a way that conflicts with downstream immutability.
5. **Repair boundaries:** `AuthoringEngine` has bounded semantic repair and a provider wrapper; `document/writer.py` has post-authoring quality validation. Confirm in P5 whether quality failures re-enter the same durable work-item budget or create a separate correction/retry boundary.
6. **Runtime/deployment identity:** no active app SHA surfaced in the inspected paths; local SHA alone cannot establish production parity.

## Baseline tests

Commands were run before any P0 documentation changes:

```powershell
# From apps/textbook-agent/backend
uv run pytest tests/application/test_p03_realization_gates.py tests/curriculum/test_p02_shared_plan_gates.py tests/planning/test_native_retry_pre_worker.py tests/planning/test_phase02_queue_and_lease.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/routes/test_d6c_learn_runtime_chain.py tests/routes/test_learn_adversarial.py -q
```

Result: **117 passed**, 2 warnings, 85.74 s. Warnings: Pydantic field name `schema` shadows a BaseModel attribute; `AgentRunResult.usage` deprecation in a retry test.

```powershell
# From apps/textbook-agent/frontend
pnpm exec vitest run src/lib/curriculum/lessons/lesson-context.test.ts src/lib/curriculum/lessons/plan-status.test.ts
```

Result: **2 files passed, 9 tests passed**, 42.22 s. These existing tests establish behavior for the current local inference functions; they do not prove that backend projection is canonical.

## P0 gate judgment

**Evidence captured; request Sol review.** The repository topology and targeted regression baseline are sufficient to establish the P0 gate package. Do not mark P0 complete or begin P1 until Sol accepts the evidence. No architectural blocker is raised from the baseline; the known mismatches are exactly bounded by later execution-plan phases.

## Recommended bounded P1 task for Sol to consider

Add one backend-owned teacher-facing preparation + Learn + Print projection to the existing path lesson status response, retaining raw worker details only for debug compatibility. Define deterministic mappings from persisted preparation/realization records to the pack's preparation/artifact state vocabulary, with explicit missing/legacy ambiguity handling. Add backend projection tests for ready output vs active prep, failed realization vs sibling state, no realization, and path isolation. Keep P1 limited to backend projection and its contract/tests; have Sol review before the separate frontend-consumption phase. Preserve the Print identity finding for P3 rather than folding a Print redesign into this projection task.
