# Feature: xplore pack generation

**Classification**: major
**Subsystems**: backend planning/execution/persistence/review/print, frontend studio/builder, contracts
**Branch**: `xplore`, cut from `v3`

## Source precedence

- `files (6).zip` supplies the corrected `MISSION.md` and `PROMPTS.md`.
- `files (5).zip` supplies `WORKED_EXAMPLE.md`, `TBG_XPLORE_HANDOFF.md`, and `UI_SPEC.md`.
- Current repository architecture and `agents/project.md` govern file placement and boundaries.
- Existing DeepSeek configuration, model selection, tiering, retries, and temperatures remain unchanged.

## Non-negotiables

- Item generation receives only the approved concept card fields, subject, level, and notation.
- Every variant in a pack references one shared item set.
- Planning always halts at `awaiting_review` until an explicit approval call.
- Teacher edits survive regeneration through the existing preserve-and-flag mechanism.
- No new provider, durable worker, deployment, tutor, learner telemetry, or adaptive routing.

## Progress

- [x] Read the mission, worked example, repository handoff, UI specification, and project rules
- [x] Publish and verify `lectio@0.6.0`
- [x] P1: contracts, dependency, and migration
- [x] P2: ConceptCard, Misconception, and VariantSpec models
- [x] P3: planner emits and persists cards
- [x] P4: durable review halt and explicit resume
- [x] P5: card review endpoints and Builder UI
- [x] P6: item generation behind the context wall
- [x] P7: diagnostic distractor mappings
- [x] P8: pack-level item review
- [x] P9: parallel variant fan-out and pack hub
- [x] P10: card-scoped QC rubric
- [x] P11: diagnostic answer-key print
- [x] P12: searchable card reuse
- [x] P13: regression and integration tests
- [x] Commit the photosynthesis fixture set
- [x] Run repository validation and architecture checks
- [x] Run the end-to-end local walkthrough on port 5173
- [x] Self-review and publish the branch

## Validation evidence

- Lectio GitHub release: `v0.6.0`
- npm registry: `lectio@0.6.0`, `latest=0.6.0`
- Lectio release workflow: passed package build, contract export, npm publish, and GitHub Release creation
- P1 registry sync: installed package, packaged contract, and synced backend contract all report `0.6.0`;
  the packaged `answer-key` component card is present.
- P1 migration: PostgreSQL upgrade → downgrade → upgrade passed for revision `20260731_0017`.
- P1 backend: 410 tests passed with one existing Pydantic field-shadow warning.
- P1 frontend: `svelte-check` found 0 errors and 0 warnings.
- P1 architecture guard: no violations.
- P2 planning suite: 36 tests passed; focused Ruff check passed.
- P2 backend: 410 tests passed with one existing Pydantic field-shadow warning.
- P3 real-provider gate: DeepSeek produced a 5-section Form 2 photosynthesis plan with
  3 plain sections and 2 card-backed sections. Both returned cards were persisted to
  PostgreSQL with observable objectives and 3 belief-level misconceptions each.
- P3 retry behavior: the first provider response exceeded the existing
  `transition_note` length contract; the existing structured-output retry corrected it
  without changing provider, model, temperature, tier, timeout, or retry settings.
- P3 planning suite: 36 tests passed; focused Ruff check passed.
- P3 backend: 410 tests passed with one existing Pydantic field-shadow warning.
- P3 architecture guard: no violations; no `known_pitfalls` references remain in
  `backend/src`.
- P4 halt gate: the generation row, chunked state, and document progress all persisted
  `awaiting_review`; entering the halt produced a new document `updated_at` version.
- P4 restart gate: a second Python process began with no in-memory generation owner or
  queue, loaded the persisted plan and context, and changed state to `stage2_running`
  only through the explicit approval endpoint. The endpoint rebuilt both transient
  values. The gate task was cancelled immediately and the fixture restored to
  `awaiting_review`.
- P4 focused lifecycle: 21 tests passed; frontend `svelte-check` found 0 errors and
  0 warnings; focused Ruff passed; no auto-approval patterns were found.
- P4 backend: 410 tests passed with one existing Pydantic field-shadow warning.
- P4 affected frontend suites: 3 files and 35 tests passed.
- P4 architecture guard: no violations.
- The all-frontend `npm test` command exceeded its five-minute harness ceiling without
  reporting a test failure; the Studio, V3 API, and V3 store suites touched by P4
  completed independently and passed.
- P5 real API gate: loaded 2 persisted photosynthesis cards, added a fourth
  misconception to one card, persisted it with `source: "teacher"` and
  `teacher_edited=true`, and resumed to `stage2_running` only through pack-level
  approval.
- P5 backend: 410 tests passed with one existing Pydantic field-shadow warning.
- P5 frontend: `svelte-check` found 0 errors and 0 warnings; production build passed;
  3 affected route/state files and 36 tests passed.
