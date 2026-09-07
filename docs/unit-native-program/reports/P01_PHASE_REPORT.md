# Phase report

Phase: P01 — Publish authoritative capability catalogues
Status: PASS
Starting commit: `8642226` (P00 PASS head) / ending commit: `5a73e31` — the last code commit, and the revision every gate below was run on. This report is committed on top of it and changes no code.
Dirty files preserved: `.tmp/**` scratch scripts and logs, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/`, `.claude/settings.local.json` — none committed.

Contract/spec/prompt versions:

| Artefact | Version |
|---|---|
| Instructional intent vocabulary (`@lectio/contracts`) | 1.0.0, synced from Print intent catalogue 1.1.0 (all 32 canonical ids) |
| Learner action vocabulary (`@lectio/contracts`) | 1.0.0 (13 actions) |
| Shared teaching view | 1.0.0 (31 teaching-selectable intents; `answer-key` is excluded because it is not a teaching choice) |
| Print intent catalogue | 1.1.0 (unchanged) |
| Print object catalogue | 1.2.0 (was 1.1.0) |
| Print generated views (selection / writer / intent-object map) | 1.0.0 |
| Learn capability catalogue | 1.0.0 (43 capabilities) |
| Learn generated views (teaching / selection / writer / runtime) | 1.0.0 |
| Learn capability manifest | 1.0.0 |

Dependencies verified: P00 is PASS at `5d15639` reviewed sha with FE gates restored at `55a657c`. The P00 capability inventory rollup (10 interaction shells incomplete, 29 content components generation-ready, 2 manual-only, 2 incomplete, 8 print forms generation-ready, 2 incomplete) is reproduced exactly by the generated Learn manifest and Print selection view, so the two are consistent at this revision.

## Changes and purpose

### Shared vocabulary — `@lectio/contracts` (new package)

A neutral package with no Svelte, Python or renderer dependency, so a planner, a backend exporter and a test fixture can all depend on the same words. It owns:

- The 32 canonical instructional intents, synced from `packages/lectio-page/contracts/intent-catalogue.v1.json`. No id was invented, renamed or dropped; the exporter copies them and a test fails if the copy diverges from the Print catalogue. The generated teaching view publishes the 31 that are teaching-selectable — `answer-key` is a Print output obligation, not something a teaching plan chooses.
- A 13-entry learner action vocabulary describing what the learner is asked to *do* (`select-one`, `order-items`, `complete-missing-values`, `match-pairs`, `classify-items`, `enter-number`, `enter-text`, `identify-region`, `place-labels`, `compare-without-response`, `read-explanation`, `produce-extended-response`, `select-many`). Print may satisfy an action on paper and Learn interactively, so the vocabulary never names how.
- A generated teaching view: intents with their neighbouring boundaries, plus the learner actions. It carries no page object id, no Learn component or interaction id, no payload schema and no capacity limit. `src/native-inventory.ts` lists the native ids as machine-checkable data, so adding native inventory means adding it to the guard too and the check cannot go stale.

### Print — `@lectio/page`

- Every object record in the object catalogue is now complete: `payload_schema_ref` into the exact document subschema, `supported_actions` in canonical action vocabulary, `form_selectable` (with `not_form_selectable_because` for `heading` and `answer-key`), per-field `writer_guidance`, and `negative_cases`. Catalogue version 1.1.0 → 1.2.0.
- Three generated views are exported and hashed into the contract manifest:
  - `generated/form-selection-view.v1.json` — eligible form ids, purpose, supported intents/actions, choose/reject test, capacity, placement, whether an asset is required and whether an answer key is produced. It carries no `content_schema`, no resolved payload schema, no writer guidance and no negative cases.
  - `generated/form-writer-view.v1.json` — the exact payload contract per form, with the payload subschema resolved from `lectio-document-v2.schema.json` rather than restated.
  - `generated/intent-object-map.v1.json` — the authored `intent → objects` direction copied verbatim, plus the generated `object → intents` reverse direction and `selectable_intent → form-selectable objects`. The reverse maps are never hand-maintained.
- Existing Print machinery is untouched: render, placement, validation and stylesheet-parity suites pass unchanged.

### Learn — `@lectio/learn`

- **Short-response is no longer the numeric evaluator.** `evaluateInteraction` aliased `short-response` to `evaluateNumeric`, so a written answer was scored by comparing it to a number. It now has its own two modes: `accepted-answers` compares the normalized response (trim, whitespace collapse, case fold) against a declared set, and `teacher-review` returns `pending-review` with zero earned score. `validateInteractionContract` rejects a missing mode, an empty accepted-answer set, answers that collide after normalization, and `teacher-review` paired with completion on correctness.
- **Config and response failures are separated.** A malformed config raises `InteractionConfigError` (an authoring error); an unknown, duplicate, mis-counted or non-finite response raises `InteractionResponseError` rather than being scored. An impossible response cannot produce evidence.
- **The classic adapters run the shared evaluators.** `QuizCheck.svelte` and `FillInTheBlank.svelte` now build a full contract and call `evaluateInteraction`, so they get the same validation and scoring as every other kind instead of a private path.
- **`teachingIntent` and web hints are exported.** Both were authored on every module and dropped on the way out. The exported component card now carries `teaching_intent` and `web` (explicitly `null` when no hints are authored, so "no hint" is distinguishable from "not exported"), and the planner index gained a generated `intent_map`.
- **The capability catalogue is published.** Ten interaction kinds are authored by hand with real selection, schema, runtime and evaluation semantics; 33 content components are *projected* from the component registry and export policy, so the catalogue cannot claim a readiness the export policy contradicts. `image-choice` is a presentation variant of `choice`, not a kind. Four views are generated (teaching, selection, writer, runtime) plus a manifest hashing the exact bytes of each.
- **`@lectio/learn/capabilities` is a renderer-free entry point.** It re-exports the catalogue, the view builders and the evaluator surface, so a Node consumer can select and score without pulling Svelte into a server or a script.

### Readiness, stated honestly

| Group | Count | Readiness / availability | Why |
|---|---|---|---|
| Interaction kinds with text/auto scoring (`choice`, `multi-select`, `fill-blank`, `numeric`, `short-response`, `match-pairs`, `classify`, `sequence`) | 8 | `planned` / `incomplete` | Each has a closed payload schema, a deterministic evaluator, a keyboard-operable renderer and — from this phase — a contract export. None is registered in a native selection policy and none has a Builder editor, so no generation run can choose or repair one. Claiming `generation-ready` would make a UI shell look like a generation capability. |
| `image-hotspot`, `drag-label` | 2 | `planned` / `unavailable` | No coordinate authoring tool and no asset-region model, so regions and targets cannot be produced or verified against a real asset. Each also states its own extra gap: the shared evaluator does not validate a selected region against the declared region set, and the drag-label renderer delegates to the text match-pairs shell and never draws the asset. |
| Content components eligible for the content contract and status `stable` | 29 | `generation-ready` / `available` | Schema, renderer, content contract, contract export and consumer selection support all present. |
| `image-block`, `video-embed` | 2 | `manual-only` / `available` | Teacher-attached media, deliberately excluded from generation selection. Present in the catalogue with a reason rather than hidden. |
| `simulation-block` | 1 | `planned` / `incomplete` | Status `beta`: exported and selectable, not yet proven stable enough to promote. |
| `glossary-inline` | 1 | `planned` / `unavailable` | Excluded by export policy; inline-only, so it has no section payload to resolve. |

Every non-available record carries non-empty `blocking_reasons` and a non-empty `path_to_readiness`, and `validateCapabilityRecords` fails the export if either is missing.

These counts reproduce the P00 `CAPABILITY_INVENTORY.json` rollup exactly (10 interaction shells not ready, 29 content generation-ready, 2 manual-only, 2 content incomplete). The P00 inventory stays as the P00 snapshot; `packages/lectio-learn/contracts/learn-capabilities.v1.json` and `packages/lectio-page/contracts/generated/form-selection-view.v1.json` are the live, regenerated readiness inventories from here on.

## Gate evidence

All commands were run on `5a73e31`. Evidence files are under `docs/unit-native-program/evidence/mocks/p01/`. Every file records the exact command, working directory and exit code. **All evidence in this phase is from deterministic unit/integration tests and real exporter subprocesses — no live provider run is claimed.**

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P01-K01 | `pnpm exec vitest run tests/regeneration.test.ts` in `packages/lectio-contracts` | Real exporter runs twice byte-identical apart from timestamp; a deliberate source-field change propagates into the generated teaching view | 4 passed, exit 0 | PASS | `k01-contracts-regeneration.txt` |
| P01-K01 | `pnpm exec vitest run src/lib/catalogue/regeneration.test.ts` in `packages/lectio-page` | Reproducible; a deliberate `choose_when` + capacity change reaches the selection view; a writer-guidance change reaches the writer view; marking a form unselectable drops it from the selection view | 5 passed, exit 0 | PASS | `k01-page-regeneration.txt` |
| P01-K01 | `pnpm exec vitest run scripts/export-capabilities.test.ts` in `packages/lectio-learn` | Exporter emits 5 views + manifest hashing the written bytes; two runs identical; a deliberate `choose_when` change in `interactions.ts` reaches the generated catalogue and moves the manifest hash; restoring the source restores the bytes | 3 passed, exit 0 | PASS | `k01-learn-regeneration.txt` |
| P01-K02 | `pnpm exec vitest run src/lib/catalogue/views.test.ts` in `packages/lectio-page` | Every object record complete; every `payload_schema_ref` resolves; every intent's `valid_objects` names a real object; reverse map agrees with the authored direction in both directions; the reference fixture validates against the exact per-object payload schemas under Ajv | 17 passed, exit 0 | PASS | `k02-page-views.txt` |
| P01-K02 | `pnpm exec vitest run tests/vocabulary.test.ts` in `packages/lectio-contracts` | The 32 intent ids, labels, roles and cognitive jobs are a faithful copy of the Print catalogue; learner actions are well-formed | 7 passed, exit 0 | PASS | `k02-contracts-vocabulary.txt` |
| P01-K02 | `pnpm exec vitest run src/lib/learn/capabilities/content.test.ts` in `packages/lectio-learn` | Every capability's intents and actions exist in `@lectio/contracts`; the projection agrees with the export policy about who is selectable | 6 passed, exit 0 | PASS | `k02-learn-content-projection.txt` |
| P01-K03 | `pnpm exec vitest run src/lib/learn/capabilities/golden.test.ts src/lib/learn/interaction-contract.test.ts` | Unknown/empty/duplicate response ids rejected; wrong blank and order counts rejected; `correct_option_id` outside the option set rejected; duplicate config ids rejected; numeric `NaN`, `±Infinity` and negative tolerance rejected in both config and response, through evaluation *and* `validateInteractionContract`; a numeric config on `short-response` is an authoring error | 43 passed, exit 0 | PASS | `k03-k04-learn-golden.txt` |
| P01-K04 | `pnpm exec vitest run src/lib/learn/capabilities/golden.test.ts src/lib/learn/interaction-contract.test.ts` | A golden case per activated kind with the exact expected outcome and score; partial scoring proven for `multi-select`, `fill-blank`, `match-pairs`, `classify` and `sequence`; attempt limits refuse a third attempt against a two-attempt policy and refuse a retry after correct; unlimited practice honoured; `partial_scoring` claims checked against the evaluator each record actually names | 43 passed, exit 0 | PASS | `k03-k04-learn-golden.txt` |
| P01-K04 | `pnpm exec vitest run src/lib/learn/interaction-shells.keyboard.test.ts` | Renderer goldens: each shell evaluates and is keyboard-operable, including the config-only contract check for the newer kinds | 12 passed, exit 0 | PASS | `k04-learn-renderer-goldens.txt` |
| P01-K05 | `pnpm exec vitest run src/lib/learn/capabilities/consumer-fixture.test.ts` | A fixture with one import site — the published capability entry point — walks selection → writer → runtime → scored response; no incomplete, unavailable or manual-only capability appears in the generation-ready view; a static walk of the entry point's import graph finds no `.svelte` import; `./capabilities` is present in the published exports map | 7 passed, exit 0 | PASS | `k05-learn-consumer-fixture.txt` |
| P01-K06 | `pnpm exec vitest run tests/teaching-view.test.ts` in `packages/lectio-contracts` | The shared teaching view names no page object, Learn component or interaction kind (exact-match against every native id, substring against the identifier-shaped ones), and carries no schema, capacity or payload key | 9 passed, exit 0 | PASS | `k06-contracts-teaching-view.txt` |
| P01-K06 | `pnpm exec vitest run src/lib/learn/capabilities/views.test.ts` | The Learn teaching view names only canonical intents/actions and no capability id; the selection view omits `payload_schema`, `field_guidance`, `examples`, `negative_cases`, `response_schema` and every answer-bearing key while keeping purpose, choose/reject and capacity; the runtime view carries no writer guidance | 17 passed, exit 0 | PASS | `k06-learn-view-separation.txt` |
| P01-K06 | `pnpm exec vitest run src/lib/catalogue/views.test.ts` in `packages/lectio-page` | The Print selection view omits full writer payload contracts; the writer view holds them separately | included in the 17 passing above, exit 0 | PASS | `k02-page-views.txt` |

### Supporting suite runs (not gate substitutes)

| Command | Result | Evidence |
|---|---|---|
| `pnpm run test` in `packages/lectio-contracts` | 20 passed, exit 0 | `contracts-vitest.txt` |
| `pnpm run check` in `packages/lectio-contracts` | exit 0 | `contracts-tsc.txt` |
| `pnpm run test` in `packages/lectio-page` | 63 passed, exit 0 | `page-vitest.txt` |
| `pnpm run check` in `packages/lectio-page` | 0 errors, 0 warnings, exit 0 | `page-svelte-check.txt` |
| `pnpm run test` in `packages/lectio-learn` | 196 passed, exit 0 | `learn-vitest.txt` |
| `pnpm run check` in `packages/lectio-learn` | 0 errors, 2 pre-existing CSS warnings, exit 0 | `learn-svelte-check.txt` |
| `python -m pytest -q tests/contracts` in `apps/textbook-agent/backend` | 6 passed, exit 0 | `backend-contracts-pytest.txt` |

## Failure attribution and repairs

Three failures were found by the new gates rather than by inspection, and each was repaired at the responsible owner:

1. **`short-response` writer guidance incomplete** — the K06 writer-view test asserts per-field guidance for every field in the payload schema and failed on `max_words`. Repaired in the capability record, not by relaxing the assertion.
2. **`@lectio/contracts` regeneration hash mismatch** — the exporter was rewriting `learner-actions.v1.json`, an *authored* file, so its hash depended on serialization rather than on source. The exporter now writes only generated files and hashes the authored file from its committed location.
3. **`validate-component` dereferenced an optional field** — `module.print` is optional and deprecated (Print layout is owned by `@lectio/page`), but the print checks ran unconditionally, producing 12 type errors. The checks moved into a guarded helper. No validation was removed.

No stage/realization ids are involved: this phase produces no runs.

## Migration and compatibility

- No DB migration. No document or release format changed.
- Print object catalogue 1.1.0 → 1.2.0 is **additive**: every existing key is preserved and the new keys (`payload_schema_ref`, `supported_actions`, `form_selectable`, `writer_guidance`, `negative_cases`, `requires_asset`, `produces_answer_key`) are new. The backend contract parity test was updated to the new version and passes.
- Learn content contract export is **additive**: `teaching_intent`, `web` and `planner_index.intent_map` are new keys. Existing consumers (`compile_orders.py`, `section_writer.py`, `deterministic_checks.py`, `learn/contracts/lectio.py`) read by key and are unaffected; backend contract tests pass.
- `short-response` is the one behavioural change. The old shape (`{ value, tolerance }`) never produced a defensible score, so it is rejected rather than silently migrated; the capability record documents the migration under `compatibility.migration`. No committed content authored a `short-response` contract, so no data needs backfilling.
- Backend contract copies were resynced with `apps/textbook-agent/tools/update_lectio_contracts.py` (`LECTIO_PACKAGE_DIR` pointed at `packages/lectio-learn`, since the app frontend does not install `@lectio/learn` into `node_modules` in this workspace).
- Rollback route: the last passing revision is `8642226`; the P01 commits are independent and revertable in reverse order.
- No public npm publication was performed.

## Decisions or deviations

| ID | Question | Decision | Rationale | Affected gates |
|---|---|---|---|---|
| D-005 | How should `@lectio/contracts` be consumed inside the monorepo? | Source-only package: `exports` point at `src/index.ts`, no build step | Keeps the neutral package free of a toolchain and of any Svelte/Python dependency; workspace consumers transform TS already | P01-K06 |
| D-006 | Should Learn content capabilities be authored or generated? | Generated from the component registry and export policy | Section components already carry metadata, a Zod schema, field contracts and an export policy; a second hand-written catalogue would drift, and the contract requires generated indices | P01-K01, P01-K02 |
| D-007 | May a text interaction claim `generation-ready` because it has a schema and an evaluator? | No — `planned` / `incomplete` with a stated path until a native selection policy can choose it and a Builder editor can repair it | A shell with an evaluator is not a generation capability; the pack requires readiness to reflect what a consumer can actually run | P01-K05 |
| D-008 | How is "no native inventory in the teaching view" checked when native ids overlap ordinary English (`prose`, `table`, `numeric`)? | Exact key/value equality against every native id, plus free-text substring search restricted to identifier-shaped (hyphenated) ids; `classify`, `sequence` and `match-pairs` are recorded as shared-by-design | Substring-matching `numeric` inside "Give a numeric answer" is a false positive; hyphenated ids never occur in natural prose, so a hit there is a real leak | P01-K06 |
| D-009 | `classify` with multiple categories per item? | Single-category membership only, declared in the record and enforced by the evaluator | The shared evaluator scores item→category as source→target pairs, so a second category for the same item is a duplicate source and is rejected; declaring multi-category support would be aspirational | P01-K03, P01-K04 |
| D-010 | Spatial interactions? | Stay `unavailable`, with per-capability blocking reasons and a path to readiness | Pack constraint: spatial stays unavailable while authoring is incomplete. Regions cannot be verified against a real asset today | P01-K05 |
| D-011 | `short-response` contracts authored against the old numeric shape? | Reject rather than silently migrate; document the migration on the capability record | The old shape never produced a defensible score for a written answer, and no committed content authored one | P01-K03 |

No acceptance criterion was weakened. Examples in the pack JSON were treated as illustrative only; the examples in the capability records are authored for the real schemas.

## Remaining risk / blocked access

1. **Full backend pytest suite cannot run in this environment.** 112 collection errors, all rooted in `ModuleNotFoundError: No module named 'pydantic_ai'` in the ambient Python. This is pre-existing and unrelated to P01 (it reproduces on files this phase never touched). The contract-parity tests, which are the ones P01 can affect, collect and pass. *Action:* install the backend dependency set (`apps/textbook-agent/backend` requirements) into the interpreter used for gates before P02, or run backend gates in the project's virtualenv.
2. **No interaction kind is selectable yet, so no end-to-end interaction claim can be made.** This is the intended P01 state, not a gap in the gate evidence: P04 registers native selection, P06 adds Builder repair and P07 proves runtime persistence. Until then the generation-ready Learn surface is content components only.
3. **Spatial authoring is absent.** `image-hotspot` and `drag-label` cannot be authored, verified or offered. Unblocking needs an asset-region model that binds an existing asset id to named regions with a declared coordinate system, plus the authoring surface that produces them.
4. **`@lectio/learn` is not installed into the app frontend's `node_modules` in this workspace**, so the backend contract sync needs `LECTIO_PACKAGE_DIR`. Harmless for gates, but worth fixing before any pipeline relies on the default path.

## Next phase

P02 — shared teaching preparation. The vocabulary and the teaching view it must produce plans in are now published and guarded, so P02 can start against `5a73e31`.

Next command: read `docs/unit-native-program/pack/phases/P02_*.md` and `pack/contracts/02_*.md`, then confirm P01 gates are PASS at `5a73e31`.
