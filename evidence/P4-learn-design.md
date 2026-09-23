# P4 Learn lifecycle design checkpoint

Status: read-only proposal for Sol review. No product code was changed for P4.

## Current paths and findings

- Unit Create calls `POST /api/v1/v3/generations/{preparation_id}/realize-learn` when a preparation exists, or the Unit `realizations:generate-learn` route otherwise. Both enter `realize_learn_from_preparation`; the handoff verifies the approved Teaching Plan and then waits for `produce_learn_from_approved_teaching` to finish before returning `status: ready`.
- The Learn producer already admits a `NativeRealizationModel`, creates a separate `GenerationModel` output, claims an output-scoped Learn lease, persists call budgets/checkpoints/heartbeat, fences output writes, creates an `EditableLessonModel` tied to the output, and links the realization to that output. This is reusable content execution, but it currently runs in the request.
- Unit retry currently rotates the realization/output via generic `retry_realization` and then calls the synchronous handoff. Generic retry has no failed-only guard, no source/realization lock, and Create can implicitly rotate failed output. This conflates duplicate Create with explicit retry.
- Studio's `realize-learn` route also runs synchronously. `realize_learn_from_preparation` requires a resolvable `PathLesson`; a pathless Studio generation cannot have a `NativeRealizationModel` under the current foreign-key schema. Existing Builder opening is owner-checked by generation ID. The Unit Learn page already refreshes the path lesson and can open a native output by its ID, but currently awaits the Create/Retry POST before refresh.
- `get_path_lesson_status` already resolves Learn and Print rows independently and projects each through the canonical workspace DTO. The projection understands `queued`, `running`, `ready`, and failures; `NativeRealizationModel` already contains path, pinned plan identity, status, output ID, revision, and an error summary. The DTO's typed error is currently synthesized generically; Learn's detailed failure state remains in the output generation's JSON and is not consistently surfaced by workspace status.
- `claim_learn_execution` and heartbeat/fencing already provide output-scoped leases. `fail_stale_learn_executions` changes abandoned running attempts to recoverable failure after lease expiry. `units_dispatch_task` is not a durable Learn dispatcher; it rejects the retired component path. Print has a durable DB-polled worker and app-lifespan startup that provide a nearby operational pattern.

## Proposed smallest durable flow

1. **Admit and return.** The owner-checked Unit route validates Unit/path version/lesson revisions, locks the source preparation and relevant Learn realization identity, loads the immutable approved revision by its pinned revision/hash, and verifies it. In one transaction, a first Create admits/reuses the path=`learn` realization and creates a distinct queued Learn `GenerationModel` output seeded with `native_learn`, `preparation_generation_id`, and exact Teaching Plan ID/revision/hash. It commits before any model call and returns `202` with `realization_id`, `output_id`, realization revision, pinned Teaching Plan identity, and canonical queued status. Duplicate Create returns the existing queued/running/ready identity; it never rotates a failed output or starts a second attempt. Reuse of an idempotency key with a different plan hash returns typed 409.

2. **Claim and execute.** Add a Learn-owned DB-polling worker started/stopped through app lifespan (not an in-memory task queue). It selects only `NativeRealizationModel.path == 'learn'` and queued rows, locks with `FOR UPDATE SKIP LOCKED` or a conditional claim, then verifies source ownership, row/output identity, and the exact immutable approved snapshot again before entering provider work. It marks the run running and uses the existing output-generation lease, heartbeat, checkpoint, budget, and fenced persistence machinery. Extract/reuse Learn document production as an executor that receives the pinned realization/output identity; it must not re-admit, rotate output IDs, or run for Print rows.

3. **Complete or park failure.** Success writes the validated document to the Learn output generation, creates/retains the owner-bound editable lesson whose `source_generation_id` is that output, and in the same completion boundary sets the realization ready with that same `output_id`. Failure persists typed `code`, `error_type`, `failure_class`, `retryable`, `stage`, `work_item_id`, and `attempt` on the output run (existing generation JSON can carry this without a realization-table migration); `NativeRealizationModel.error_summary` remains the concise compatibility message. The row becomes `failed_recoverable` or `failed_terminal`; worker failure never changes teaching approval or Print state.

4. **Read/refresh.** Unit refresh reads `get_path_lesson_status`; the Learn workspace row is authoritative for product state and points to the Learn output. The page renders queued/running progress, opens the owner-checked Builder lesson only when ready, and stops polling on ready or failure. It does not infer readiness from output-ID presence. Direct native Builder opening continues to verify output generation ownership.