- P5 architecture guard: no violations. Card-review markup is confined to Builder;
  `V3Canvas.svelte` contains none.
- P6 wall gates: `SectionBrief` no longer has `question_briefs`; the item executor
  accepts exactly one `ConceptCard`; it imports no component, section-brief, or
  generated-section types; and its prompt contains no generated-content channel.
- P6 execution: approval generates one five-item diagnostic set per approved card,
  persists it under the pack, recomputes misconception coverage and unmapped-option
  counts, and preserves existing item rows rather than overwriting them.
- P6 real-provider gate: the unchanged premium slot resolved to
  `openai_compatible/deepseek-v4-pro`; one photosynthesis card produced 5 items with
  exactly one correct option each, coverage `M1=1, M2=2, M3=1`, and no missing
  misconception coverage.
- P6 backend: 416 tests passed with one existing Pydantic field-shadow warning.
- P6 focused execution/planning suite: 38 tests passed; Ruff passed.
- P6 architecture guard: no violations.
- P7 contracts: `ItemOption.diagnoses` and the pack-level `QuestionBrief` item
  shape now live in planning models; `SectionBrief` remains unable to carry items.
- P7 real database gate: the photosynthesis pack persisted 10 items, five for each
  approved card, all under the same pack id. Every non-null diagnosis resolved to
  a real misconception on its card; 27 unmapped distractors remained `null`.
- P7 review signaling: both real card batches reported their unmapped-option counts
  and neither silently missed required misconception coverage.
- P7 backend: 416 tests passed with one existing Pydantic field-shadow warning.
- P7 item/lifecycle suite: 27 tests passed after isolating one transient full-suite
  harness hang; the clean full rerun passed.
- P8 API: pack-scoped item review, teacher item patching, and one-card regeneration
  endpoints are ownership-scoped. Coverage, missing misconceptions, unmapped options,
  stale state, and teacher-edited state are explicit response fields.
- P8 preservation gate: regeneration refreshes unedited rows but retains a
  teacher-edited item and marks it stale so the difference remains visible.
- P8 real API gate: the photosynthesis pack returned 2 cards and 10 items under one
  pack, surfaced 17 unmapped distractors, and reported no missing coverage.
- P8 frontend: pack-level `/packs/[pack_id]/items` review supports card switching,
  item text/tag editing, coverage badges, untagged warnings, stale warnings, and
  scoped regeneration. Builder links out to the pack surface.
- P8 backend: 419 tests passed with one existing Pydantic field-shadow warning.
- P8 frontend: `svelte-check` found 0 errors and 0 warnings; focused API suite passed
  3 tests; production build passed with existing Rollup/chunk warnings.
- P9 model cardinality: `VoiceSpec` now belongs to `VariantSpec`; a coordinator plan
  creates one generation row per teacher-labelled learner group while retaining one
  pack-scoped item set.
- P9 execution: approval generates the shared items once and fans variant expansion
  out concurrently. Child runs explicitly skip item generation, persist independent
  state/documents, and expose retry-one and variant removal without blocking siblings.
- P9 UI: the wizard captures up to three labelled learner groups and shows a no-write
  confirmation with booklet count and rough duration. The pack hub shows per-variant
  progress/issues, gates editors until every live variant has landed or failed, links
  the shared quiz, and supplies a landed-variant print picker.
- P9 validation: focused backend planning/lifecycle suites passed 30 tests; the item
  review suite passed 3 tests in isolation after the combined SQLite harness hit its
  known lock. Frontend `svelte-check` found 0 errors and 0 warnings; 50 focused tests
  passed. Ruff, compile, diff, cardinality grep, and architecture checks passed.
- P10 QC: every generated card/variant is checked on the existing fast tier for its
  objective, each approved misconception, scope/avoid list, and notation. Failures
  name the card and failed criterion, persist `repair_target_id` plus
  `qc_correction_hint`, and appear in the variant-scoped issues surface.
- P10 repair: the existing section-writer work orders are filtered by the failed
  card ID, regenerated with the QC hint, patched into the document, and rechecked.
  The production visual-QC path was also confirmed to write its correction hint.
- P10 validation: 43 focused review, assembly, and execution tests passed; Ruff and
  compile checks passed; frontend `svelte-check` found 0 errors and 0 warnings.
- P11 print: generation documents are augmented at read/export time with the same
  non-stale pack item rows, so every variant receives byte-equivalent shared quiz
  content without copying item ownership into a variant.
- P11 key: pack items and card misconceptions map into Lectio's `answer-key`
  contract. Diagnostic copy uses `Chose "{option}" → consistent with:
  {misconception}` and explicitly labels tags as hypotheses.
- P11 pack route: `/packs/{pack_id}/print` prints selected landed booklets together
  and appends exactly one shared diagnostic key; it also supports key-only output.
- P11 validation: 15 PDF/item tests passed after retaining the established individual
  print-route contract; the Lectio adapter suite passed 8 tests. Ruff and frontend
  type checks passed with no errors or warnings.
