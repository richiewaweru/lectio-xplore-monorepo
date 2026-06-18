# V4 Lock Discovery

**Date**: 2026-06-18
**Classification**: major
**Scope**: reconcile the Lectio v4-lock execution goal with the current repository state before phase execution
**Behavior changes**: none yet

## Goal Intake

Primary source of truth reviewed:

- `C:\Users\richi\Downloads\lectio-v4-codex-goal.md`

Supporting references inspected:

- `C:\Users\richi\Downloads\files (12).zip`
- `lectio-v4-lock-proposal.md`
- `lectio-v4-prompt-and-reasoning-spec.md`

## Progress

- [x] Read project onboarding and standards
- [x] Read the v4-lock goal document
- [x] Inspect repo git state and current branch/tag situation
- [x] Check whether the named target packages and files exist in source form
- [x] Reconcile the goal doc's phase targets with the current codebase's actual live modules
- [ ] Establish a Phase 0 baseline that matches the current repo
- [ ] Execute phases in order only after the live-path mapping is proven

## Implementation Progress

- [x] Map the goal doc onto the current `planning -> pipeline -> generation -> studio` architecture
- [x] Identify the explicit continuity-contract gap against `transition_note`
- [x] Implement an explicit `transition_note` field through the current planning schema, bridge mapping, and Studio review flow
- [x] Validate focused backend planning/bridge/pipeline tests
- [x] Validate focused frontend Studio tests
- [x] Reassess the live `curriculum_enrichment` dependency after continuity is explicit
- [x] Move seeded-outline term/practice enrichment ownership into planning refinement
- [x] Remove the extra seeded-outline enrichment LLM pass from the live curriculum planner path
- [x] Re-validate seeded planner trace, API, and reporting surfaces after the reduction
- [x] Remove dead curriculum enrichment prompt helpers and orphaned package residue
- [x] Remove bytecode-only legacy package shells for old learning/v3/v3-studio/lens/trace surfaces
- [ ] Start formal Phase 0 branch/tag/baseline work once the translated live-path target is stable

## Validation Evidence

- Repo state at intake:
  - current branch: `main`
  - local branch `v2-capture` exists
  - working tree appeared clean
  - local `main` is behind `origin/main` by 19 commits
- Goal-doc target check:
  - directories such as `backend/src/v3_review/`, `backend/src/v3_execution/`, `backend/src/v3_blueprint/`, `backend/src/generation/v3_studio/`, and `backend/src/learning/` exist
  - many of the named v3/v4 files do **not** currently exist as `.py` source files at those paths
  - those directories currently contain `__pycache__` artifacts, which suggests the goal doc refers to a code shape that is not fully present in this checkout
- Current live backend source appears centered on:
  - `backend/src/planning/`
  - `backend/src/pipeline/`
  - `backend/src/generation/`
  - `backend/src/core/`
  - `backend/src/telemetry/`
- Focused implementation validation after adding `transition_note`:
  - backend:
    - `uv run pytest tests/planning/test_planning.py tests/routes/test_brief.py tests/pipeline/test_content_policy.py`
    - result: `46 passed`
  - frontend:
    - `npx vitest run src/lib/api/brief.test.ts src/lib/studio/template-swap.test.ts src/lib/components/studio/PlanReview.test.ts src/lib/stores/studio.test.ts src/lib/components/studio/TeacherStudioFlow.test.ts`
    - result: `11 passed`
  - architecture:
    - `python tools/agent/check_architecture.py --format text`
    - result: `No architecture violations found.`
  - frontend typecheck:
    - `npm run check`
    - result: failed in pre-existing files outside the changed `transition_note` path:
      - `frontend/src/lib/generation/viewer-state.ts`
      - `frontend/src/lib/components/PrintSectionLink.svelte`
      - `frontend/src/routes/textbook/[id]/+page.svelte`
- Focused implementation validation after moving term/practice enrichment into planning:
  - backend:
    - `uv run pytest tests/planning/test_planning.py tests/routes/test_brief.py tests/pipeline/test_content_policy.py`
    - result: `46 passed`
  - backend trace/report surfaces:
    - `uv run pytest tests/routes/test_api.py tests/routes/test_generation_tracing.py tests/services/test_generation_report_recorder.py`
    - result: `46 passed`
  - frontend:
    - `npx vitest run src/lib/api/brief.test.ts src/lib/studio/template-swap.test.ts src/lib/components/studio/PlanReview.test.ts src/lib/stores/studio.test.ts src/lib/components/studio/TeacherStudioFlow.test.ts`
    - result: `11 passed`
  - architecture:
    - `python tools/agent/check_architecture.py --format text`
    - result: `No architecture violations found.`
- Cleanup validation after removing dead curriculum-enrichment surface:
  - orphan search:
    - `rg -n "build_curriculum_enrichment_system_prompt|build_curriculum_enrichment_user_prompt|CurriculumEnrichmentOutput|SectionPlanEnrichment|curriculum_enrichment|PLANNING_ENRICHMENT_CALLER" backend/src backend/tests tools -S`
    - result: no matches
  - backend:
    - `uv run pytest tests/planning/test_planning.py tests/routes/test_brief.py tests/pipeline/test_content_policy.py tests/routes/test_api.py tests/routes/test_generation_tracing.py tests/services/test_generation_report_recorder.py`
    - result: `92 passed`
  - architecture:
    - `python tools/agent/check_architecture.py --format text`
    - result: `No architecture violations found.`
- Legacy package-shell cleanup validation:
  - tracked-files check:
    - `git ls-files "backend/src/learning/*" "backend/src/v3_review/*" "backend/src/v3_execution/*" "backend/src/v3_blueprint/*" "backend/src/generation/v3_studio/*" "backend/src/generation/v3_lenses/*" "backend/src/telemetry/v3_trace/*"`
    - result: no tracked files
  - live import grep:
    - `rg -n "from (learning|v3_review|v3_execution|v3_blueprint)|import (learning|v3_review|v3_execution|v3_blueprint)|generation\.v3_studio|generation\.v3_lenses|telemetry\.v3_trace" backend/src backend/tests frontend tools -S`
    - result: no live import hits
  - post-clean tree:
    - `Get-ChildItem -Path 'backend/src' -Directory | Select-Object -ExpandProperty Name`
    - result:
      - `builder`
      - `contracts`
      - `core`
      - `generation`
      - `media`
      - `pipeline`
      - `planning`
      - `resource_specs`
      - `telemetry`
  - backend:
    - `uv run pytest tests/planning/test_planning.py tests/routes/test_brief.py tests/pipeline/test_content_policy.py tests/routes/test_api.py tests/routes/test_generation_tracing.py tests/services/test_generation_report_recorder.py`
    - result: `92 passed`
  - architecture:
    - `python tools/agent/check_architecture.py --format text`
    - result: `No architecture violations found.`