5. **Explicit retry.** The retry endpoint locks and re-reads the owned path lesson and Learn realization. It only retries `failed_recoverable`; stale, hashless, mismatched, terminal, read-only, or ambiguous rows return typed conflict/reprepare guidance. It verifies the existing pinned approved snapshot without requiring the current pointer to remain on that revision, then increments `realization_revision` once, allocates a fresh Learn output generation, and atomically sets queued. The prior failed output remains readable. Duplicate concurrent retries re-read after lock and return the winning queued/running identity (or typed 409), never allocate a second output. Teaching review revision and Print realization are untouched.

## State and compatibility rules

| Persisted Learn realization | Teacher-facing Learn workspace | Action |
|---|---|---|
| no path=`learn` row | `not_created` | Create |
| `queued` with matching queued output | `queued` | Poll |
| `running` with live output lease | `running` | Poll |
| `ready` with owner-matched output, document, and editable lesson linked to that output | `ready` | Open output |
| `failed_recoverable` | `failed_recoverable` plus typed error | Explicit Retry |
| `failed_terminal` | `failed_terminal` plus typed error | Reprepare/review or support path; no retry |
| `stale`, `read_only`, legacy ambiguous, or broken output/pinned identity | fail closed as recoverable only when an explicit reprepare action is valid; otherwise `failed_terminal` with identity/reprepare error | Preserve any already-delivered owner-checked output read access; never execute ambiguous rows |

Learn and Print keep separate realization IDs, output IDs, status, and failure records. A queued/running/failed Learn run cannot update the Print row or its detached output, and vice versa. The source preparation retains immutable approval; downstream failure cannot change review state. Shared semantic artifacts remain content-hash pinned; P4 should avoid treating source preparation worker fields as a Learn run or allowing concurrent path completion to overwrite sibling status.

For legacy data, completed Learn outputs remain readable through their owner-checked Builder record. A historical row can be executed or retried only if its path, source, pinned revision, stored content hash, and output ownership verify; otherwise it stays read-only/ambiguous and requires reprepare. A pathless Studio Learn request has no legal `NativeRealizationModel` under the current schema; recommended bounded behavior is a typed conflict directing the user to the owning Unit lesson, while preserving any existing standalone Builder outputs. Sol should decide if standalone Studio Learn generation is a required compatibility contract before implementation.

## P4 paths to reuse vs change

Reuse: `NativeRealizationModel`; canonical workspace projection and per-path status resolution; `GenerationModel` Learn output and `EditableLessonModel`; existing Learn producer, content hash checks, call budget/checkpoint/progress stores, output-scoped lease/fencing, stale-lease reconciliation, and owner-checked native Builder open.

Change: separate a prompt-returning Learn admission service from execution; add a durable Learn worker/claim path and app lifespan hook; extract the current in-request producer orchestration to execute a pinned queued row; make Create idempotent without implicit retry; give Learn explicit locked/failed-only/new-output retry semantics parallel to detached Print; expose typed error details from the output run in workspace status; and update Units/Studio callers to consume queued identity and poll backend state rather than expect a synchronous ready response.

## Focused P4 gate tests

1. Duplicate Create while queued/running/ready returns the same realization/output IDs and creates no orphan; duplicate request key with changed content hash returns typed 409.
2. Learn starts queued, worker moves it running then ready; output document and editable lesson are linked to the same `output_id`; ready output is never projected as queued/preparing.
3. Inject a recoverable provider failure; status exposes typed error and stays parked without model calls until explicit retry.
4. Explicit retry after recoverable failure creates one new output, increments realization revision once, preserves prior output and approved Teaching Plan revision, and does not mutate Print. Concurrent retry admits exactly one output.
5. Learn failure with Print ready, Print failure with Learn ready, Learn running with Print ready, and Print running with Learn ready preserve distinct states and IDs.
6. Refresh after queued/running/ready/failure reconstructs the same backend state and routes to the owner-checked Learn output; another owner cannot read/open it.
7. Missing/hashless/mismatched approval, ambiguous legacy identity, wrong output owner, mismatched output metadata, or corrupt path identity fails closed before provider work; existing verified ready legacy output remains readable.
8. Lease-expired worker reconciliation changes Learn running to `failed_recoverable`; it does not auto-requeue and does not touch Print or approved teaching state.

Commands should include the focused Learn handoff/native execution/fencing and `tests/application/test_p03_realization_gates.py` tests, curriculum path status/retry route tests, relevant Builder owner/read tests, plus Ruff, architecture validation, focused frontend Learn/lesson-context tests, `npm run check`, and `npm run build` after implementation scope is approved.