- P12 library: `GET /v3/cards` searches the current teacher's cards by slug, title,
  or objective and collapses repeated slugs to the latest owned copy.
- P12 reuse: pack card review can replace a target card from the library. Objective,
  title, prerequisites, and misconception beliefs are copied; source card and pack
  IDs are persisted as provenance, dependent items become stale, and the durable
  structural-plan snapshot is synchronized before variant generation.
- P12 migration: PostgreSQL revision `20260731_0018` passed upgrade → downgrade →
  upgrade. Focused Ruff/compile and frontend checks passed with 0 errors/warnings.
- P13 contracts: automated tests prove sibling variant failure isolation, one shared
  pack-owned item set across variants, restart-safe `awaiting_review`, preservation
  of teacher-edited misconceptions during plan regeneration, and rejection of any
  generated-content channel at the item-executor wall.
- P13 QC: complete card/variant rubrics pass, while omitted misconception checks and
  mismatched repair verdicts fail deterministically.
- P13 fixture: the committed Form 2 photosynthesis pack is pinned to Lectio contract
  `0.6.0`, two concept cards, valid diagnostic mappings, and two labelled variants.
  The P13 focused suite passed 15 tests; Ruff passed.
- Final backend gate: Ruff passed, the architecture guard reported no violations, and
  the full suite passed 428 tests with one existing Pydantic field-shadow warning.
- Final frontend gate: `svelte-check` reported 0 errors and 0 warnings. The first full
  Vitest run passed 277 tests and exposed three Lectio `0.6.0` compatibility
  expectations; all three were corrected. Focused lockfile and plan-action reruns
  passed. The package-smoke rerun and production build later stalled in the Windows
  harness without a compiler or assertion diagnostic; the port-5173 development
  runtime remained healthy.
- Live walkthrough: Google sign-in, Studio setup, real DeepSeek narrowing/planning,
  the durable `awaiting_review` halt, Builder concept-card review, explicit approval,
  shared diagnostic generation, and parallel variant fan-out all completed on
  `http://127.0.0.1:5173`.
- Live pack `929af699-d012-41b7-9738-1320a172c787` landed both `Support` and
  `Extension` booklets. The pack hub reported `Pack ready`, exposed both editors,
  unlocked the print picker, and retained one shared five-question diagnostic set.
- Live diagnostic coverage reported `M1` three times, `M2` three times, and `M3`
  twice. Every item had one correct option; five deliberately unmapped distractors
  were surfaced as untagged rather than silently assigned.
- Live print verification rendered both selected booklets, both generated Elodea
  diagrams, the shared diagnostic, and its correct-answer markings in one pack.
- Local runtime assets generated during the walkthrough remain available under
  `backend/data/images/` and are excluded from this worktree locally.
- Branch `xplore` was pushed to `origin/xplore`.

## Deployment environment handoff

- No new Xplore-only runtime secret was added.
- `LECTIO_TOKEN` belongs in GitHub repository secrets for the Lectio publish workflow
  only. The Textbook deployment consumes the published `lectio@0.6.0` package and
  baked-in `0.6.0` contracts; it does not need that token.
- Backend production must set `LECTIO_CONTRACTS_DIR=/app/backend/contracts` and
  `RUN_MIGRATIONS_ON_STARTUP=true`.
- The validated provider posture uses `DEEPSEEK_API_KEY` with the `V3_FAST_*`,
  `V3_STANDARD_*`, and `V3_PREMIUM_*` DeepSeek values documented in
  `backend/.env.example`, plus `V3_STAGE2_PARALLEL=true`.
- `ANTHROPIC_API_KEY` remains required while the configured visual-QC slot uses
  Anthropic. Generated images also need the selected provider key and production
  `GCS_*` storage values.
- Production frontend deployment needs `PUBLIC_API_URL` and
  `PUBLIC_GOOGLE_CLIENT_ID`. Railway needs the same Google client ID as
  `GOOGLE_CLIENT_ID`, plus the exact frontend URL in `FRONTEND_ORIGIN`,
  `LESSON_BUILDER_PUBLIC_URL`, and `PDF_RENDER_BASE_URL`.
- The canonical deployment matrix is in `docs/project/SETUP.md`.

## Risks and follow-up

- P4, P6, and P9 are isolated high-risk phases and must remain independently reversible.
- The mission stop conditions apply if current session persistence cannot support restart-safe resume,
  the existing correction hint is not written in production, or one-plan/one-document assumptions
  exceed the handoff estimate by roughly double.
- The printable live pack surfaced Lectio schema-capacity warnings for one hook option
  count, two five-step worked examples, and one long hint. These are visible quality
  warnings, not contract failures; the pack rendered successfully.
- A clean full frontend test/build rerun should be repeated in CI or a non-stalling
  harness to replace the focused rerun evidence above.