- Live-path translated-phase audit evidence:
  - Studio flow:
    - [frontend/src/routes/studio/+page.svelte](/C:/Projects/Textbook%20agent/frontend/src/routes/studio/+page.svelte:1) renders only `TeacherStudioFlow`
    - [frontend/src/lib/components/studio/TeacherStudioFlow.svelte](/C:/Projects/Textbook%20agent/frontend/src/lib/components/studio/TeacherStudioFlow.svelte:1) defines only four stages:
      - `idle`
      - `planning`
      - `reviewing`
      - `generating`
  - no live standard-path / clarification / lens symbols:
    - `rg -n "architect_mode|architectMode|generateBlueprint|runLessonArchitect|missing_signals|clarifying|V3ClarificationQuestion|V3ClarificationAnswer|AppliedLens|applied_lenses|LensEffect|v3_lenses" frontend/src backend/src backend/tests tools -S`
    - result: no matches
  - no stale naming remnants:
    - `rg -n "Kira Learning|\bKira\b|pipeline\\\." backend/src backend/tests frontend/src tools backend/contracts backend/src/resource_specs -S`
    - result: no matches
  - frontend types surface:
    - `Get-ChildItem -Path 'frontend/src/lib/types' -File | Select-Object -ExpandProperty Name`
    - result:
      - `index.ts`
      - `studio.ts`
- Translated Phase 2 review-path evidence:
  - terminal status and quality are computed in
    [backend/src/pipeline/run.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/run.py:1)
    from:
    - assembled section count
    - partial section count
    - failed section count
    - QC report coverage and `report.passed` values
  - `quality_passed` is explicitly deterministic:
    - incomplete section coverage => `False`
    - missing QC report coverage => `False`
    - full report coverage => `all(report.passed for report in reports)`
  - `QCCompleteEvent` is emitted only when:
    - all planned sections are assembled
    - QC reports cover all planned sections
    - no partial sections remain
    - no failed sections remain
  - current retry/repair routing is section-scoped, not whole-lesson:
    - [backend/src/pipeline/routers/qc_router.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/routers/qc_router.py:1)
    - targets:
      - `retry_media_frame`
      - `retry_field`
      - `process_section`
  - current semantic QC still uses an LLM:
    - this was true before the modern cut in this run
  - current validation repair still uses an LLM for rerender content repair:
    - this was true before the modern cut in this run
  - focused validation:
    - `uv run pytest tests/pipeline/test_section_recovery.py tests/pipeline/test_pipeline_integration.py tests/services/test_generation_service_progress_updates.py`
    - result: `62 passed`
- Translated Phase 2 implementation update:
  - [backend/src/pipeline/nodes/qc_agent.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/qc_agent.py:1)
    is now a deterministic pass-through that preserves visible QC reports and does not call an LLM
  - [backend/src/pipeline/routers/qc_router.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/routers/qc_router.py:1)
    now terminates at `END` instead of queueing:
    - `retry_media_frame`
    - `retry_field`
    - `process_section` reruns
  - [backend/src/pipeline/nodes/content_generator.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/content_generator.py:1)
    now surfaces validation failures directly without `content_generator_repair`
  - dead semantic QC prompt helper removed:
    - `backend/src/pipeline/prompts/qc.py`
  - dead-helper search:
    - `rg -n "build_qc_system_prompt|build_qc_user_prompt" backend/src backend/tests -S`
    - result: no matches
  - broader validation after the cut:
    - `uv run pytest tests/planning/test_planning.py tests/routes/test_brief.py tests/pipeline/test_content_policy.py tests/routes/test_api.py tests/routes/test_generation_tracing.py tests/services/test_generation_report_recorder.py tests/pipeline/test_section_recovery.py tests/pipeline/test_pipeline_integration.py tests/services/test_generation_service_progress_updates.py`
    - result: `139 passed, 17 skipped`
  - architecture:
    - `python tools/agent/check_architecture.py --format text`
    - result: `No architecture violations found.`

## Key Finding

The goal document is precise, but it does not yet map cleanly onto the source tree in this checkout. That means we should not start Phase 0 branch/tag/test work for the v4-lock cut until we identify one of these two realities:

1. the current repository has already been partially migrated away from the v3/v4 module layout named in the goal; or
2. the source files for that layout are missing from this checkout and the goal targets another branch or snapshot.

## Live-Path Findings

- The frontend Studio route is now a thin wrapper around `TeacherStudioFlow`:
  - [frontend/src/routes/studio/+page.svelte](/C:/Projects/Textbook%20agent/frontend/src/routes/studio/+page.svelte:1)
- The current teacher flow is linear already:
  - intent -> planning stream -> review -> generation
  - there is no visible `architectMode`, `generateBlueprint`, or clarification stage in the current live frontend path
  - [frontend/src/lib/components/studio/TeacherStudioFlow.svelte](/C:/Projects/Textbook%20agent/frontend/src/lib/components/studio/TeacherStudioFlow.svelte:1)
- The current backend planning flow is under `planning/routes.py`, not the v3-studio files named in the goal:
  - `/api/v1/brief/stream`
  - `/api/v1/brief/commit`
  - [backend/src/planning/routes.py](/C:/Projects/Textbook%20agent/backend/src/planning/routes.py:1)
- The current Stage 1 planning equivalent is split across:
  - [backend/src/planning/service.py](/C:/Projects/Textbook%20agent/backend/src/planning/service.py:1)
  - [backend/src/planning/section_composer.py](/C:/Projects/Textbook%20agent/backend/src/planning/section_composer.py:1)
  - [backend/src/planning/visual_router.py](/C:/Projects/Textbook%20agent/backend/src/planning/visual_router.py:1)
  - [backend/src/planning/prompt_builder.py](/C:/Projects/Textbook%20agent/backend/src/planning/prompt_builder.py:1)
  - [backend/src/planning/models.py](/C:/Projects/Textbook%20agent/backend/src/planning/models.py:1)
