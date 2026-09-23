# P4 Learn lifecycle implementation evidence

Status: implementation complete; pending Sol gate review. P4 is not marked PASS.

## Implemented flow

- Unit and Studio Learn creation now admit a distinct queued Learn output and return before provider work. Unit creation returns HTTP 202 with the realization/output identity. Pathless Studio Learn returns `LEARN_PATH_LESSON_REQUIRED` with `open_unit_lesson` recovery guidance.
- The Learn-owned DB-polling worker claims only queued Learn realizations. It rechecks source ownership, PathLesson identity, immutable approved revision/hash, output ownership, and output pin metadata before invoking the existing writer. A conditional queued-to-running realization update makes duplicate worker dispatch fail closed; the writer still claims the output-scoped Learn lease before provider work.
- Completion writes the Learn document and owner-bound EditableLesson against the distinct output ID, then links that output as `ready` on the Learn realization. Existing ready replay requires both a saved document and editable lesson. Learn output state is independent from preparation and Print state.
- Create replay does not rotate failed runs. Explicit retry accepts only `failed_recoverable`, verifies the pinned approved snapshot again, and uses a conditional update over status, revision, output, and plan identity. A winning retry increments the realization revision once and creates one new output; the previous failed output remains intact. Concurrent losers receive a typed conflict or replay the already queued run.
- The Unit Learn workspace uses canonical backend path state and serializes queued/running refreshes so slow status calls cannot overlap. Terminal/reprepare states do not show an invalid Retry action. Worker failure details flow from the output `error_detail` into the workspace projection.
- App startup/shutdown manages the Learn worker under the existing native-worker feature flag. Existing output lease fencing and stale-lease reconciliation are reused.

## Validation

Commands run from `apps/textbook-agent/backend`:

```text
uv run pytest tests/application/test_p04_learn_worker.py tests/curriculum/test_workspace_projection.py -q
33 passed, 1 pre-existing Pydantic warning, 25.81s

uv run pytest tests/application/test_p04_learn_worker.py tests/curriculum/test_workspace_projection.py tests/application/test_p03_realization_gates.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/print_learn/test_p08_integration_gates.py tests/planning/test_path_routes.py -q
77 passed, 5 existing warnings, 95.14s

uv run pytest tests/application/test_p04_learn_worker.py tests/curriculum/test_workspace_projection.py tests/application/test_p03_realization_gates.py tests/planning/test_phase02_queue_and_lease.py tests/planning/test_native_retry_pre_worker.py tests/planning/test_native_retry_lease_fencing.py tests/planning/test_native_retry_durability.py tests/print_learn/test_p05_print_production_gates.py tests/planning/test_phase02_visual_pdf_routes.py tests/planning/test_path_routes.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/print_learn/test_p08_integration_gates.py -q
207 passed, 11 existing warnings, 136.35s (run before the final Learn retry CAS; the overlapping 77-test suite passed after that CAS)

uv run ruff check src/app.py src/application/unit_lesson/realize_learn_handoff.py src/curriculum/routes.py src/curriculum/workspace_projection.py src/learn/generation/fencing.py src/learn/generation/native_execution.py src/learn/generation/units_routes.py src/learn/generation/worker.py tests/application/test_p04_learn_worker.py tests/curriculum/test_workspace_projection.py
All checks passed!

uv run python ../tools/agent/check_architecture.py --format text
No architecture violations found.
```

Commands run from `apps/textbook-agent/frontend`:

```text
pnpm exec vitest run src/lib/curriculum/lessons/serialized-poll.test.ts src/lib/curriculum/lessons/lesson-context.test.ts src/lib/api/v3.test.ts src/lib/curriculum/lessons/TeachingPlanReview.test.ts src/routes/units/'[id]'/lessons/'[lessonId]'/plan/page.test.ts src/routes/studio/page.test.ts
61 passed across 6 files. Existing fixture stderr covers deliberately injected errors.

pnpm exec vitest run src/lib/curriculum/lessons/serialized-poll.test.ts
1 passed; verifies queued-to-ready refresh and no overlapping refresh while a request is slow.

pnpm run check
0 errors, 5 existing warnings in Learn/Print editor components.

pnpm run build
Passed; existing Svelte warnings and optional dependency notices (canvas, utf-8-validate, bufferutil, supports-color).
```

Repository checks:

```text
git -c core.whitespace=cr-at-eol diff --check
Passed.

docker version
Docker CLI 29.1.5 is installed; Docker Desktop daemon is not reachable (`//./pipe/dockerDesktopLinuxEngine` missing).
```

## Gate coverage and limits

The focused P4 tests prove durable queued admission and duplicate replay, typed pathless Studio rejection, Unit HTTP 202, real single-worker completion with editable-document linkage, Print/preparation isolation, corrupt foreign-output non-mutation, incomplete-ready rejection, explicit retry and duplicate retry behavior, one retry output with no orphan, and stale status without retry affordance. Existing P03 reliability/fencing tests cover a competing Learn output lease claim; P08 covers independent Learn/Print behavior and provider execution.

The shared test fixture uses SQLite, where `SELECT FOR UPDATE` does not provide PostgreSQL row-lock behavior. The conditional Learn retry update is exercised concurrently on SQLite, but the full two-worker PostgreSQL completion proof is deferred to P8 because Docker is installed but its daemon is unavailable. No PostgreSQL concurrent-completion claim is made for P4.

## Sol review request

Please review the Learn admission/worker/retry flow, pathless Studio behavior, output ownership checks, conditional retry reservation, and the SQLite/PostgreSQL test boundary. P5 remains gated on Sol's decision.
