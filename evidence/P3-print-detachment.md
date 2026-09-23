# P3 — Detached Print outpu

Date: 2026-09-23
Branch: `codex/generation-stability
Base HEAD: `57177e66ce6b1d1e89c0e912b77212c7e138365b
Gate: Implementation and validation complete; **Sol review pending**. Do not start P4 before acceptance.

## Implemented behavior

- Create Print verifies the immutable, hash-bound approved Teaching Plan under a lock on the source preparation. It leaves the preparation Generation and teaching approval ledger unchanged, admits a Print realization, allocates a separate queued output Generation, and links the realization to that output.
- Output page state is initialized empty. It copies the approved snapshot, required packet/legality/catalogue/QC inputs, and shared semantic artifacts from an allowlist. Existing Print documents, form plans, execution state, lease data, errors, visuals, writer checkpoints, and progress/call-budget state do not transfer.
- Duplicate admission reuses the same realization/output. Reused outputs must have the expected owner and realization/preparation/Teaching Plan ID, revision, and hash or admission returns typed 409 `PRINT_OUTPUT_IDENTITY_CONFLICT`.
- Worker lifecycle updates the linked realization from the output Generation. Stale and read-only realizations are absorbing. Retry row-locks and rechecks the failed realization before reserving a new output, pins the verified approved snapshot (including a verified superseded snapshot), and keeps the prior output/document.
- The active Studio approval path saves approval without queuing the preparation, then admits/polls the detached output. Studio updates its active generation ID and URL query to the output ID. Output status exposes `requested_realization_path`; refresh fetches and displays the verified approved Teaching Plan, and retry targets the detached output.
- Standalone Studio is supported through its explicit `native_whole_lesson` source marker. A source with Unit/path markers but missing PathLesson/provenance fails closed with typed `PRINT_PATH_PROVENANCE_MISSING` rather than taking the standalone branch.

## Legacy behavior and limits

- A historical Print realization whose `output_id` still equals its preparation ID can be read when already ready; non-ready preparation-linked rows are read-only and require reprepare to create a detached run.
- Standalone Studio has a detached output Generation but no `NativeRealizationModel`: that model requires a `PathLesson` foreign key. Its retry/history lifecycle is therefore represented by the output Generation itself. Existing standalone preparations without the explicit native Studio marker fail closed and need recovery/reprepare.
- Hashless, ambiguous legacy records remain non-executable. Existing saved output read access remains intact.

## Validation

From `apps/textbook-agent/backend`:

```tex
uv run pytest tests/application/test_p03_realization_gates.py -q


Result after Sol's ready-artifact acceptance regression: **18 passed, 1 existing Pydantic warning in 35.40s**. Coverage includes output-to-realization `ready` linkage, owner-checked artifact read, unchanged approved source snapshot, detached-output pointer integrity, old-output stale guard, Studio standalone gate, and missing Unit provenance.

Expanded queue, retry, production, route, and P3 regression command:

```tex
uv run pytest tests/planning/test_phase02_queue_and_lease.py tests/planning/test_native_retry_pre_worker.py tests/planning/test_native_retry_lease_fencing.py tests/planning/test_native_retry_durability.py tests/print_learn/test_p05_print_production_gates.py tests/planning/test_phase02_visual_pdf_routes.py tests/planning/test_path_routes.py tests/application/test_p03_realization_gates.py -q


Result before Sol's additional ready-artifact test: **161 passed, 7 warnings in 95.85s**. Warnings were the existing Pydantic `schema` field warning and PydanticAI `usage` deprecation warnings. The final P3-only rerun below includes the added acceptance case.

Focused tests were also rerun individually during implementation: standalone Studio plus missing Unit path provenance: **2 passed**; corrupt detached-output pointer identity: **1 passed**. The final full P3 suite above includes these regressions.

From `apps/textbook-agent/frontend`:

```tex
npm test -- src/routes/studio/page.test.ts
npm run check
npm run build


Studio tests: **34 passed**. Svelte check: **0 errors, 5 existing warnings** in other editor/canvas files. Production build completed successfully with existing Svelte warnings and optional-dependency notices for `canvas`, `bufferutil`, `utf-8-validate`, and `supports-color`.

Backend quality gates:

```tex
uv run ruff check src/application/unit_lesson/realize_print_handoff.py src/application/unit_lesson/realizations.py src/print/generation/whole_lesson/repository.py src/print/http/v3_studio/router.py src/print/http/v3_studio/dtos.py src/curriculum/routes.py tests/application/test_p03_realization_gates.py
uv run python ../tools/agent/check_architecture.py --format tex


Ruff passed. Architecture checker returned `No architecture violations found` (exit 0). `git -c core.whitespace=cr-at-eol diff --check` passed.

## Changed areas

- Backend Print admission/retry: `application/unit_lesson/realize_print_handoff.py` and `application/unit_lesson/realizations.py`.
- Output worker repository state and status synchronization: `print/generation/whole_lesson/repository.py`.
- Curriculum retry/status route and Studio approval/status contracts: `curriculum/routes.py`, `print/http/v3_studio/router.py`, and `print/http/v3_studio/dtos.py`.
- Studio output-ID handoff, query, refresh, approved-plan display, and retry tests: `frontend/src/routes/studio/+page.svelte` and `page.test.ts`.
- Focused gate coverage: `backend/tests/application/test_p03_realization_gates.py`.

Earlier P0/P1/P2 work remains in the same uncommitted branch. The pre-existing `.gitignore` change and untracked diagnosis document were preserved. No commit was created.