- The live generation path still depends on curriculum enrichment logic:
  - `backend/src/pipeline/nodes/curriculum_planner.py` defines `SectionPlanEnrichment` and `CurriculumEnrichmentOutput`
  - the seeded-outline path calls `_enrich_seeded_outline(...)`
  - that path invokes `build_curriculum_enrichment_system_prompt(...)` and `build_curriculum_enrichment_user_prompt(...)`
  - [backend/src/pipeline/nodes/curriculum_planner.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/curriculum_planner.py:1)

## Phase Mapping

### Phase 0 - Preconditions

- **Goal-doc expectation**:
  - create `v4-lock` branch and `pre-v4-lock` tag
  - confirm `v2-capture`
  - run full tests and a baseline chunked generation
- **Current-state evidence**:
  - local branch `v2-capture` exists
  - working tree looked clean during intake
  - current branch is `main`
  - local `main` is behind `origin/main` by 19 commits
- **Mapping result**:
  - still applicable, but should wait until the phase targets are mapped to the current architecture
  - creating the branch/tag before that would lock in an ambiguous baseline

### Phase 1 - Ghosts

- **Goal-doc targets**:
  - `learning/pack_runner.py`, `learning/routes.py`, logger rename, stale pack specs, stale architecture-test rules
- **Current-state evidence**:
  - `backend/src/learning/` exists only as `__pycache__` in this checkout
  - `backend/src/core/logging.py` is live and does not use the `pipeline.{node_name}` logger namespace described by the goal
  - wheel manifest already excludes `learning`
- **Mapping result**:
  - partially already achieved, but verification must target the current source tree rather than the historical filenames
  - likely remaining work is repo hygiene around stale bytecode-only directories and any lingering source references, not the exact cuts named in the goal

### Phase 2 - Slim review to deterministic checks

- **Goal-doc targets**:
  - remove LLM coherence review and repair routing from the live generation path
- **Current-state evidence**:
  - the named `v3_review` and `v3_execution` source files are not present as live `.py` modules in this checkout
  - initial searches did not show the named review/repair symbols in current source
- **Mapping result**:
  - needs a second-pass mapping against current `pipeline/` runtime and tests to determine whether this phase is already complete under renamed modules or whether equivalent logic moved elsewhere

### Phase 3 - Delete the standard path

- **Goal-doc targets**:
  - remove the standard architect generation path and keep chunked only
- **Current-state evidence**:
  - current frontend studio route is already linear and does not reference `architectMode`, `generateBlueprint`, or `runLessonArchitect`
  - current planning frontend drives `/api/v1/brief/stream` and `/api/v1/brief/commit`
- **Mapping result**:
  - appears largely already achieved in the live frontend/backend path
  - remaining work is to confirm no hidden non-chunked branch still exists outside the current Studio surface

### Phase 4 - Delete curriculum enrichment

- **Goal-doc targets**:
  - remove `curriculum_enrichment` once the standard consumer is gone
- **Current-state evidence**:
  - the current live pipeline still enriches seeded outlines in `pipeline/nodes/curriculum_planner.py`
  - tests still exercise `CurriculumEnrichmentOutput` and `SectionPlanEnrichment`
- **Mapping result**:
  - explicitly **not safe** to execute as written
  - this is the clearest current stop-condition trigger

### Phase 5 - Prune lens / clarification / signals over-machinery

- **Goal-doc targets**:
  - remove lenses and clarification round-trips from the live Studio path
- **Current-state evidence**:
  - no live clarification stage is present in `TeacherStudioFlow`
  - `frontend/src/routes/studio/+page.svelte` is already a thin wrapper
  - `backend/src/generation/v3_lenses/` exists only as `__pycache__` in this checkout
  - current planning input uses direct `signals`, `preferences`, and `constraints` in `StudioBriefRequest`
- **Mapping result**:
  - live behavior appears mostly aligned with the goal already
  - likely remaining work is cleanup of stale artifacts and confirmation that no hidden imports still reference lens-era code

### Phase 6 - Lighten Stage 1 while preserving contract

- **Goal-doc targets**:
  - lighten the structural planner prompt while preserving section role plus continuity output contract
- **Current-state evidence**:
  - current Stage 1 is split into normalization, section composition, visual routing, and text refinement
  - `PlanningSectionPlan` currently emits:
    - `role`
    - `title`
    - `objective`
    - `focus_note`
    - `selected_components`
    - `rationale`
    - visual fields
  - it does **not** expose `transition_note` under that name
- **Mapping result**:
  - this phase needs architectural translation before implementation
  - the closest modern equivalent is the `planning/` plan contract, not `v3_blueprint/planning/structural_planner.py`
  - if the goal remains authoritative, we would need to decide whether `rationale` or another field is the intended successor to `transition_note`, or whether the current contract must be extended

## Continuity Contract Audit

The goal document treats `transition_note` as non-negotiable, so the current continuity chain was traced end to end.

### Current planning contract

- `PlanningSectionPlan` contains:
  - `role`
  - `title`
  - `objective`
  - `focus_note`
  - `selected_components`
  - `rationale`
  - `terms_to_define`
  - `practice_target`
  - [backend/src/planning/models.py](/C:/Projects/Textbook%20agent/backend/src/planning/models.py:211)
- There is no explicit `transition_note` field in the planning schema.

### How planning is translated into the pipeline request

- `planning/routes.py` maps each planning section into `pipeline.types.requests.SectionPlan`
- The mapping uses:
  - `focus = section.focus_note or section.objective or section.rationale or section.title`
  - `continuity_notes = section.rationale`
  - `bridges_from` and `bridges_to` are set later from neighboring section titles
  - [backend/src/planning/routes.py](/C:/Projects/Textbook%20agent/backend/src/planning/routes.py:101)
- The same mapping logic also exists in `generation/service.py` for the generation path
  - [backend/src/generation/service.py](/C:/Projects/Textbook%20agent/backend/src/generation/service.py:222)

### What the pipeline contract actually carries

