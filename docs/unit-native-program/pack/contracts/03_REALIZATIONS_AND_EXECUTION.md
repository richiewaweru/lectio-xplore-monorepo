# Native realizations and execution

## Identity
Prepared lesson and teaching plan are shared. Each output realization is native.
Proposed fields: realization_id, path(print|learn), teaching_plan_id/revision/hash, variant_id, native_policy_version/hash, package_contract_version/hash, realization_revision, status, output_id, error_summary.
Creation idempotency includes shared revision, path, variant and policy/contracts. Same lesson can have Print and Learn simultaneously.
Keep old pack_id for legacy links as necessary; do not make it the authoritative discriminator for both outputs. Backfill only unambiguous records. Mark ambiguous legacy records read-only with explicit regeneration rather than guessing.
Reuse resolves exact identity. Changing native policy invalidates only that native realization; changing shared teaching marks dependent realizations stale but preserves their snapshots.

## Stage states
Shared: preparing → awaiting_instructional_review → teaching_ready, with failed_recoverable/failed_terminal as explicit alternatives.
Native: queued → selecting → writing → validating → assembling → ready; Print may include awaiting_assets/exporting and Learn editing/published as separate artifact lifecycle.
Map to existing states rather than create competing status engines. Persist path identity and reuse it for workers, status, retries and reload; never infer from environment defaults after admission.
Publish is explicit; generation completion does not publish silently.

## Native planning
Eligibility = package compatibility ∩ native policy ∩ planned intent/action ∩ available assets ∩ supported writer/runtime ∩ remaining budgets.
Default target: a few suitable candidates; no arbitrary truncation that removes the only valid candidate. Deterministic projections omit unrelated options. Validate choices against the EXACT candidate snapshot supplied to the model.
Print selector adds form/placement. Learn selector adds content/interaction decisions, preserving teaching order and dependencies.
Optional interaction may be none. Required unsupported action returns NO_COMPATIBLE_CAPABILITY with source block, constraints and reason. Bounded reconsideration may produce another legal subset, not widen silently.

## Writing and assembling
Reuse existing exact work orders. Carry block ID, teaching revision/hash, capability contract hash, source refs, expected output schema and dependency IDs.
Content/activity/visual writers receive only their relevant contract. Technical fields are backend-owned. Parallelize only independent work; image-dependent tasks wait for a validated asset and region definition.
Native assembler is deterministic. Every required block appears once; no missing/dangling/duplicate refs, repeated component types preserved, no reordering through section-field collapse.
Student and teacher payload views separate answers/feedback visibility from authoring data. Student client need not receive authoritative graded answer data before allowed feedback.

## Retry and invalidation
Transient provider failures: bounded exponential backoff with jitter, timeout and retry budget.
Schema failure: bounded scoped repair with exact validation errors and the same schema.
Semantic/source mismatch: explicit validation failure; never make an answer fit by changing the objective.
Missing dependency: retry dependency, then invalidate dependent results only.
Stale plan/lease: reject write, do not overwrite current revision.
Exhaustion: persist terminal reason and actionable retry/review state.
Use existing worker leases/checkpoints where valid. Successful siblings and teacher edits survive. Repeated requests are idempotent; crash/restart resumes from persisted state.

## Trace
Persist stage input/output references, source hashes, provider/model configuration, prompt version/hash, latency, token counts if available, attempts, validation errors and final decisions. Do not log credentials or learner-sensitive payloads in unrestricted logs.
A phase test must prove error attribution to preparation/teaching/selection/writing/assembly/rendering rather than one generic generation failure.
