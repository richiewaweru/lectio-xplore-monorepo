# P1 evidence — canonical lesson workspace state

Date: 2026-09-22 (Africa/Nairobi)
Branch: `codex/generation-stability
Repository HEAD: `57177e66ce6b1d1e89c0e912b77212c7e138365b` (no commit created)
Gate: Implementation and targeted validation complete; **Sol review pending**.

## Contract added

The existing path lesson status response now includes `workspace` with three independent projections:

- `preparation.state`: `not_started`, `planning`, `awaiting_review`, `approved`, `failed_recoverable`, or `failed_terminal`. Review states carry `review_kind` (`structural` or `teaching_plan`). A verifiable approved preparation carries generation and Teaching Plan identity, approved revision, verification flag, and staleness.
- `learn.state` and `print.state`: each independently uses `not_created`, `queued`, `running`, `ready`, `failed_recoverable`, or `failed_terminal`, and carries only its own realization/output/open-link identity and typed error details where persisted.
- `workspace.legacy_ambiguities` identifies cases where persisted identity cannot safely be assigned.

Existing raw `generation_status` and `workflow_stage` fields remain in the response for compatibility and are marked deprecated in the schema. `worker_debug` identifies them as debugging/progress data. They are not the teacher-facing workspace contract.

## Projection precedence and missing data

1. A verified approved snapshot requires persisted `teaching_revisions`, a review `approved_revision` pointer, an approved revision record at that number, and a valid plan whose revision and ID match the record. `TeachingRevisionStore`'s synthesized legacy approval is not accepted as proof of an immutable persisted snapshot.
2. A verified approval with current review status `approved` remains approved when the preparation worker later reports failure or a Learn/Print realization fails. `stale` is carried separately.
3. A structurally valid current pending Teaching Plan reports `awaiting_review`; an older verified approved snapshot remains exposed separately. Invalid/mismatched pending state is a terminal integrity ambiguity instead of a polling state.
4. Explicit preparation failure wins over a stale active worker stage, after verified approval or valid current Teaching Plan review have been considered. Structural gates with `awaiting_review` and a persisted structural plan map to `awaiting_review`, not failure.
5. Artifact state is derived from its own realization row. Missing rows are `not_created`. A failed row remains failed even with an output pointer. A ready-like status is ready only with an output ID. Print cannot populate Learn and vice versa.
6. Legacy realization rows whose path cannot be verified are reported as ambiguous and assigned to neither path. Completed preparation without verifiable approval fails closed. Missing/unknown state does not get guessed into approval or readiness.
7. Typed error metadata is carried when persisted (`code`, `error_type`, `failure_class`, `message`, `retryable`, `stage`, `work_item_id`, `attempt`). Some legacy realization rows only persist `error_summary`, so missing typed fields remain null.

The route uses the persisted `page_document_v2` teaching ledger from the loaded chunked-state wrapper. It does not import Print-layer code into curriculum. The wrapper's outer stage remains worker progress/debug input. `preparation_hash` is not exposed as a content hash; hash semantics are deferred to P2 per review direction.

## Tests and tooling

All commands below were run from `apps/textbook-agent/backend`.

Focused projection and exact status response contract:

```powershell
uv run pytest tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py::test_unprepared_lesson_status_is_explicit_over_http -q


Result: **20 passed, 1 warning in 31.65 s**.

Combined focused projection/route and targeted P0 regression suite:

```powershell
uv run pytest tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py::test_unprepared_lesson_status_is_explicit_over_http tests/application/test_p03_realization_gates.py tests/curriculum/test_p02_shared_plan_gates.py tests/planning/test_native_retry_pre_worker.py tests/planning/test_phase02_queue_and_lease.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/routes/test_d6c_learn_runtime_chain.py tests/routes/test_learn_adversarial.py -q


Result: **137 passed, 2 warnings in 93.86 s**. Warnings: Pydantic `schema` field shadows a `BaseModel` attribute; `AgentRunResult.usage` is deprecated in an existing retry test.

Lint and formatter checks:

```powershell
uv run ruff check src/curriculum/models.py src/curriculum/routes.py src/curriculum/workspace_projection.py tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py
uv run ruff format --check src/curriculum/workspace_projection.py tests/curriculum/test_workspace_projection.py


Result: Ruff check passed; formatter check passed. Formatter check is limited to new owned files because existing `models.py` and `routes.py` contain unrelated pre-existing formatting differences.

Focused tests cover path isolation, missing rows, output pointer with failure, structural review, teaching-plan review, unverified legacy approval, approved snapshot plus newer draft, typed preparation errors, failure vs stale active-stage precedence, and route-level reading of nested `page_document_v2` approval while outer generation status says failed. The route contract test retains all previous exact fields and asserts the added workspace/debug values.

## Changed files and protection check

P1 files: `apps/textbook-agent/backend/src/curriculum/models.py`, `apps/textbook-agent/backend/src/curriculum/routes.py`, `apps/textbook-agent/backend/src/curriculum/workspace_projection.py`, `apps/textbook-agent/backend/tests/curriculum/test_workspace_projection.py`, `apps/textbook-agent/backend/tests/planning/test_path_routes.py`, `GENERATION_STABILITY_RUNBOOK.md`, `WORKLOG.md`, and this evidence file.

The unrelated modified `.gitignore` and untracked `docs/architecture/generation-reliability-diagnosis-2026-09-22.md` remain untouched. No migration, frontend, approval mutation, realization storage, Print handoff/worker identity, authoring engine, database, environment file, or commit was changed.

## Gate judgmen

The delegated P1 truth projection and its focused regression evidence are ready for Sol review. The implementation leaves path-specific handoff identity and frontend consumption to their later phases. No P1 architectural blocker remains after extracting nested page state from the already loaded wrapper in the curriculum-owned helper. **Do not mark P1 complete or begin P2 until Sol accepts this gate.**
