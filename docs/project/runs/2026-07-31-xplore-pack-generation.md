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
- [ ] P3: planner emits and persists cards
- [ ] P4: durable review halt and explicit resume
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

## Risks and follow-up

- P4, P6, and P9 are isolated high-risk phases and must remain independently reversible.
- The mission stop conditions apply if current session persistence cannot support restart-safe resume,
  the existing correction hint is not written in production, or one-plan/one-document assumptions
  exceed the handoff estimate by roughly double.
