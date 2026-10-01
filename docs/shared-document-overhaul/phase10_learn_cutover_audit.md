# Phase 10 Learn cutover audit

Read-only audit of the active Learn creation and consumption graph in the main
checkout. This file records the entry points and contract gaps that must be
closed before routing all new Learn creation through a verified
`SharedLessonDocument`.

## WORK PACKAGE

Bounded Phase 10 read-only cutover audit: identify active Learn creation
entrypoints/callers, ordinary authoring callers and prompts, persistence/open/
reload/evaluation/progress/publish paths, exact file:line evidence, dependency
order, and contract gaps.

## STATUS

Complete as a read-only audit. No runtime, schema, frontend, or test code was
changed.

## CHANGES

Created this audit document only. It records the current graph and the work
required for SharedLessonDocument identity verification and Learn cutover.

## Audit checklist

- [x] Trace Unit workspace admission and frontend callers.
- [x] Trace the legacy preparation-generation admission route.
- [x] Trace worker, persistence, Builder open/reload/save, publish, runtime,
  evaluation, progress, and release paths.
- [x] Locate ordinary composer, writer, figure, interaction, and prompt calls.
- [x] Record exact cutover dependency order and deletion guards.
- [x] Identify contract and verification gaps without editing runtime code.

No database or full-suite command was run for this audit.

## Current active creation graph

### Canonical Unit workspace admission

The current product-facing creation call is:

```text
Unit Learn workspace
  -> POST /api/v1/units/{unit}/path/lessons/{lesson}/realizations:generate-learn
  -> realize_learn_from_preparation
  -> NativeRealizationModel(path=learn)
  -> LearnRealizationWorker
  -> execute_learn_realization
  -> produce_learn_from_approved_teaching
  -> Teaching Plan -> ordinary composer/writer + Learn interaction writer
```

References:

- Frontend calls `generateLearnRealization` from
  `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/learn/+page.svelte:156-168`.
  It only admits when the preparation projection is approved and fresh.
- The API client posts the path and lesson revisions at
  `apps/textbook-agent/frontend/src/lib/api/units.ts:346-364`.
- The backend route validates Unit, path, and lesson identity, requires
  `lesson.pack_id` as preparation, and calls the application handoff at
  `apps/textbook-agent/backend/src/learn/generation/units_routes.py:441-500`.
- The handoff verifies the approved Teaching Plan and admits a durable Learn
  realization at
  `apps/textbook-agent/backend/src/application/unit_lesson/realize_learn_handoff.py:268-373`.
- The worker polls queued Learn rows and calls the execution handoff at
  `apps/textbook-agent/backend/src/learn/generation/worker.py:77-105`.
- Execution claims the Learn row and output lease, then calls the existing
  producer at
  `apps/textbook-agent/backend/src/application/unit_lesson/realize_learn_handoff.py:376-464`.
- The producer currently enters the old Teaching Plan authoring path at
  `apps/textbook-agent/backend/src/learn/generation/native_execution.py:452-464` and
  `apps/textbook-agent/backend/src/learn/generation/native_execution.py:527-547`.

### Legacy preparation-generation admission

The older `/v3` preparation route remains registered and is another active
caller of the same handoff:

- `POST /api/v1/v3/generations/{generation_id}/realize-learn` is defined at
  `apps/textbook-agent/backend/src/application/unit_lesson/native_http.py:198-230`.
- The router is imported and registered by
  `apps/textbook-agent/backend/src/app.py:18` and
  `apps/textbook-agent/backend/src/app.py:331`.
- It calls `realize_learn_from_preparation` directly, without a shared-document
  identity in its request or response.

This route must either be moved behind the same SharedLessonDocument admission
contract or be retired after callers are proven absent. Removing only the Unit
route would leave this route able to create a Learn realization through the old
path.

### Builder creation and materialization surfaces

There are two Builder entry points with different roles:

- `POST /api/v1/builder/lessons` creates a mutable editable lesson directly at
  `apps/textbook-agent/backend/src/learn/authoring/builder/routes.py:360-432`.
  It accepts `manual`, `template`, `document`, `learn_document`, and
  `native_learn` source types through
  `apps/textbook-agent/backend/src/learn/authoring/builder/service.py:24-29`.
  The frontend API wrapper is
  `apps/textbook-agent/frontend/src/lib/learn/authoring/builder/api/lesson-crud.ts:30-53`;
  no current product page caller was found, but the HTTP endpoint remains an
  active direct creation backdoor and is covered by route tests.
- `POST /api/v1/builder/lessons/from-native-learn/{generation_id}` materializes
  a completed native generation at
  `apps/textbook-agent/backend/src/learn/authoring/builder/routes.py:449-491`.
  It copies the generated payload into `EditableLessonModel` through
  `get_or_create_native_learn_builder_lesson` at
  `apps/textbook-agent/backend/src/learn/authoring/builder/service.py:173-217`.

The Unit Learn page uses the second materialization path when the native output
has an `open_href` but no editable lesson yet:
`apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/learn/+page.svelte:79-117`.

The direct Builder route needs an explicit product decision before final
deletion: retain it as manual authoring with a clearly separate source, or
require every generated Learn artifact to carry a verified SharedLessonDocument
lineage. It currently accepts `document` and `learn_document` without that
lineage.

## Ordinary authoring callers that must leave the Learn path

The current Learn producer still owns ordinary composition and writing:

- `compose_document_plan` is called from
  `apps/textbook-agent/backend/src/learn/generation/native_production.py:387-398`.
- `write_document_primitive` is called once per ordinary decision from
  `apps/textbook-agent/backend/src/learn/generation/native_production.py:413-472`.
- Figure media is attached inside that same loop at
  `apps/textbook-agent/backend/src/learn/generation/native_production.py:473-503`.
- Learn interaction authoring is called at
  `apps/textbook-agent/backend/src/learn/generation/native_production.py:504-553`.
  This interaction writer can remain only for realizing retained
  `TaskAnchor`/`SharedTaskSpec` contracts; it must not recreate ordinary task
  meaning.
- The final LearnDocument v2 is assembled in
  `apps/textbook-agent/backend/src/learn/generation/native_production.py:565-597`.

The old ordinary implementation and prompts are still live dependencies:

- `document.composer.compose_document_plan` is implemented at
  `apps/textbook-agent/backend/src/document/composer.py:375-527`; it resolves
  the locked `document-composer` prompt through
  `apps/textbook-agent/backend/src/document/composer.py:17-21` and
  `apps/textbook-agent/backend/src/document/writer_prompts.py:32-44`.
- `document.writer.write_document_primitive` is implemented at
  `apps/textbook-agent/backend/src/document/writer.py:258-399`; it resolves the
  locked `document-writer` prompt through
  `apps/textbook-agent/backend/src/document/writer.py:24-26` and
  `apps/textbook-agent/backend/src/document/writer_prompts.py:37-47`.
- The prompt manifest still exposes those ordinary stages at
  `apps/textbook-agent/backend/resources/prompts/manifest.yaml:77-87`.
  Their bodies are `resources/prompts/document-composer.md` and
  `resources/prompts/document-writer.md`.
- `learn.generation.document_realizer.realize_learn_document` remains a
  Teaching Plan heuristic path at
  `apps/textbook-agent/backend/src/learn/generation/document_realizer.py:90-132`.
  `native_production.py:30` imports it and line 634 retains a module-level
  reachability assignment, so the symbol and its tests still prevent a simple
  zero-caller claim.
- `native_execution.py:434-511` revalidates and may regenerate the lesson
  sourcebook and shared task registry before Learn writing. That is a second
  source of ordinary semantic authoring and must be replaced by a read-only
  load of the approved SharedLessonDocument and its frozen TaskAnchors.

The retained interaction prompts remain separate and should be audited after
the SharedTaskSpec mapping is wired:

- `interaction-selection` is used by the selection helper in
  `apps/textbook-agent/backend/src/learn/generation/native_production.py:138-186`.
- `interaction-writer` is used by
  `apps/textbook-agent/backend/src/learn/generation/interaction_writer.py:146-378`.
- The manifest entries are at
  `apps/textbook-agent/backend/resources/prompts/manifest.yaml:89-99`.

## Persistence, open/reload, evaluation, progress, and publish

