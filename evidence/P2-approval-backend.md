# P2a evidence — immutable Teaching Plan content identity

Date: 2026-09-23 (Africa/Nairobi)
Branch: `codex/generation-stability
Repository HEAD: `57177e66ce6b1d1e89c0e912b77212c7e138365b` (no commit created)
Gate: Bounded backend implementation and validation complete; **Sol review pending**. P2b and P3 have not started.

## Contract implemented

`curriculum.teaching_plan.content_hash.teaching_plan_content_hash` validates the TeachingPlan and hashes its complete model payload with deterministic JSON serialization. It excludes only code-owned metadata: `teaching_plan_id`, `revision`, `preparation_hash`, and `approval_status`. All pedagogical fields, including `misconception_focus_ids`, participate in the digest. The digest stays stable when pending metadata becomes approved metadata. `preparation_hash` remains the upstream preparation/input identity and is never presented as the Teaching Plan content digest.

The revision store persists a `content_hash` on pending snapshots and approved snapshots. Approval checks the expected revision, the pending snapshot digest, equality between the snapshot and mutable review plan, and—when supplied—the browser's `expected_content_hash`. Stale revision and changed displayed content fail deterministically. Historical approved records without a persisted digest remain readable but cannot start new Learn or Print work; the API returns typed content-hash failure metadata with `recovery_action: reprepare`.

Learn and Print share the curriculum digest adapter. Consumer admission verifies the selected ledger snapshot and digest before new model work, then pins the same `content_hash` in both path handoffs. The current approval pointer is required for default admission; an explicitly pinned older `superseded` snapshot remains usable only when its stored digest verifies. A missing embedded revision is accepted only when the ledger revision is present and its snapshot digest verifies; workspace projection follows the same rule. A nonempty conflicting plan ID or a present conflicting revision is rejected.

The lesson-approach GET returns `teaching_plan`, `teaching_review`, and a separate `teaching_plan_identity` containing pending hash and approved revision/hash verification metadata. Approval accepts `expected_content_hash`, returning a typed 409 on mismatch. Current Units and Studio callers have not yet adopted the field, so the backend records a missing submitted hash as `approval_hash_binding: server_current_compat`; a submitted hash is recorded as `submitted`. This is an explicit P2a transition only. P2b must update both callers to send the pending digest and make the active-flow field required. Hashless historical approvals are rejected for new work, with existing output read access preserved.

`curriculum.shared_tasks.service.teaching_plan_hash`, sourcebook content bindings, review coherence metadata, and both native path hash adapters now use the same digest. This prevents a changed pedagogical plan with the same upstream preparation hash from reusing task/sourcebook identity. Learn no longer silently rewrites an old persisted sourcebook hash to the new Teaching Plan hash; mismatch follows the existing bounded refresh gate.

## Gate coverage

Focused tests cover canonical digest inclusion/exclusion, Print/Learn adapter parity, changed pedagogical content with unchanged preparation identity invalidating shared-task reuse, stale revision and stale displayed hash conflicts, approval snapshot immutability after later edits, same-revision content mutation detection, old pinned approved snapshots, missing approval/ledger/digest rejection, review GET content/review/identity separation, workspace/consumer admission parity for revisionless but digest-verified snapshots, and preservation of preparation approval despite downstream failure.

The existing queue regression also exposed a legacy pending snapshot whose outer ledger carried identity while the embedded TeachingPlan omitted `revision`; approval now accepts an omitted embedded revision while continuing to reject a present mismatch. A focused regression and the full relevant suite pass after this correction.

## Commands and results

From `apps/textbook-agent/backend`:

```tex
uv run pytest tests/curriculum/test_p2_approval_content_identity.py tests/curriculum/test_p02_shared_plan_gates.py tests/curriculum/test_smart_lesson_contracts.py tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py::test_unprepared_lesson_status_is_explicit_over_http tests/planning/test_phase02_queue_and_lease.py::test_approve_queues_without_executing -q
48 passed, 1 warning in 38.58s


```tex
uv run pytest tests/application/test_p03_realization_gates.py tests/print_learn/test_p05_print_production_gates.py tests/print_learn/test_p08_integration_gates.py tests/planning/test_phase02_queue_and_lease.py tests/curriculum/test_workspace_projection.py tests/curriculum/test_p02_shared_plan_gates.py tests/curriculum/test_smart_lesson_contracts.py tests/planning/test_path_routes.py -q
145 passed, 10 warnings in 156.63s


The warnings are the existing Pydantic `GenerationFieldContract.schema` shadow warning and Pydantic-AI `AgentRunResult.usage` deprecations. An earlier run had one failing queue compatibility regression; its failure identified the omitted embedded revision edge described above. After the correction, the targeted test passed and the final expanded regression command, including workspace projection, passed.

```tex
uv run ruff check src/curriculum/teaching_plan src/curriculum/shared_tasks/service.py src/curriculum/lesson_sourcebook/validation.py src/curriculum/lesson_review/service.py src/curriculum/models.py src/curriculum/routes.py src/curriculum/workspace_projection.py src/application/unit_lesson/realization_contracts.py src/application/unit_lesson/realize_learn_handoff.py src/application/unit_lesson/realize_print_handoff.py src/print/generation/native_production.py src/print/generation/whole_lesson/repository.py src/print/generation/whole_lesson/service.py src/print/http/v3_studio/router.py src/learn/generation/native_execution.py src/learn/generation/native_production.py tests/curriculum/test_p2_approval_content_identity.py tests/curriculum/test_p02_shared_plan_gates.py tests/curriculum/test_smart_lesson_contracts.py tests/curriculum/test_workspace_projection.py tests/planning/test_path_routes.py
All checks passed.


```tex
uv run python ../tools/agent/check_architecture.py --format tex
No architecture violations found (exit 0; run by Sol during review).


## Scope and remaining review

No schema migration was needed; the digest is stored with the existing revision-ledger record. The shared-task/sourcebook call sites changed because their existing identity field would otherwise reuse work when the pedagogical TeachingPlan changes but upstream preparation identity does not. Native Print/Learn production adapters changed only to delegate to the curriculum digest. The pre-existing `.gitignore` edit and diagnosis document are preserved.

Sol review requested. Do not begin P2b or P3 before review. P2b must make the browser submit the pending digest on both Units and Studio approval flows and then remove the transitional hashless approval path for active lessons.