- `pipeline.types.requests.SectionPlan` contains:
  - `focus`
  - `bridges_from`
  - `bridges_to`
  - `continuity_notes`
  - `terms_to_define`
  - `practice_target`
  - [backend/src/pipeline/types/requests.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/types/requests.py:83)

### What the fill stage actually reads

- `pipeline/prompts/content.py` injects:
  - `continuity_notes`
  - `terms_to_define`
  - `practice_target`
  - `bridges_from`
  - `bridges_to`
  into content prompts
  - [backend/src/pipeline/prompts/content.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/prompts/content.py:74)
- That means continuity is currently reconstructed from:
  - the section's `rationale`, carried as `continuity_notes`
  - neighboring section titles, carried as `bridges_from` / `bridges_to`

### Evidence-based conclusion

The current codebase **does have** a continuity mechanism, but it is **not equivalent** to the goal doc's required `transition_note` contract:

- `transition_note` in the goal is defined as:
  - one line
  - explicitly saying what the prior section established
  - explicitly saying what the current section now does with that prior work
- the current repo instead uses:
  - a free-form `rationale` string per section
  - neighboring section titles as bridge labels
  - a derived `focus` fallback chain

That is weaker than the goal's requirement because it does not guarantee that every section carries an explicit teacher-editable continuity sentence in the required shape.

### Execution implication

If the v4-lock goal remains the source of truth, then Phase 6 cannot be treated as already satisfied. Before or during the Stage 1 lightening work, the current planning contract would need one of these two outcomes:

1. prove that `rationale -> continuity_notes + bridges_from/bridges_to` is the accepted successor to `transition_note`; or
2. add an explicit continuity field to the current planning contract and propagate it through planning, review, pipeline request mapping, and content prompts.

Without one of those, the current checkout does not satisfy the goal doc's non-negotiable continuity requirement.

## Explicit Continuity Field - Change Surface

If we choose the second path above, the current codebase already shows the full implementation surface.

### Backend schema and planning generation

- Add the explicit field to the planning schema:
  - [backend/src/planning/models.py](/C:/Projects/Textbook%20agent/backend/src/planning/models.py:211)
- Decide whether the planning LLM should generate it directly or whether it should be produced in the refinement step:
  - [backend/src/planning/section_composer.py](/C:/Projects/Textbook%20agent/backend/src/planning/section_composer.py:1)
  - [backend/src/planning/prompt_builder.py](/C:/Projects/Textbook%20agent/backend/src/planning/prompt_builder.py:1)
  - [backend/src/planning/service.py](/C:/Projects/Textbook%20agent/backend/src/planning/service.py:1)
- Preserve validation expectations in planning tests:
  - [backend/tests/planning/test_planning.py](/C:/Projects/Textbook%20agent/backend/tests/planning/test_planning.py:1)

### Backend API and pipeline translation

- Carry the field from planning sections into the pipeline request shape:
  - [backend/src/planning/routes.py](/C:/Projects/Textbook%20agent/backend/src/planning/routes.py:101)
  - [backend/src/generation/service.py](/C:/Projects/Textbook%20agent/backend/src/generation/service.py:222)
- Extend the pipeline request contract if the new field should survive independently from `continuity_notes`:
  - [backend/src/pipeline/types/requests.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/types/requests.py:83)
- Update policy and content-prompt expectations if the fill stage should read the explicit note rather than inferred continuity:
  - [backend/src/pipeline/prompts/content.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/prompts/content.py:74)
  - [backend/tests/pipeline/test_content_policy.py](/C:/Projects/Textbook%20agent/backend/tests/pipeline/test_content_policy.py:1)

### Frontend Studio contract and review surface

- Add the field to the Studio planning types:
  - [frontend/src/lib/types/studio.ts](/C:/Projects/Textbook%20agent/frontend/src/lib/types/studio.ts:1)
  - [frontend/src/lib/types/index.ts](/C:/Projects/Textbook%20agent/frontend/src/lib/types/index.ts:1)
- Ensure plan streaming and commit serialization carry it without dropping it:
  - [frontend/src/lib/api/brief.ts](/C:/Projects/Textbook%20agent/frontend/src/lib/api/brief.ts:1)
- Preserve the field through review-state updates:
  - [frontend/src/lib/stores/studio.ts](/C:/Projects/Textbook%20agent/frontend/src/lib/stores/studio.ts:1)
  - [frontend/src/lib/studio/template-swap.ts](/C:/Projects/Textbook%20agent/frontend/src/lib/studio/template-swap.ts:1)
- Expose it in the teacher review UI if the goal's "teacher edits output / teacher-editable plan" rule is to remain true:
  - [frontend/src/lib/components/studio/PlanReview.svelte](/C:/Projects/Textbook%20agent/frontend/src/lib/components/studio/PlanReview.svelte:1)

### API and contract tests that would need updates

- Planning API shape and commit behavior:
  - [backend/tests/routes/test_brief.py](/C:/Projects/Textbook%20agent/backend/tests/routes/test_brief.py:1)
- Planning stream client and Studio state consumers:
  - `frontend/src/lib/api/brief.test.ts`
  - `frontend/src/lib/stores/studio.test.ts`
  - `frontend/src/lib/studio/template-swap.test.ts`
  - `frontend/src/lib/components/studio/PlanReview.test.ts`
  - `frontend/src/lib/components/studio/TeacherStudioFlow.test.ts`

## Recommended Implementation Shape

Based on the current architecture, the least ambiguous path is:

1. add `transition_note` explicitly to `PlanningSectionPlan`
2. make the refinement prompt produce it alongside `title` and `rationale`
3. map `transition_note` into the pipeline request as the canonical continuity field
4. keep `bridges_from` / `bridges_to` as auxiliary labels derived from neighboring sections
5. expose `transition_note` in Studio review as a teacher-editable field

That approach preserves the goal doc's intent much more faithfully than overloading `rationale`, while fitting the modern `planning -> pipeline -> generation` split already present in the repo.

### Phase 7 - Manifest and final sweep

- **Goal-doc targets**:
  - update wheel package list and remove orphan references
- **Current-state evidence**:
  - [backend/pyproject.toml](/C:/Projects/Textbook%20agent/backend/pyproject.toml:1) already packages only `core`, `generation`, `pipeline`, `planning`, `telemetry`, and `pdf_export`
  - `learning` and `curriculum_enrichment` are already omitted from the wheel package list