### Generated output and editable workspace

- `GenerationModel` stores the generated JSON and runtime state in
  `document_json` and `chunked_state_json` at
  `apps/textbook-agent/backend/src/infra/database/models.py:122-161`.
- A completed Learn run creates an `EditableLessonModel` row and copies the
  generated document into it at
  `apps/textbook-agent/backend/src/learn/generation/native_execution.py:615-752`.
- The editable table stores only `source_generation_id`, `source_type`, title,
  and mutable `document_json` at
  `apps/textbook-agent/backend/src/infra/database/models.py:679-705`.
- Builder GET, PUT, and DELETE are active at
  `apps/textbook-agent/backend/src/learn/authoring/builder/routes.py:518-643`.
  PUT rewrites the ordinary document in place at lines 567-624.
- The Unit workspace resolves a Builder id by looking up an editable lesson
  using `source_generation_id` at
  `apps/textbook-agent/backend/src/curriculum/routes.py:330-368`.
- The frontend then reads the editable document and releases at
  `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/learn/+page.svelte:79-117`.

### Publish and immutable release

- Publish validates the current editable document, computes a generic document
  hash, and snapshots it at
  `apps/textbook-agent/backend/src/learn/publishing/release_routes.py:283-388`.
- `LearnReleaseModel` stores `document_json` and `document_hash`, but no
  SharedLessonDocument id, revision, or content hash, at
  `apps/textbook-agent/backend/src/infra/database/models.py:710-742`.
- The publish validator supports v2 ordered nodes through
  `apps/textbook-agent/backend/src/learn/publishing/publish_validation.py:33-54`,
  but does not verify SharedLessonDocument lineage.
- Frontend publish and release listing are called from
  `apps/textbook-agent/frontend/src/routes/units/[id]/lessons/[lessonId]/learn/+page.svelte:185-198`
  through
  `apps/textbook-agent/frontend/src/lib/learn/student/api/releases.ts:21-43`.

### Learn runtime and reload

- A learner instance is created from a `LearnRelease` at
  `apps/textbook-agent/backend/src/learn/runtime/runtime_routes.py:183-212`.
- Instance reload loads the release document and returns progress, attempts,
  and scores at
  `apps/textbook-agent/backend/src/learn/runtime/runtime_routes.py:295-365`.
- Attempt submission is server-authoritative and reloads the immutable release
  before evaluating the response at
  `apps/textbook-agent/backend/src/learn/runtime/runtime_service.py:388-569`.
- v2 interaction lookup is supported by
  `apps/textbook-agent/backend/src/learn/runtime/evaluation.py:462-525`.
- Passive section completion and rebuild progress load section and interaction
  data at
  `apps/textbook-agent/backend/src/learn/runtime/runtime_service.py:572-650`.
- The frontend instance page reloads the instance and release, submits attempts,
  and records visited sections at
  `apps/textbook-agent/frontend/src/routes/learn/instances/[instanceId]/+page.svelte:27-126`.

The runtime has a v2 compatibility gap: `_contracts_index` only indexes legacy
`document.blocks` at
`apps/textbook-agent/backend/src/learn/runtime/runtime_service.py:323-338`,
while v2 interactions are stored in `document.nodes`. Direct attempt evaluation
finds v2 nodes, but score aggregation and progress rebuild do not consistently
see v2 contract metadata. The cutover must fix this before deleting v1 support.

## Status and frontend dependencies

- The backend preparation status reads the preparation generation and projects
  path-specific realization rows at
  `apps/textbook-agent/backend/src/curriculum/routes.py:1360-1446`.
- `workspace_projection._artifact_projection` maps queued, running, failed,
  and ready states for the frontend at
  `apps/textbook-agent/backend/src/curriculum/workspace_projection.py:384-455`.
- The frontend derives the Learn artifact state and Builder identity from
  `workspace.learn` at
  `apps/textbook-agent/frontend/src/lib/curriculum/lessons/lesson-context.ts:72-121`.
- Current status identity is realization/output/builder based. There are no
  shared-document id, revision, or recomputed content-hash fields in the
  frontend status path.

