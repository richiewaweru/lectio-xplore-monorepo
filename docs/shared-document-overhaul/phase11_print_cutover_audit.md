# Phase 11 Print cutover audit

Audit of the active Print creation graph, mirroring the Phase 10 Learn
cutover audit's structure, plus the cutover implemented in this package.

## WORK PACKAGE

Bounded Phase 11 cutover: route Unit Print admission and worker execution
onto the verified SharedLessonDocument pipeline (mirroring the Learn P10B
cutover), with contract/failure tests. Deletion of superseded ordinary
Print authoring is a later package; this package only proves zero callers
on the new admission path and lists candidates for that later deletion.

## Active Print creation graph (pre-cutover)

### Unit Print admission

- `POST /api/v1/units/{unit}/path/lessons/{lesson}/realizations:generate-print`
  (frontend caller and route registration were not re-verified in this
  package; the same handoff below is also reached from the legacy `/v3`
  preparation route, exactly like Learn's dual entry point).
- `realize_print_from_preparation` at
  `apps/textbook-agent/backend/src/application/unit_lesson/realize_print_handoff.py:41-322`
  admits a durable `NativeRealizationModel(path="print")` row via
  `admit_realization` (`realize_print_handoff.py:236-249`) and creates a
  detached output `GenerationModel` via `_create_print_output_generation`
  (`realize_print_handoff.py:342-484`) that carries a `page_document_v2`
  chunked-state envelope (`lesson_packet`, `teaching_plan`,
  `teaching_review`, `execution`, etc.) — a materially different shape from
  Learn's flat `native_learn` envelope.
- A `standalone` branch (`realize_print_handoff.py:71-234`, reached when
  `allow_standalone=True` and no Unit lesson resolves) creates a bare
  `GenerationModel` with **no** `NativeRealizationModel` row at all. This is
  the legacy Studio/`v3` authoring surface, has no `path_lesson_id` to hang
  a SharedLessonDocument identity on, and is **out of scope** for this
  package — see "Scope boundary" below.
- `retry_print_realization` (`realize_print_handoff.py:487-640`) reserves a
  new output id for a `failed_recoverable` row under the same pinned
  identity; unchanged by this package.

### Print worker

- `NativeExecutionWorker` at
  `apps/textbook-agent/backend/src/print/generation/whole_lesson/worker.py:26-241`
  polls via `claim_next_native_job`
  (`print/generation/whole_lesson/repository.py:2360-2440`, pre-cutover
  line numbers), which claimed **any** queued/active `page_document_v2`
  generation with a `teaching_plan` + `lesson_packet` and an approved
  review, then called `execute_after_teaching_approval`
  (`print/generation/whole_lesson/executor.py:853+`) — the ordinary
  planning-forms → writing-sections/blocks → assembling pipeline.
- Ordinary authoring entrypoints reached from that pipeline:
  - `plan_forms`/form agent (`print/generation/whole_lesson/form_agent.py`,
    `form_plan.py`) — ordinary section/block form planning.
  - Writer dispatch inside `executor.py` (`_writer_result_from_outcome` and
    surrounding block-writing loop, `executor.py:600-785`) — ordinary
    per-block prose/table/figure/task authoring via
    `print/generation/whole_lesson/teaching_agent.py`,
    `visual_dispatch.py`, `shared_writer_bridge.py`.
  - `print.generation.native_production` (`native_production.py`) and
    `print.generation.document_realizer` (`document_realizer.py`) —
    Teaching-Plan-driven whole-document composition/reinterpretation used
    by older dual-native/native_http entrypoints
    (`application/unit_lesson/dual_native.py`,
    `native_http.py`), not the Unit admission route above but still live
    callers pre-cutover.
  - `print.generation.composition_bridge` — bridges Teaching Plan blocks
    into the whole-lesson form/writer pipeline; still called from
    `native_production.py`/`document_realizer.py`.

### Persistence / editor / PDF / answer key

- Document candidate/finalize seam:
  `persist_document_candidate` / `finalize_verified_document`
  (`print/generation/whole_lesson/repository.py`, pre-cutover ~1387-1622) —
  lease-fenced, hash-verified write of `GenerationModel.document_json`, the
  single source both PDF export and the answer key read.
- Read route: `GET /api/v1/v3/generations/{generation_id}/document`
  (`print/http/v3_studio/router.py:1955`).
- PDF export: `print/rendering/pdf/service.py` renders the SSR route
  `/studio/print/{generation_id}` via Playwright
  (`pdf/service.py:353-397`); it reads whatever `document_json` the above
  seam persisted — no separate composition path.
- **No ordinary-content edit route was found for the Print
  `LectioDocumentV2`.** The only Print-adjacent PATCH routes in
  `print/http/v3_studio/router.py` (`:1010`, `:1194`) edit Studio *concept
  cards*/*pack items* (an older, separate authoring surface, not the
  admitted-Unit-Print `LectioDocumentV2`). There is therefore no existing
  "Print editor" PUT/PATCH to add a lineage/ordinary-node-edit guard to for
  this package; if one is added later it must verify
  `GenerationModel.shared_document_*` lineage and block ordinary-node edits
  (mirroring the Learn Builder guard), while continuing to allow
  Print-owned layout/treatment-only fields per `18_PRINT_REALIZATION.md`.

## Cutover implemented in this package

Mirrors the Learn P10B pattern
(`document/shared_lesson/realization_source.py`,
`learn/generation/shared_document_execution.py`) as closely as Print's
different persistence shape allows:

1. **Admission pinning.** `realize_print_from_preparation`'s non-standalone
   branch now calls `ensure_shared_document_run` and pins
   `NativeRealizationModel.shared_document_run_id`
   (`realize_print_handoff.py`, after the legacy self-link check, before
   output creation), exactly like Learn admission
   (`realize_learn_handoff.py:346-379`). Duplicate admission reuses the same
   pinned run (idempotent, proven in
   `tests/application/test_p10b_shared_document_learn_cutover.py`'s Learn
   analogue and by this package's updated P03 tests).
2. **No new migration.** `NativeRealizationModel` and `GenerationModel`
   already carry `shared_document_run_id/id/revision/hash` generically
   (added by migration `20260928_0047_learn_shared_document_lineage.py` for
   *all* rows in those shared tables, not only Learn rows — confirmed by
   reading `infra/database/models.py:124-171` (`GenerationModel`) and
   `:1050-1108` (`NativeRealizationModel`)). `EditableLessonModel`/
   `LearnReleaseModel` are Learn-only and untouched; Print has no editable
   workspace or release table.
3. **Worker gate.** `claim_next_native_job`
   (`print/generation/whole_lesson/repository.py`) now recognizes every
   detached (non-legacy) `NativeRealizationModel(path="print")` row and
   calls `load_realization_source` **before** ever claiming a lease:
   - `pending` — never claims; the realization row is annotated
     (`shared_document_run_id`/`shared_document_state="pending"`) but its
     `status` stays `queued` and no attempt is consumed (mirrors Learn).
   - `needs_review` — `status="needs_shared_review"`,
     `shared_document_state="needs_review"`.
   - `stale` / `failed` — `status="failed_recoverable"`,
     `shared_document_state` set accordingly, typed `error_summary`.
   - `ready` — proceeds to `PageDocumentRepository.claim_execution` exactly
     as before (queued → planning_forms), then `NativeExecutionWorker._run_job`
     detects the same cutover row and calls
     `print.generation.shared_document_execution.execute_print_realization_from_shared_document`
     instead of `execute_after_teaching_approval`.
4. **Pure adapter execution.**
   `execute_print_realization_from_shared_document`
   (`print/generation/shared_document_execution.py`, new file):
   - Transitions `planning_forms → assembling` directly
     (`PageDocumentRepository.enter_assembling_for_shared_document`, new
     method; `states.py` additively allows this one transition — a verified
     shared source skips ordinary form planning/writing entirely).
   - Calls the pre-existing pure adapter
     `print.generation.shared_document_adapter.realize_shared_document_for_print`
     against the verified `SharedLessonDocument` and only the **ready**
     `FigureMediaResult` entries from `ready.media_results` (a deferred
     binding is *excluded*, not replaced with a synthetic placeholder, so a
     required figure with only deferred media fails truthfully through the
     adapter's own required-figure check, per `18_PRINT_REALIZATION.md`:
     "Required figure failure cannot yield a truthful fully-ready result").
   - A `SharedDocumentPrintMappingError` is persisted through a new,
     narrow `PageDocumentRepository.fail_shared_document_mapping` method —
     `failed_recoverable`, never `classify_failure`'s provider-retry
     heuristics, since a mapping failure is a data-truthfulness failure, not
     a transient provider error.
   - On success, persists through the **same**
     `persist_document_candidate` → fresh-session reload/hash-verify →
     `finalize_verified_document` seam every other Print output uses, so
     `GET /document`, PDF export, and the answer key are reading
     identical, hash-verified content — no new read path was created.
     Lineage (`shared_document_run_id/id/revision/hash`) is stamped on both
     the output `GenerationModel` and the `NativeRealizationModel` row.
   - Resume-safe: a lease reclaimed while already in `assembling` (a crash
     between entering assembling and the fresh-session finalize) re-runs
     the adapter and the hash-fenced candidate/finalize seam, which is
     idempotent over the same immutable inputs.
5. **No ordinary composer/writer/whole-lesson-form call is reachable** for
   a detached, cutover-admitted Print realization: `claim_next_native_job`
   never falls through to the ordinary `teaching_plan`/`lesson_packet`
   claim branch for such a row (see zero-caller evidence below), and
   `execute_print_realization_from_shared_document` never imports
   `print.generation.whole_lesson.form_agent`,
   `print.generation.whole_lesson.teaching_agent`,
   `print.generation.composition_bridge`,
   `print.generation.native_production`, or
   `print.generation.document_realizer`.

## Scope boundary: standalone Studio Print is unchanged

The `allow_standalone=True` branch of `realize_print_from_preparation`
(no Unit lesson, no `NativeRealizationModel` row) cannot carry a
SharedLessonDocument identity — there is no `path_lesson_id` to key
`ensure_shared_document_run`/`load_realization_source` on. It continues to
route through the ordinary whole-lesson pipeline untouched by this
package. `claim_next_native_job`'s new gate only fires when a
`NativeRealizationModel(path="print", output_id=<this generation>)` row
exists, so standalone generations fall through to the pre-existing
ordinary-path branch exactly as before. This matches the work package's
explicit scope ("Unit Print admission route(s)") and Sol should decide
later whether standalone Studio Print is retired or given its own
SharedDocument-compatible identity.

## Deployment note (not code-gated in this package)

`claim_next_native_job`'s cutover branch applies to a detached Print
`NativeRealizationModel` row regardless of its `GenerationModel.status`
(queued or an active status being reclaimed after a stale heartbeat). A
Print job that was already mid-flight through the *ordinary* pipeline
(`writing_sections`/`writing_blocks`/`assembling`) at the moment this
package deploys would, on its next stale-heartbeat reclaim, be routed
through the new cutover path instead of resuming ordinary writing. Draining
in-flight Unit Print jobs before deploying this package (or accepting that
they fail over to a fresh SharedDocument-sourced attempt) is a rollout
concern for Sol/ops, not a code gate added here — no in-flight jobs existed
in this repository's test/dev database at the time of this package.

## Zero-caller / deletion evidence (candidates for the later deletion package)

These modules have **zero callers on the cutover admission path** proven by
the monkeypatch guard test
(`tests/application/test_p11_print_shared_document_cutover.py::test_ready_path_never_calls_ordinary_authoring`)
and by `rg` below. They are **not deleted in this package** — Sol must
approve deletion after the standalone-Studio-Print scope question above is
resolved, since some of these modules may still be reachable from the
standalone branch:

- `print.generation.whole_lesson.form_agent` / `form_plan.py` — ordinary
  form planning.
- `print.generation.whole_lesson.teaching_agent` — ordinary per-block
  writing.
- `print.generation.composition_bridge` — Teaching-Plan → form/writer
  bridge.
- `print.generation.native_production` — whole-document Teaching-Plan
  composition (still reachable from `dual_native.py`/`native_http.py` for
  the standalone/legacy surfaces; not zero-called overall).
- `print.generation.document_realizer` — Teaching-Plan heuristic realizer
  (same caveat).

```
rg "form_agent|teaching_agent" src/print/generation/shared_document_execution.py src/print/generation/whole_lesson/worker.py
# (no matches)
```

## Focused tests (this package)

- `tests/application/test_p11_print_shared_document_cutover.py` (new):
  duplicate admission reuse, `pending`/`needs_review`/`stale`/`ready`
  worker-gate classification, zero-caller monkeypatch proof for the ready
  path, and an answer-key integrity check against the SharedDocument task
  evaluations.
- `tests/application/test_p03_realization_gates.py`: updated
  `test_p03_detached_print_output_is_idempotent_and_failure_retry_isolated`
  and `test_p07_detached_print_export_failure_preserves_approval_and_ready_learn`
  to drive their SharedLessonDocument run to `ready` before calling
  `claim_next_native_job`, since an admitted Print realization no longer
  claims a lease until its shared source verifies ready.

## TESTS

See the Luna report accompanying this commit for exact command/count
evidence.

## MIGRATIONS

None. `NativeRealizationModel`/`GenerationModel` already carry the required
lineage columns from migration `20260928_0047_learn_shared_document_lineage.py`.

## P11B deletion (2026-09-29)

Standalone Print generation is retired (Sol's decision above): a request that
resolves no `path_lesson_id` now fails closed at admission with a typed
`PRINT_STANDALONE_RETIRED` 409 (`realize_print_from_preparation`), instead of
falling back to the old detached-`GenerationModel`-only creation path. The
`allow_standalone` parameter and both `native_http.py` call sites that passed
`allow_standalone=True` are removed.

### Deleted (zero production caller once standalone was removed)

- `print/generation/composition_bridge.py`
- `print/generation/document_realizer.py`
- `print/generation/shared_writer_bridge.py`
- `print/generation/authoring_adapter.py`
- `print/generation/work_orders.py`
- `print/generation/selection_snapshot.py`
- `print/generation/source_resolver.py`
- `print/generation/model_tiers.py`
- `print/generation/whole_lesson/form_agent.py`
- `print/generation/whole_lesson/form_plan.py`
- `print/generation/whole_lesson/executor.py`
- `print/generation/whole_lesson/resolved_block_plan.py`
- `print/generation/whole_lesson/failure_injection.py`
- `application/unit_lesson/dual_native.py`
- `print/generation/native_production.py`'s ordinary composition/selection body
  (kept as a thin `teaching_plan_content_hash` compat shim, mirroring Learn's
  P10E `learn/generation/native_production.py` shim — `realize_print_handoff.py`
  still imports that one function).
- `curriculum.prompts.form_planner_prompt` (and its packaged resource file
  `resources/form-planner-v1.txt`) — its only caller,
  `prompt_render.render_form_prompt`, is deleted below.
- Six historical Phase-9 operator scripts that imported already-deleted
  modules (`scripts/live_closeout_bcd.py`, `live_closeout_bc_plans.py`,
  `run_p09_live_campaign.py`, `run_p09_salvage_attempts_a.py`,
  `run_p09_salvage_case_a.py`, `run_p09_v05_failure_recovery.py`), plus three
  more found by the same zero-caller sweep
  (`scripts/live_print_composition_proof.py`, `live_print_pdf_proof.py`,
  `live_sibling_path_proof.py`, all importing `composition_bridge`).

### Trimmed dead code in files that stay (they have a live caller elsewhere)

- `print/generation/whole_lesson/validation.py` — removed `validate_form_plan`/
  `advisory_form_qc`/the `FormPlan` import; kept `validate_teaching_plan`/
  `advisory_teaching_qc`/`allowed_teaching_evidence_refs`/`anchor_terms`
  (live via `teaching_agent.run_lesson_approach_planner`).
- `print/generation/whole_lesson/prompt_render.py` — removed
  `render_form_prompt`/`build_form_planner_payload`/the `form_planner_prompt`
  import; kept `render_teaching_prompt` (same live caller).
- `print/generation/whole_lesson/__init__.py` — dropped the `FormPlan`/
  `FormDecision`/`FormPlanBlock`/`FormPlanSection`/`coerce_form_plan`/
  `ResolvedBlockPlan`/`ResolvedLessonPlan`/`ResolvedSectionPlan`/
  `resolve_block_plans` re-exports (their source modules are deleted).
- `print/rendering/page_objects/registry.py` — deleted the LLM writer path
  (`dispatch_writer_async`, `_write_validated_llm`, `_work_order_for_context`,
  `_LegacyWriterAuthoringProvider`, `_document_writer_kind`,
  `_print_payload_to_document_primitive`, `_authoring_provider`,
  `_content_validation_from_authoring_error`, `_figure_result_from_content`)
  and its now-unused imports (`infra.authoring.*`, `document_form_map`,
  `work_orders`, `FORM_OUTPUTS`/`WRITER_PROVIDER_OUTPUTS`/
  `ContentValidationError`/`UnsupportedObject`). Kept the deterministic
  `dispatch_writer`/stub-writer dispatch, which is the live path
  `print/rendering/page_objects/document_assembly.py` calls from
  `shared_document_adapter.py`/`shared_document_execution.py`.
- `print/rendering/page_objects/__init__.py` / `models.py` — dropped the
  `dispatch_writer_async` export and the stale `PrintWorkOrder` type hook on
  `WriterContext.print_work_order` (now `Any | None`; nothing sets it any
  more since `executor.py` is gone).
- `print/generation/whole_lesson/worker.py` — removed the
  `execute_after_teaching_approval` import/call; a claimed job that is
  neither a pre-worker retry nor a detached cutover realization now raises
  a typed `RuntimeError` (persisted as a failure) instead of running ordinary
  authoring — it can only be a stale pre-P11B standalone row.
- `print/generation/whole_lesson/repository.py` — `claim_next_native_job`'s
  ordinary-claim branch (rows with no `NativeRealizationModel` link) now
  always `continue`s instead of calling `claim_execution`; such a row can
  only be a stale pre-P11B standalone artifact and is never claimed again
  (its persisted `document_json`, if any, stays readable).

### KEPT-WITH-LIVE-CALLER (verified, not touched)

- `print/generation/whole_lesson/teaching_agent.py` —
  `run_lesson_approach_planner` called from
  `print/generation/whole_lesson/service.py:29`, itself called from
  `application/unit_lesson/native_pipeline.py` and
  `print/generation/whole_lesson/native_retry.py` (the shared Teaching Plan
  preparation pipeline, upstream of both Learn and Print).
- `print/generation/whole_lesson/native_status.py` — `project_native_status`
  called from `application/unit_lesson/native_pipeline.py:138`;
  `visual_quality_summary` called from `print/http/v3_studio/router.py:1819,1975`.
- `print/generation/whole_lesson/visual_dispatch.py` (and its
  `visual_topology*.py` dependents) — `dispatch_and_patch_from_repo` called
  from `application/unit_lesson/native_http.py:469` (`/visuals/retry` route).
- `print/generation/catalogue_projections.py` — imported by
  `print/generation/whole_lesson/legality.py` and `teaching_agent.py` (both
  live).
- `print/generation/task_treatments.py` — `print_treatment_for_learner_action`
  called from `print/generation/shared_document_adapter.py:26` (the P11
  cutover adapter itself) and `print/resources/selection.py`.
- `print/generation/whole_lesson/failure_policy.py` /
  `print/generation/whole_lesson/teaching_errors.py` — `classify_failure`
  called from `repository.py`/`worker.py` for generic native-job failure
  classification, not ordinary-authoring-specific.
- `print/generation/whole_lesson/{packet,packet_builder,service,legality,
  teaching_plan,events,states,figure_ids,native_routing}.py` — the shared
  Teaching Plan preparation/native-routing/status plumbing used by both
  Learn and Print, untouched by this package.

### Zero-caller sweep evidence (representative)

```
rg "print\.generation\.(composition_bridge|document_realizer|shared_writer_bridge|authoring_adapter|work_orders|selection_snapshot|source_resolver|model_tiers)" src
rg "whole_lesson\.(form_agent|form_plan|executor|resolved_block_plan|failure_injection)" src
rg "unit_lesson\.dual_native" src
# (no matches outside the deleted modules themselves after this package)
```

### Tests

Deleted tests that only exercised the retired ordinary pipeline:
`tests/print_learn/{test_composition_bridge,test_document_realizers,
test_p04_native_selection_gates,test_p05_print_production_gates,
test_print_document_align,test_shared_writer_bridge}.py`;
`tests/planning/{test_contract_hardening,test_contract_ownership,
test_parallel_section_execution,test_phase02_delivery_proof,
test_phase02_document_fencing,test_phase02_resume_and_assembly,
test_phase02_worker_failure_policy,test_section_resume,
test_streaming_monotonic,test_d6a_unit_print_integration,
contract_fixtures}.py`;
`tests/authoring_correction/{test_a00_print_table_fallback,
test_a01_authoring_definitions,test_a02_shared_authoring_engine,
test_a03_print_authoring_migration,test_a05_selection}.py`;
`tests/generation/{test_native_all_forms_e2e,
test_writer_registry_all_forms,test_writer_repair}.py`;
`tests/remaining_fixes/test_r03_print_selection.py`.

Extracted still-needed fixtures (`packet`/`make_snapshot`/
`five_item_check_packet`/`check_plan`) into new
`tests/planning/legality_fixtures.py` before deleting their old home
(`test_contract_hardening.py`), since `test_teaching_plan_semantic_review.py`
and `test_pre_worker_failure_sync.py` still need them for still-live
Teaching Plan review coverage.

Surgically removed only the now-invalid assertions inside otherwise-live
test files rather than deleting the whole file:
`test_pre_worker_failure_sync.py` (dropped its two
`failure_injection`/`execute_after_teaching_approval`-only tests, kept the
pre-worker teaching-failure-sync tests), `test_native_retry_pre_worker.py`
(dropped one whole `failure_injection`-only test and two
"must-not-run"-guard `patch()` calls that targeted the deleted executor
module inside otherwise-live tests).

Adapted `tests/planning/test_phase02_queue_and_lease.py`'s three
`claim_next_native_job` race/reclaim tests (`test_two_workers_cannot_both_claim_queued`,
`test_stale_active_contention_one_winner`, `test_fresh_heartbeat_prevents_reclaim`)
to seed a genuine SharedLessonDocument-admitted, ready-for-claim Print
realization instead of the old bare `_seed_native_generation` row (which
`claim_next_native_job` never claims any more) — otherwise these tests would
either fail outright or silently degrade to a vacuous pass.

New guard: `tests/architecture/test_p11b_print_ordinary_authoring_guard.py`
(retired-module `ModuleNotFoundError`, an AST scan forbidding
`document.composer`/`document.writer` imports anywhere under `print/` or
`application/unit_lesson/` with **no exception** — unlike Learn's P10E guard,
Print's last caller of those modules, `composition_bridge.py`, is deleted —
a deleted-symbol reference scan, a signature check that `allow_standalone`
is gone, and a fail-closed proof for a standalone admission request).

## RISKS / QUESTIONS

- `document/composer.py::compose_document_plan` and
  `document/writer.py::write_document_primitive` appear to have **zero
  production callers left at all** now that `composition_bridge.py` (their
  last caller) is deleted — confirmed by `rg "document\.composer\b|document\.writer\b" src`
  outside `document/__init__.py`'s own re-export. `learn/generation/work_orders.py`
  still reads `document.writer._PRIMITIVE_SCHEMAS` for its closed
  LessonDocument-v1 `compile_learn_work_orders` path, which the P10E guard
  already documented as test-only (zero production callers). Deleting this
  whole chain (`document/composer.py`, `document/writer.py`,
  `document/writer_prompts.py`, `compile_learn_work_orders`, and the P10E
  guard's `learn/generation/work_orders.py` exception) is optional bonus
  scope that spans `tests/authoring_correction`, `tests/policy_cleanup`, and
  `tests/remaining_fixes` files unrelated to Print — left for Sol to
  schedule as its own follow-up rather than folded into this Print-focused
  package.
- `infra/authoring/model_policy/models.py::V2_FORM_PLANNER` is now a
  zero-caller model-tier slot (its only real caller, `form_agent.py`, is
  deleted), but `tests/v3_execution/test_v3_config_models.py` parametrizes
  over it generically; left in place rather than touching that unrelated
  test file for a one-constant cleanup.
- No Print content-edit route currently exists to add a lineage/ordinary-
  node-edit guard to; if one is added later it must reuse the lineage
  verification pattern from this package.
- The in-flight-job deployment note above is a rollout concern, not a code
  gate; flag to ops before deploying this branch if any Unit Print job is
  mid-flight in production. Deploying P11B additionally means any stale
  pre-P11B standalone `GenerationModel` row still queued/active will never
  be claimed again (it fails closed by omission, not by an explicit error);
  its already-persisted `document_json`, if any, remains readable.