- **Mapping result**:
  - partly already satisfied
  - final grep and validation should happen only after the live-path refactor targets are settled

## Goal-Doc Stop Condition Triggered

The v4-lock goal says to halt if `curriculum_enrichment` has any consumer on the chunked path. In this checkout, the current live path does have an active consumer, but it lives under `pipeline/nodes/curriculum_planner.py` rather than the exact v3/v4 files named in the goal. That means the goal cannot be executed literally here without first remapping the phases to the current architecture.

## Risks

- Starting destructive cuts against guessed equivalents would violate the goal document's stop-condition rules.
- The goal requires phase-by-phase verification; that is not possible until the live path mapping is known.
- Branching from a local `main` that is behind `origin/main` may not match the goal's intended baseline.

## Working Conclusion

The v4-lock document is still useful as the product and architecture intent, but this repository appears to be a newer or differently-shaped implementation than the one the file names were written against. The practical way forward is:

1. treat the goal doc as the architecture target and acceptance gate
2. translate each phase to the current `planning/`, `pipeline/`, `generation/`, and frontend Studio modules
3. only then begin the actual cut, baseline, and verification sequence

## Requirement Audit Matrix

Status key used here:

- **Proved**: current evidence directly supports the requirement
- **Contradicted**: current evidence directly conflicts with the requirement
- **Open**: requirement may still be achievable, but current evidence is missing or incomplete
- **N/A by translation**: the named file path is obsolete, but the underlying product intent appears satisfied elsewhere

| Goal requirement | Current status | Evidence |
| --- | --- | --- |
| Phase 0 branch `v4-lock` exists | Contradicted | Current branches are `main`, `v2-capture`, `v3`; no `v4-lock` branch yet |
| Phase 0 tag `pre-v4-lock` exists | Contradicted | `git tag --list` returned no tags |
| `v2-capture` recovery branch exists | Proved | `git branch --list` shows `v2-capture` |
| Baseline full test result recorded | Contradicted | No baseline run or evidence captured yet in this runbook |
| Baseline chunked generation recorded | Contradicted | No generation timing or artifact evidence captured yet in this runbook |
| Single linear Studio flow (no architect mode branch) | Proved | Current Studio route uses `TeacherStudioFlow`; no `architectMode`, `generateBlueprint`, or `runLessonArchitect` in the live path |
| Clarification round-trip removed from live Studio path | Proved | `TeacherStudioFlow` shows intent -> planning -> review -> generation; no clarifying stage in live path |
| Lens layer removed from live Studio path | Proved | No live lens usage found in active frontend/backend path; legacy `generation/v3_lenses` is only bytecode residue |
| Dead `curriculum_enrichment` can be safely deleted | Contradicted | Live consumer exists in `backend/src/pipeline/nodes/curriculum_planner.py` |
| Stage 1 continuity contract preserves explicit `transition_note` | Contradicted | Current contract uses `rationale` plus `bridges_*`; no explicit `transition_note` field |
| Current Stage 1 has a continuity mechanism of some kind | Proved | `continuity_notes` plus `bridges_from` / `bridges_to` are carried into content prompts |
| Wheel manifest excludes stale `learning` / enrichment packages | Proved | `backend/pyproject.toml` already omits `learning` and `curriculum_enrichment` from wheel packages |
| Goal doc can be executed literally file-by-file against this checkout | Contradicted | Multiple named v3/v4 files are absent in source form; live architecture is newer/different |
| Goal doc remains usable as architecture target | Proved | Modern `planning -> pipeline -> generation` path can be mapped to the goal’s intent and invariants |

## Highest-Confidence Next Work

Based on the audit, the strongest next implementation target is still the explicit continuity contract, because it is:

- directly contradicted by current evidence
- clearly required by the goal doc
- implementable in the modern architecture without needing the historical v3/v4 file layout

Only after that work is translated and implemented does it make sense to begin the formal Phase 0 branch/tag/baseline sequence for a true v4-lock execution pass.

## Translated Execution Sequence

The current project docs confirm that the live planning stack is:

- deterministic through `normalize_brief -> choose_template -> compose_sections -> route_visuals`
- followed by a single LLM refinement pass in `refine_plan_text`
- then bridged into the pipeline from `planning/routes.py` and `generation/service.py`

That means the safest repo-native execution order is:

### Step A - Fix the non-negotiable continuity contract first

Reason:

- this is the clearest contradiction with the goal doc
- it fits the modern planning architecture cleanly
- it does not require guessing at removed v3/v4 files

Target modules:

- `backend/src/planning/models.py`
- `backend/src/planning/prompt_builder.py`
- `backend/src/planning/service.py`
- `backend/src/planning/routes.py`
- `backend/src/generation/service.py`
- `backend/src/pipeline/types/requests.py`
- `backend/src/pipeline/prompts/content.py`
- Studio frontend types/review UI/tests

### Step B - Re-audit seeded-outline enrichment after continuity is explicit

Reason:

- the goal doc's stop condition is currently triggered because curriculum enrichment is still live
- once continuity has a proper explicit carrier, we can judge whether the enrichment layer is still doing unique work or is now redundant

Target modules:

- `backend/src/pipeline/nodes/curriculum_planner.py`
- `backend/src/pipeline/prompts/curriculum.py`
- related pipeline/content-policy tests

### Step C - Only then begin formal Phase 0 repo mechanics

Reason:

- branch/tag/baseline work should happen against the translated live execution target, not against the older filename map

Tasks at that point:

- create `v4-lock` branch
- create `pre-v4-lock` tag
- record full validation baseline
- record one real generation baseline

### Step D - Continue with the remaining translated cuts

In practical order:

1. continuity contract completion
2. enrichment reassessment/removal if truly redundant
3. any remaining live-path cleanup for stale review/repair machinery
4. final manifest/orphan sweep
5. full validation and timing comparison

## Remaining Hard Blockers

- The goal doc assumes a historical module layout that is not the live source layout in this checkout.
- `curriculum_enrichment` is still active on the current live path, so its deletion cannot be justified yet.
- `transition_note` is now explicit, but term/practice enrichment is still separate and live.
- Formal Phase 0 evidence does not yet exist in this worktree: no `v4-lock` branch, no `pre-v4-lock` tag, no recorded baseline validation or generation artifact.