The new status contract must expose the authoritative SharedLessonDocument
identity and the realization output identity together, including stage,
work-item progress, allowed actions, and source/output hashes. A ready Learn
artifact must not be inferred solely from `output_id` plus a generic document
hash.

## Cutover dependency order

1. **Shared source persistence and verifier.** Add the durable
   SharedLessonDocument record/repository and a read-only loader that verifies
   document id, revision, recomputed document hash, and approved Teaching Plan
   identity before any path work. Include required-media and QA readiness.
2. **Learn adapter.** Add the pure adapter that flattens ordinary shared nodes,
   preserves order/hierarchy/figure media, and maps each TaskAnchor from the
   frozen SharedTaskSpec. It must reject missing/stale/conflicting identities.
3. **Admission pinning.** Extend `NativeRealizationModel` admission and both
   Learn admission routes (`units_routes.py` and `native_http.py`) to pin and
   return SharedLessonDocument id/revision/hash. Duplicate requests must reuse
   the same identity; conflicting payloads must fail.
4. **Worker cutover.** Change `execute_learn_realization` and the worker to load
   the verified shared document and call the adapter. Remove Learn's sourcebook
   and ordinary composer/writer calls from the new path. Keep leases,
   checkpoints, cancellation, retries, and healthy sibling outputs intact.
5. **Output and Builder lineage.** Persist shared source identity on the Learn
   output and editable workspace. `get_or_create_native_learn_builder_lesson`
   must verify it on open/reload. Decide whether Builder PUT is a realization
   edit that creates a new shared revision or is blocked for generated ordinary
   nodes; it must not silently fork shared content.
6. **Publish and runtime.** Stamp SharedLessonDocument lineage into
   `LearnRelease`, validate it at publish, and make runtime v2 indexing,
   evaluation, progress, and section completion use ordered nodes and sections.
   Keep releases immutable and preserve interaction semantics.
7. **Frontend state and proof.** Add shared source identity to status/types and
   ensure Unit Learn preview, reload, retry, publish, and learner instance flows
   display and pass it through unchanged. Run the Learn end-to-end gate covering
   approval, open/reload, evaluation, progress, publish, and retry/cancellation.
8. **Zero-caller sweep and deletion.** Search static imports/calls, route
   registration, worker startup, dynamic imports, frontend callers, and tests.
   Add an architecture guard that Learn generation cannot import or invoke
   ordinary composer/writer modules. Only after the guard is clean should the
   old Learn ordinary calls, prompts, selection machinery, tests, and obsolete
   route be deleted.

## Contract and verification gaps

The following are blockers for a Phase 10 PASS:

1. **No durable SharedLessonDocument consumer identity.** The current codebase
   has no persistence/API field for SharedLessonDocument id, revision, or
   content hash in `NativeRealizationModel`, `GenerationModel`,
   `EditableLessonModel`, or `LearnReleaseModel`.
2. **Teaching Plan is still the Learn source.** The handoff verifies only the
   approved Teaching Plan at
   `realize_learn_handoff.py:123-153` and `:424-434`; no SharedLessonDocument
   is loaded or hash-recomputed.
3. **Ordinary content is generated again per path.** The Learn producer invokes
   the ordinary composer/writer and can regenerate semantic sourcebook/task
   artifacts, violating the authored-once boundary.
4. **Ready media/QA is not an admission gate.** The Learn handoff has no
   required-media or document-QA check before it admits or marks a run ready.
5. **Editable copy has no shared lineage.** Builder persistence copies and then
   permits arbitrary ordinary node updates; publish hashes that copy but cannot
   prove it came from the approved shared source.
6. **Release lineage is incomplete.** `LearnRelease` has only generic document
   hash plus old generation/path provenance. It cannot reject a stale or
   misbound SharedLessonDocument realization.
7. **v2 runtime aggregation is incomplete.** Direct v2 interaction lookup works,
   but `_contracts_index` and related progress aggregation index only v1 blocks.
8. **Duplicate Learn entry points remain.** The Unit route and `/v3` route both
   admit Learn; both must be cut over or one must be retired with a zero-caller
   proof.
9. **Direct Builder creation remains available.** `POST /builder/lessons`
   accepts generated-looking source types without shared lineage, and its
   route/tests must be classified before closeout.
