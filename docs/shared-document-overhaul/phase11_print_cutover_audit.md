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

## RISKS / QUESTIONS

- Standalone Studio Print (no Unit lesson) is out of scope and unchanged;
  Sol should decide its fate (retire vs. give it its own identity) before
  the deletion package, since some zero-caller candidates above are still
  reachable from it.
- No Print content-edit route currently exists to add a lineage/ordinary-
  node-edit guard to; if one is added later it must reuse the lineage
  verification pattern from this package.
- The in-flight-job deployment note above is a rollout concern, not a code
  gate; flag to ops before deploying this branch if any Unit Print job is
  mid-flight in production.