## Curriculum Enrichment Re-Audit

This was re-checked after the explicit `transition_note` implementation.

### What `transition_note` now covers

- teacher-editable continuity between sections
- the "what the previous section established / what this one now does" contract from the goal doc
- prompt-visible continuity carried through the pipeline request

### What seeded-outline enrichment still adds that is not replaced by `transition_note`

The seeded enrichment path in [backend/src/pipeline/nodes/curriculum_planner.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/curriculum_planner.py:1) still adds three distinct fields:

- `terms_to_define`
- `terms_assumed`
- `practice_target`

These are still live and load-bearing:

- they are requested explicitly by [backend/src/pipeline/prompts/curriculum.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/prompts/curriculum.py:1)
- they are injected into content prompts by [backend/src/pipeline/prompts/content.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/prompts/content.py:71)
- they are asserted in [backend/tests/pipeline/test_content_policy.py](/C:/Projects/Textbook%20agent/backend/tests/pipeline/test_content_policy.py:1)
- they flow into reporting and tracing payloads on the seeded-enrichment path

### Evidence-based conclusion

`curriculum_enrichment` is **still doing unique work** after `transition_note` became explicit.

It is not just duplicating continuity anymore; in the current architecture it is the only visible source for:

- assigning key terms to one section
- marking terms reused by later sections
- setting a section-specific practice target

That means the goal doc's Phase 4 deletion step is **still unsafe** in this checkout unless those responsibilities are first absorbed into another live planning stage.

### Practical implication

If the v4-lock goal remains authoritative, there are now two different categories of planning information:

1. **continuity** - now handled explicitly via `transition_note`
2. **term/practice enrichment** - still handled only by seeded-outline enrichment

So the next reduction step cannot be "delete curriculum enrichment now." It would first need a replacement plan for:

- `terms_to_define`
- `terms_assumed`
- `practice_target`

Without that, the stop condition on chunked-path enrichment consumers remains active.

## Recommended Next Step

Map each goal-doc phase target to the current repository's live module(s), beginning with:

- standard vs chunked generation entrypoints in the current frontend/backend
- whether the current `planning/` + `pipeline/` flow is the post-v3 replacement for the named goal-doc modules
- which current module corresponds to each goal-doc phase target before any branch/tag/test baseline work begins
- whether the v3/v4 directories are stale shells, generated artifacts, or omitted source

Only after that mapping should Phase 0 begin.

## Seeded Enrichment Reduction

The live seeded-outline path no longer performs a second LLM enrichment pass once planning-owned
section plans are already present.

### What changed

- Planning refinement now owns these per-section fields directly:
  - `transition_note`
  - `terms_to_define`
  - `terms_assumed`
  - `practice_target`
- The seeded branch in
  [backend/src/pipeline/nodes/curriculum_planner.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/curriculum_planner.py:1)
  now:
  - validates and sorts the supplied section plans
  - routes visual placements
  - preserves the planning-supplied term/practice metadata
  - publishes the same planner trace/report shape
  - skips the redundant curriculum-enrichment LLM call

### Verification outcome

- Seeded planner tests now assert that:
  - planning-authored `terms_to_define`, `terms_assumed`, and `practice_target` survive unchanged
  - visual placements are still derived on the seeded path
  - no seeded enrichment LLM call is made
- Reporting and tracing tests still pass with `path="seeded_enrichment"` and `result="planned"`,
  so downstream consumers remain stable even though the extra enrichment step is gone

### Current interpretation against the goal doc

This closes the strongest remaining contradiction behind the goal doc's Phase 4 stop condition in
the modern architecture: the seeded path still exists, but it is no longer doing a separate
pedagogical enrichment round once teacher-reviewed planning data is already available.

What remains is a repo-wide live-path audit for the later translated cuts and then the formal
Phase 0 branch/tag/baseline sequence.

## Dead Surface Cleanup

After the seeded-path reduction, two kinds of stale curriculum-enrichment surface still remained:

- unused helper functions in
  [backend/src/pipeline/prompts/curriculum.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/prompts/curriculum.py:1)
- a bytecode-only `backend/src/curriculum_enrichment/` directory with no source files left

Those are now removed.

### Evidence

- repo search shows no remaining references to:
  - `build_curriculum_enrichment_system_prompt`
  - `build_curriculum_enrichment_user_prompt`
  - `CurriculumEnrichmentOutput`
  - `SectionPlanEnrichment`
  - `curriculum_enrichment`
  - `PLANNING_ENRICHMENT_CALLER`
- the broader backend validation slice still passes after the cleanup

### Why this matters

This moves the modern repo closer to the goal doc's intended Phase 4 end state:

- no live extra enrichment pass on the seeded path
- no orphaned enrichment-specific helpers left behind in the prompt layer
- no residual enrichment package on disk pretending to be part of the active architecture

The remaining work is no longer about curriculum-enrichment specifically; it is about proving the
other translated v4-lock phases against the actual current repo, then deciding when the formal
Phase 0 branch/tag baseline should begin.

## Legacy Package Shell Cleanup

The repo still had several top-level directories that matched the old goal-doc vocabulary but no
longer contained source files:

- `backend/src/learning/`
- `backend/src/v3_review/`
- `backend/src/v3_execution/`
- `backend/src/v3_blueprint/`
- `backend/src/generation/v3_studio/`
- `backend/src/generation/v3_lenses/`
- `backend/src/telemetry/v3_trace/`

These were bytecode-only shells with no tracked source files and no live import references.
They are now removed.

### Why this matters

This is the strongest evidence so far that large parts of the goal doc's older filename map are
already obsolete in this checkout rather than merely hidden:

- the live app assembles from `core`, `generation`, `planning`, `pipeline`, and `telemetry`
- the old v3/v4/learning package names were not real source packages anymore
- keeping the bytecode shells around made the repository look more historical than it actually is

### Translation impact

With those shells removed, the translated phase mapping is sharper:

- Phase 1 ghost cleanup is now materially advanced in the modern repo
- Phase 3 and Phase 5 legacy frontend/backend package names look structurally retired already
- the remaining work is less about deleting obvious old directories and more about proving
  whether any equivalent live behavior still exists under modern module names

