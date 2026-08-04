# Xplore V2 Complete Build Plan

## Summary

The product is technically strong through Phase 5, but users can only see the legacy Studio.
The unit/path architecture therefore cannot yet be exercised as a coherent product. The human
owner has authorized completing Phases 6 through 13 before running the approximately 30-lesson
comparative study.

This changes the timing of the human evaluation, not the engineering quality bar. Every phase
must still pass its automated, migration, architecture, and browser gates before the next phase
starts. Human evaluation and taxonomy/skeleton tuning happen against the finished beta workflow.

## Human decision — build-through authorization

On 2026-07-31, the product owner decided:

- the approximately 30-lesson shadow review is no longer a prerequisite for building the rest of
  Xplore V2;
- Phases 6 through 13 are authorized;
- the complete unit/path/schedule/resource/results experience will be built first;
- the human comparison study will then be run against the complete experience;
- findings may tune classifiers, skeletons, prompts, and defaults without replacing the durable
  concept, path, objective-ownership, provenance, or projection architecture.

Skeleton authority is scoped to the new unit/path workflow. Existing Studio generation remains
available and unchanged as the compatibility and rollback path until the final rollout decision.

## Target state

A signed-in teacher can:

1. create a unit and its scope contract;
2. plan, inspect, edit, split, merge, skip, reorder, replan, and approve a concept path;
3. preview the skeleton and differentiated shapes for each path lesson;
4. prepare one path lesson through the existing review, generation, QC, Builder, Lectio, and PDF
   machinery without objective drift;
5. group path lessons into teaching periods without changing concept identity;
6. define support, core, and extension groups through declared structural toggles;
7. compose deterministic lesson, homework, revision, flashcard, quiz, answer-key, and unit-exam
   resources from approved material;
8. record lesson actuals and aggregate option-count marks into misconception summaries; and
9. move between Units and Legacy without losing existing packs or teacher edits.

## Locked constraints

- Preserve all nine Xplore invariants from the controlling goal.
- Never pass lesson count or lesson duration to path decomposition.
- The approved path lesson owns its objective; every generated artifact verifies its hash.
- A skipped lesson remains stateful and visible to prerequisite analysis.
- Scheduling may use time but may not mutate the path.
- Shared diagnostic items remain pack-owned and identical across variants.
- Resource projection uses zero model calls when deterministic selection can produce it.
- Existing Studio, packs, Builder, Lectio, PDF, and generation routes remain operational.
- No destructive migration and no forced conversion of existing packs.
- No learner accounts or individual learner claims are introduced.

## Delivery strategy

Build as a sequence of independently releasable vertical slices. Keep the new experience behind a
server-controlled capability flag until Phase 13, but enable it for authorized beta users so the
real production workflow is visible and testable. A failure in V2 must not block Legacy Studio.

Each slice includes persistence, service/API contracts, frontend states, tests, observability, and
documentation. Do not create backend-only phases that leave another invisible feature surface.

## Phase 6 — Complete the path-to-Xplore bridge

Although Phase 5 delivered the initial `:prepare` bridge, Phase 6 makes it production-complete.

### Work

- Confirm preparation consumes the approved path version, unit scope, canonical concept, earlier
  established capabilities, group definitions, knowledge type, skeleton, and terminology.
- Add explicit status and regenerate/invalidation contracts.
- Persist the path lesson-to-pack/generation relationship and idempotency key.
- Reuse the existing durable `awaiting_review` halt and teacher-edit preservation behavior.
- Carry immutable provenance and objective hash through card approval, generation, Builder, and
  export.
- Surface actionable states for scope review, prerequisite gaps, skeleton conflicts, variant
  overflow, and preparation invalidation.

### Gate

- One approved fixture lesson prepares, pauses for review, resumes, generates, opens in Builder,
  and exports through Lectio/PDF.
- Repeated prepare is idempotent; explicit regenerate creates a traceable revision.
- Objective or slot-sequence drift is rejected.
- The unreachable Grade 8 path still cannot be approved or prepared.

## Phase 7 — First visible end-to-end unit slice

### Work

- Add authenticated frontend API contracts and typed models for units, paths, previews, preparation,
  and errors.
- Add `Units` navigation and unit list/create pages.
- Add a unit workspace with path list and lesson inspector.
- Support plan, edit, reorder, split, merge, skip, replan, approve, skeleton preview, and prepare.
- Show real progress and failure states; never display a partial path as complete.
- Link prepared lessons into the existing review/Builder flow and back to the unit.
- Keep `Legacy Studio` explicitly available in navigation.

### Gate

- Browser acceptance completes create unit -> plan -> edit -> approve -> prepare -> review ->
  generate -> open artifact.
- Keyboard, narrow-screen, loading, empty, error, and retry states are covered.
- Ownership checks prevent one user from reading or mutating another user's unit.

## Phase 8 — Full path workspace

### Work

- Add path-version history and clear draft/approved/superseded states.
- Add prerequisite and external-prerequisite visualization.
- Add completeness, risk, merge-critic, and destination-reachability panels.
- Add focused lesson editing for objective, must-establish, exclusions, type, and approved deviations.
- Add path-level status aggregation for unprepared, awaiting review, generating, ready, warning,
  failed, skipped, and stale lessons.
- Add explicit confirmation and undo/recovery paths for structural mutations.

### Gate

