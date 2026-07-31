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
- [ ] P9: parallel variant fan-out and pack hub
- [ ] P10: card-scoped QC rubric
- [ ] P11: diagnostic answer-key print
- [ ] P12: searchable card reuse
- [ ] P13: regression and integration tests
- [ ] Commit the photosynthesis fixture set
- [ ] Run repository validation and architecture checks
- [ ] Run the end-to-end local walkthrough on port 5173
- [ ] Self-review and publish the branch

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

## Risks and follow-up

- P4, P6, and P9 are isolated high-risk phases and must remain independently reversible.
- The mission stop conditions apply if current session persistence cannot support restart-safe resume,
  the existing correction hint is not written in production, or one-plan/one-document assumptions
  exceed the handoff estimate by roughly double.
