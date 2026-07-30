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
- [ ] P5: card review endpoints and Builder UI
- [ ] P6: item generation behind the context wall
- [ ] P7: diagnostic distractor mappings
- [ ] P8: pack-level item review
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

## Risks and follow-up

- P4, P6, and P9 are isolated high-risk phases and must remain independently reversible.
- The mission stop conditions apply if current session persistence cannot support restart-safe resume,
  the existing correction hint is not written in production, or one-plan/one-document assumptions
  exceed the handoff estimate by roughly double.