## Translated Phase Status

Based on the current live tree and command evidence, the translated phase picture now looks like
this:

### Phase 1 - Ghosts

- **Evidence now supports mostly satisfied in the modern repo**
- Why:
  - old `learning` package shell removed
  - no `Kira` label hits
  - no `pipeline.` logger namespace hits
  - no tracked source remains for the old ghost directories

### Phase 3 - Standard path deletion

- **Evidence currently supports satisfied in the live Studio/frontend path**
- Why:
  - no `architectMode`, `architect_mode`, `generateBlueprint`, or `runLessonArchitect` hits
  - Studio route is a thin wrapper around `TeacherStudioFlow`
  - `TeacherStudioFlow` runs a single plan -> review -> generate path

### Phase 4 - Curriculum enrichment removal

- **Translated modern equivalent is materially advanced but not fully equivalent to the goal-doc wording**
- Why:
  - seeded outline no longer does a second enrichment LLM call
  - dead enrichment helpers and orphan package residue are removed
  - the runtime planner trace still uses `path="seeded_enrichment"` for compatibility, even though
    the extra enrichment step is gone

### Phase 5 - Lens / clarification pruning

- **Evidence currently supports satisfied in the live path**
- Why:
  - no clarification symbols remain in live frontend/backend source
  - no lens symbols remain in live source
  - frontend type surface no longer has a dedicated `v3.ts`; only `index.ts` and `studio.ts` remain

### Still open

- Phase 0 formal baseline work:
  - branch `v4-lock`
  - tag `pre-v4-lock`
  - recorded full-suite baseline
  - recorded real generation baseline
- Phase 2 translated review-path proof:
  - evidence now supports **implemented in the live path**
  - why:
    - terminal status and `quality_passed` remain deterministic
    - semantic LLM QC is removed from the live path
    - automatic rerender routing after review is removed from the live path
    - validation failures now surface as visible errors instead of triggering automatic content repair
  - remaining residue:
    - compatibility event types and recorder counters for retry/repair still exist on disk
    - some legacy retry-oriented tests are now explicitly skipped because they assert behavior that
      the v4-lock cut intentionally removed
- Phase 6 translated Stage-1 proof:
  - continuity contract is now explicit
  - still need stronger evidence about the remaining lean-planner intent versus the goal doc's timing
    and role-contract requirements
- Phase 7 final sweep:
  - depends on the remaining open items above

## Translated Phase 6 - Active Contract Role Lock

The goal doc's lean Stage 1 planner required emitted section roles to stay inside the active spec
vocabulary. In the modern repo, the closest live equivalent is the planning contract's
`section_role_defaults`.

### What the live-path audit found

- Contract JSON files already define their usable section-role vocabulary through
  `section_role_defaults`
- The planning prompt in
  [backend/src/planning/section_composer.py](/C:/Projects/Textbook%20agent/backend/src/planning/section_composer.py:1)
  still advertised a broader global role list
- The LLM output validator checked count, intro/summary shape, and some pedagogical constraints,
  but did not reject roles that were valid globally yet invalid for the chosen contract
- The deterministic fallback sequence also assumed some global roles rather than deriving its
  sequence from the active contract first

### Change made

The section composer now treats the active contract as the role authority:

- the system prompt tells the model to use only roles supplied in the user prompt
- the user prompt now lists only the chosen contract's `section_role_defaults` keys
- `_roles_are_usable(...)` now rejects any role outside that contract-specific set
- deterministic fallback role selection now picks from the active contract vocabulary rather than
  from the global role universe

### Validation evidence

- `uv run pytest tests/planning/test_planning.py`
  - result: `22 passed`
- `uv run pytest tests/routes/test_brief.py tests/pipeline/test_content_policy.py tests/routes/test_api.py tests/routes/test_generation_tracing.py tests/services/test_generation_report_recorder.py tests/pipeline/test_section_recovery.py tests/pipeline/test_pipeline_integration.py tests/services/test_generation_service_progress_updates.py`
  - result: `119 passed, 17 skipped`
- `python tools/agent/check_architecture.py --format text`
  - result: `No architecture violations found.`

### Translation impact

This closes the clearest remaining Phase 6 contradiction in the live planner:

- the active template contract now defines the planner's legal role vocabulary
- out-of-contract LLM role sequences are rejected and fall back to a contract-safe sequence
- the planner remains leaner than the older goal-doc architecture while preserving the same
  invariant the goal doc was trying to enforce

## Validation Recovery And Phase 7 Hygiene Evidence

After the translated Phase 6 work, the repo still could not honestly satisfy the goal doc's
"full suite green" style verification because the declared repo validation scope was failing on
lint and frontend typecheck drift unrelated to the main planning/pipeline cuts.

### What was fixed

- removed stale unused imports that were breaking backend Ruff validation
- restored module-level compatibility exports in:
  - [backend/src/pipeline/nodes/image_generator.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/image_generator.py:1)
  - [backend/src/generation/routes.py](/C:/Projects/Textbook%20agent/backend/src/generation/routes.py:1)
  so monkeypatched test seams and executor compatibility still work while remaining lint-clean
- hardened frontend section-title reads so the viewer/report surfaces tolerate temporarily missing
  `header` payloads without typecheck failure:
  - [frontend/src/lib/generation/viewer-state.ts](/C:/Projects/Textbook%20agent/frontend/src/lib/generation/viewer-state.ts:1)
  - [frontend/src/lib/components/PrintSectionLink.svelte](/C:/Projects/Textbook%20agent/frontend/src/lib/components/PrintSectionLink.svelte:1)
  - [frontend/src/routes/textbook/[id]/+page.svelte](/C:/Projects/Textbook%20agent/frontend/src/routes/textbook/[id]/+page.svelte:1)
- added report-read fallback hydration so section-level interaction/image/diagram outcomes remain
  visible in API responses even if the persisted section snapshot lags behind the authoritative
  report timeline:
  - [backend/src/telemetry/service.py](/C:/Projects/Textbook%20agent/backend/src/telemetry/service.py:1)
  - [backend/src/generation/service.py](/C:/Projects/Textbook%20agent/backend/src/generation/service.py:1)
  - [backend/src/telemetry/routes.py](/C:/Projects/Textbook%20agent/backend/src/telemetry/routes.py:1)