- All path operations preserve ordering, prerequisite, concept identity, and approval constraints.
- Refresh/restart retains the same workspace state.
- Concurrent or stale edits fail visibly instead of overwriting a newer path version.

## Phase 9 — Teaching schedule and unit groups

### Work

- Add reversible migrations for teaching periods, period lessons, and unit groups.
- Add schedule read/write/suggest APIs and feasibility calculation.
- Add drag/drop period grouping with an accessible non-drag alternative.
- Let time influence schedule suggestions only; never feed it back into path decomposition.
- Add support/core/extension group management using declared structural toggles.

### Gate

- Scheduling never changes concept IDs, prerequisites, objectives, or path order.
- Group variants retain one shared pack-owned diagnostic item set.
- Migration upgrade/downgrade/upgrade and ownership tests pass.

## Phase 10 — Controlled differentiated shapes

### Work

- Display canonical, support, core, and extension skeletons as structural diffs.
- Explain every added, removed, or repeated slot using its declared toggle.
- Detect slot conflicts and six-section overflow before preparation.
- Require explicit teacher approval for deviations outside declared toggles.
- Persist approvals and deviations in provenance; preserve them across safe regeneration.

### Gate

- No variant can silently change the objective, concept scope, or shared check.
- Overflow and conflict cases block preparation with actionable UI.
- Sibling variant failure remains isolated.

## Phase 11 — Resource projections

### Work

- Add reversible composition persistence and typed compose preview/create/read APIs.
- Implement deterministic projections for full lesson, homework, revision sheet, flashcards, quiz,
  answer key, and unit exam.
- Add selection by path lesson, period, group, and approved component/item.
- Record source pack/version, selected components, item IDs, and template version.
- Add preview, selective print, and export UI.

### Gate

- Deterministic projections make zero LLM calls.
- Every projected block and item is traceable to an approved source revision.
- Existing Lectio/Builder/PDF contracts still render and print.

## Phase 12 — Actuals, marks, and misconception summaries

### Work

- Add reversible lesson-actual and marks-entry persistence.
- Record taught/not-taught, notes, pace, and capability-establishment signals at lesson level.
- Enter aggregate answer-option counts against pack-owned items.
- Map tagged distractor counts to advisory misconception summaries while preserving null tags.
- Feed relevant actuals into later lesson preparation as explicit context, never as silent path
  mutation.

### Gate

- Counts reconcile, item ownership is enforced, and null misconception tags remain valid.
- Summaries are labelled advisory and make no learner-level claims.
- Editing actuals is audited and does not rewrite previously published artifacts.

## Phase 13 — Convergence and production readiness

### Work

- Finalize Home, Units, Classes, Results, Library, and Legacy navigation using available product
  surfaces; do not invent empty sections solely to match a wireframe.
- Add compatibility wrappers so existing packs can appear as one-lesson legacy units without data
  migration.
- Add capability flags, observability, audit events, rate limits, and rollback controls.
- Run the full backend/frontend/architecture/migration/browser/performance/accessibility/security
  suite.
- Deploy to production beta and run smoke tests against real infrastructure.
- Update runbooks, API documentation, migration recovery, support notes, and the final handoff.

### Gate

- All legacy and V2 workflows pass in the same deployment.
- No cross-user access, partial-success masquerading, objective drift, or orphaned revisions.
- Production health, migrations, queue behavior, Builder, Lectio, and PDF are verified.
- Rollback disables V2 navigation/workflows without deleting V2 data or disrupting Legacy Studio.

## Post-build human evaluation and tuning

After Phase 13 is production-beta complete:

- run at least 30 real lessons stratified across grades, subjects, knowledge types, lesson modes,
  and group profiles;
- review classifier accuracy independently from skeleton fit;
- compare the finished V2 workflow with Legacy Studio on path quality, lesson shape, teacher effort,
  generation quality, failures, latency, and cost;
- classify each result as current preferred, V2 preferred, equivalent, or unusable;
- capture wrong classifications, unexplained deviations, severe subject-specific failures, and
  teacher edits;
- tune versioned classifier prompts, skeleton data, toggles, and UI defaults through normal
  migrations/versioning; and
- make the final rollout decision: promote V2 as default, keep it beta while revising, or retain
  Legacy as default.

The study is not allowed to weaken machine guards. A poor result changes versioned configuration
or workflow behavior, not objective ownership, prerequisite safety, provenance, or compatibility.

## Validation required in every phase

- focused regression and contract tests for the change;
- complete backend tests and Ruff;
- frontend unit/component tests, `svelte-check`, and production build;
- architecture gate and unchanged Phase 0 fixture hash;
- migration upgrade/downgrade/upgrade for every schema change;
- browser acceptance for the newly visible vertical slice;
- explicit verification of all nine controlling invariants; and
- recorded command output, commit SHA, risks, and rollback in `PROGRESS.md`.

## Recommended implementation order

1. Phase 6 bridge hardening.
2. Phase 7 visible vertical slice.
3. Phase 8 full path workspace.
4. Phase 9 schedule and groups.
5. Phase 10 differentiated shapes.
6. Phase 11 projections.
7. Phase 12 actuals and marks.
8. Phase 13 convergence and production beta.
9. Post-build human study and iterative tuning.

Do not combine these into one unreviewable change. Each phase must leave production deployable,
with the new capability independently reversible.