10. **Old prompts and test callers remain.** `document-composer`,
    `document-writer`, `document_realizer`, and direct composer/writer tests are
    still present. Their deletion must follow a static and dynamic zero-caller
    sweep.

## Required focused tests and guards

Add or update tests in this dependency order:

- **Adapter contract:** shared id/revision/hash verification, recomputation,
  exact ordinary-node order, hierarchy and figure media, duplicate/misbound
  TaskAnchors, unsupported interaction mapping, and sibling isolation.
- **Admission:** duplicate admission, hash conflict, stale preparation, missing
  required media, QA failure, and stale lease/checkpoint/restart recovery. The
  existing admission/worker coverage starts at
  `apps/textbook-agent/backend/tests/application/test_p04_learn_worker.py`.
- **Cutover integration:** replace the old producer call in
  `tests/print_learn/test_p08_integration_gates.py` with the verified shared
  source and prove Learn failure does not mutate the shared source or Print
  sibling.
- **Builder/open/reload:** extend
  `apps/textbook-agent/backend/tests/routes/test_builder_lessons.py` and the
  frontend Unit Learn page test to assert shared identity verification on open,
  reload, and retry.
- **Runtime v2:** add ordered-node contract indexing and test attempt evaluation,
  section progress, rebuild, and reload through a published v2 release. Existing
  runtime gates are under `backend/tests/print_learn/test_p07_learn_runtime_gates.py`.
- **Publish:** extend release tests to require shared source identity and
  recomputed hash while retaining idempotent release behavior. Existing publish
  coverage is under `backend/tests/routes/test_learn_releases.py` and
  `backend/tests/routes/test_d6b_unit_learn_publish.py`.
- **Architecture guard:** fail if Learn generation imports or calls
  `document.composer`, `document.writer`, or the retired ordinary realizer after
  the adapter cutover; include dynamic route/worker registration checks.
- **Frontend gates:** preserve the Unit Learn page's create/poll/open/retry/
  publish flow and learner instance evaluation. Relevant tests are
  `frontend/src/routes/units/[id]/lessons/[lessonId]/learn/page.test.ts` and the
  learner instance route tests.

## Deletion proof

Deletion is safe only after the following evidence is recorded:

1. `rg` finds no production callers for `compose_document_plan`,
   `write_document_primitive`, `realize_learn_document`, or the ordinary Learn
   prompts.
2. Both Learn admission routes either call the SharedLessonDocument adapter or
   are removed and their frontend callers are absent.
3. Worker startup and retry/restart paths resolve only the shared-document
   pipeline.
4. Builder and publish paths carry and verify the source identity.
5. v2 runtime reload, evaluation, section progress, and release snapshots pass
   with immutable source/output siblings.
6. The full phase verification script, backend/frontend/page checks, and the
   architecture guard pass after deletion.

## TESTS

N/A for this read-only work package. No database, focused test, frontend check,
or full-suite command was run.

## FAILURE TESTS

N/A for this read-only work package. The required failure cases are listed in
the focused-test section above for the implementation phase.

## ZERO-CALLER/DELETION EVIDENCE

Not yet proven. Current evidence shows live ordinary Learn callers at
`native_production.py:387-472`, the old realizer reachability assignment at
`native_production.py:633-634`, two Learn admission routes at
`units_routes.py:441-500` and `native_http.py:198-230`, and direct Builder
creation at `builder/routes.py:360-432`. The deletion proof is the ordered
static/dynamic sweep in the section above.

## MIGRATIONS

N/A for this read-only work package. The audit identifies required model and
status migrations but does not modify migration code or the database.

## RISKS/QUESTIONS

- Decide whether direct Builder creation is a supported manual authoring
  product surface or must be removed/restricted during generated Learn
  cutover.
- Decide whether generated Builder edits create a new approved shared revision
  or are blocked for ordinary nodes. Silent mutation would break shared-source
  lineage.
- The `/v3/generations/{generation_id}/realize-learn` route remains registered;
  confirm its intended retirement date and caller owner before deleting it.
- Runtime v2 progress currently indexes only legacy blocks; the fix must land
  before v1 cleanup.

## COMMIT

Pending commit of this audit file; no other files are in scope.