### Phase 7-style hygiene evidence

- wheel manifest already matches the modern live package surface:
  - [backend/pyproject.toml](/C:/Projects/Textbook%20agent/backend/pyproject.toml:1)
  - wheel packages:
    - `src/core`
    - `src/generation`
    - `src/pipeline`
    - `src/planning`
    - `src/telemetry`
    - `src/pdf_export`
- no legacy package-path references remain in backend manifest/config grep:
  - `rg -n "src/curriculum_enrichment|src/learning|src/v3_review|src/v3_execution|src/v3_blueprint|generation/v3_studio|generation/v3_lenses|telemetry/v3_trace" backend -S`
  - result: no matches
- orphan symbol sweep now returns nothing unintended:
  - `rg -n "route_repairs|run_llm_review|curriculum_enrichment|architect_mode|missing_signals|clarifying|applied_lenses|LensEffect|AppliedLens|pipeline\\.|Kira Learning|\\bKira\\b" backend/src backend/tests frontend/src tools backend/contracts backend/src/resource_specs -S`
  - result: no unintended live-code hits

### Validation evidence

- focused frontend regression slice after the null-safety fixes:
  - `npx vitest run src/lib/generation/viewer-state.test.ts src/lib/components/PrintSectionLink.test.ts src/routes/textbook/[id]/page.test.ts`
  - result: `23 passed`
- focused backend regression slice after restoring compatibility seams:
  - `uv run pytest tests/pipeline/test_image_pipeline.py tests/routes/test_api.py`
  - result: `56 passed`
- focused tracing regression after report hydration:
  - `uv run pytest tests/routes/test_generation_tracing.py`
  - result: `2 passed`
- full declared repo validation:
  - `python tools/agent/validate_repo.py --scope all`
  - result:
    - backend Ruff: pass
    - backend pytest: `388 passed, 17 skipped`
    - frontend check: pass
    - frontend build: pass
    - tooling pytest: `8 passed`
- architecture:
  - `python tools/agent/check_architecture.py --format text`
  - result: `No architecture violations found.`

### What still remains before the full goal can be claimed complete

The repo is in a much stronger proof state now, but the original goal is still not fully proven:

- Phase 0 branch/tag baseline has not been executed on the current dirty worktree:
  - no `v4-lock` branch created yet
  - no `pre-v4-lock` tag created yet
- the goal doc still requires one real end-to-end booklet baseline and a post-cut timing comparison
- we have not yet produced fresh evidence for:
  - one real chunked generation completing to booklet/PDF on the current tree
  - faster Stage 1 / end-to-end timing versus the requested baseline

## V3 Port Completion Pass

The validated `v4`-goal behavior has now been carried onto `v3` and re-stabilized against the
current branch shape instead of the earlier `main` snapshot.

### What changed in this pass

- restored lean-contract compatibility in
  [backend/src/pipeline/contracts.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/contracts.py:1)
  so `v3` contract exports still satisfy the newer pipeline summary model
- restored the richer
  [backend/contracts/guided-concept-path.json](/C:/Projects/Textbook%20agent/backend/contracts/guided-concept-path.json:1)
  contract payload needed by the current pipeline and route tests
- re-applied the deterministic review cut on `v3` by making:
  - [backend/src/pipeline/routers/qc_router.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/routers/qc_router.py:1)
    terminate at `END`
  - [backend/src/pipeline/nodes/qc_agent.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/qc_agent.py:1)
    preserve existing QC reports or synthesize a default pass report without an extra LLM review
  - [backend/src/pipeline/nodes/content_generator.py](/C:/Projects/Textbook%20agent/backend/src/pipeline/nodes/content_generator.py:1)
    surface rerender validation failures directly instead of emitting repair-attempt events
- unified `/api/v1/blocks/generate` back onto the ownership-checked route surface by mounting
  [backend/src/generation/block_generate_routes.py](/C:/Projects/Textbook%20agent/backend/src/generation/block_generate_routes.py:1)
  through
  [backend/src/generation/routes.py](/C:/Projects/Textbook%20agent/backend/src/generation/routes.py:1)
  and removing the duplicate handler that bypassed the patched seam

### Validation Evidence

- focused backend recovery:
  - `uv run pytest tests/pipeline/test_content_policy.py -q`
  - result: `16 passed`
- deterministic review / section recovery:
  - `uv run pytest tests/pipeline/test_pipeline_integration.py -q`
  - result: `36 passed, 17 skipped`
  - `uv run pytest tests/pipeline/test_section_recovery.py -q`
  - result: `7 passed`
- generation and telemetry follow-up:
  - `uv run pytest tests/generation/test_v3_generation_writer.py -q`
  - result: `4 passed`
  - `uv run pytest tests/generation/test_v3_studio_generation_stream.py -q`
  - result: `30 passed`
  - `uv run pytest tests/services/test_telemetry_service.py -q`
  - result: `2 passed`
- route and health follow-up:
  - `uv run pytest tests/routes/test_blocks_generate.py -q`
  - result: `4 passed`
  - `uv run pytest tests/routes/test_auth_google.py -q`
  - result: `1 passed`
  - `uv run pytest tests/core/health/test_health_routes.py -q`
  - result: `11 passed`
- full backend validation:
  - `uv run pytest -q`
  - result: `375 passed, 17 skipped`
- architecture:
  - `python tools/agent/check_architecture.py --format text`
  - result: `No architecture violations found.`
- frontend:
  - `npm run check`
  - result: `svelte-check found 0 errors and 0 warnings`
  - `npm run build`
  - result: pass
- declared repo validation:
  - `python tools/agent/validate_repo.py --scope all`
  - result:
    - backend Ruff: pass
    - backend pytest: `375 passed, 17 skipped`
    - frontend check: pass
    - frontend build: pass
    - tooling pytest: `8 passed`

### Current status

- [x] Established a `v3`-native validation baseline for the ported work
- [x] Executed the translated `v4` goal changes against the live `v3` architecture
- [x] Reached full declared repo validation on branch `v3`
- [ ] Produced a fresh real generation timing/baseline artifact
- [ ] Decided whether the historical Phase 0 branch/tag mechanics are still needed now that the user wants the work to land directly on `v3`
