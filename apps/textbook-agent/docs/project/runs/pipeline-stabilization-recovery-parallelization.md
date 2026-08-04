# Whole-Pipeline Stabilization, Failed-Section Recovery, and Safe Parallelization

**Date**: 2026-03-24  
**Branch**: `codex/pipeline-stabilization-recovery-parallel`  
**Status**: validated

## Goal

Finish the next stabilization layer for the textbook pipeline so that:

- sections do not fail silently before assembly
- partial generations persist enough evidence to explain what broke
- enhancement reruns only failed or missing sections instead of throwing away good ones
- diagram retries stop wasting time on repeated timeout paths
- the per-section pipeline is structured into explicit phases so later optimization work is safer

This run intentionally builds on the earlier silent-hang recovery work instead of replacing it.

## Shipped Scope

### 1. Failed-section visibility is now first-class

Added pipeline and document/report structures for failed sections and failure details:

- `NodeFailureDetail` in `backend/src/pipeline/state.py`
- `FailedSectionEntry` in `backend/src/pipeline/api.py`
- `section_failed` SSE event in `backend/src/pipeline/events.py`
- failure details + retry counters in `backend/src/pipeline/reporting.py`
- report aggregation in `backend/src/textbook_agent/application/services/generation_report_recorder.py`

Result:

- a section that dies before assembly is no longer silently dropped
- the final document can expose `failed_sections`
- the report captures node-level failure details and retry telemetry
- the frontend can reflect failure state immediately instead of waiting for a terminal generation outcome

### 2. `content_generator` now gets one bounded repair chance

`backend/src/pipeline/nodes/content_generator.py` now:

- detects validation-shaped failures from the first output attempt
- builds a schema-repair prompt via `backend/src/pipeline/prompts/content.py`
- retries exactly once using `content_generator_repair`
- persists failed-section diagnostics if the repair also fails
- emits `ValidationRepairAttemptedEvent`, `ValidationRepairSucceededEvent`, and `SectionFailedEvent`

Policy:

- this is a bounded repair, not a loop
- broken content does not continue to diagram, interaction, assembly, or QC
- successful sibling sections still complete

### 3. Partial reruns now target only failed or missing sections

The enhance path in `backend/src/textbook_agent/interface/api/routes/generation.py` now:

- reconstructs section plans from the saved manifest and failed sections
- preserves successful seeded sections and QC reports
- computes `target_section_ids` from failed or missing sections

Pipeline execution support was added in:

- `backend/src/pipeline/types/requests.py`
- `backend/src/pipeline/graph.py`
- `backend/src/pipeline/run.py`
- `backend/src/pipeline/nodes/curriculum_planner.py`

Result:

- enhancing a partial draft does not rerun every section by default
- successful sections are preserved
- missing/failed sections get a focused rerun path

### 4. Diagram retries are now explicit and bounded

`backend/src/pipeline/nodes/diagram_generator.py` now uses tiered timeouts:

- `draft`: `20s`
- `balanced`: `35s`
- `strict`: `45s`

It also writes diagram outcomes to state and emits `DiagramOutcomeEvent`.

`backend/src/pipeline/graph.py` and `backend/src/pipeline/routers/qc_router.py` now:

- track diagram retry budget separately
- avoid rerunning a prior timeout path
- keep diagram failure degradable without blocking the section

Result:

- draft mode stays fast
- balanced/strict modes give complex diagrams more runway
- timeout loops are bounded instead of repeating expensive dead-end work

### 5. The per-section flow is now phased and parallel-safe

New deterministic planning was added in:

- `backend/src/pipeline/types/composition.py`
- `backend/src/pipeline/nodes/composition_planner.py`

`backend/src/pipeline/nodes/process_section.py` and `backend/src/pipeline/nodes/section_runner.py` now structure a section as:

1. `content_generator`
2. `composition_planner`
3. parallel phase
   - `diagram_generator`
   - interaction path (`interaction_decider -> interaction_generator`)
4. `section_assembler`
5. `qc_agent`

Important compatibility choice:

- `interaction_decider` is still preserved in the runtime path for parity
- the new deterministic composition plan is additive rather than a full decider replacement

This keeps the new structure in place without overloading `content_generator` or forcing a brittle all-at-once interaction migration.

### 6. Frontend now shows partial failures explicitly

Frontend updates landed in:

- `frontend/src/lib/types/index.ts`
- `frontend/src/lib/generation/viewer-state.ts`
- `frontend/src/routes/textbook/[id]/+page.svelte`

Result:

- `failed_sections` render in the textbook view
- `section_failed` SSE events update the page in real time
- ready vs failed section counts are visible during partial generations

## Validation

Validated successfully with:

- backend targeted recovery/API/report suites
- backend broader pipeline/interface suites
- full backend test suite from `backend/`
- frontend targeted test suites
- full frontend test suite
- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope all`

Validation note:

- backend test execution must be run from `backend/` or via tooling that respects `backend/pyproject.toml`
- repo-root `pytest` picks a different config and is not the correct backend validation entry point in this workspace
- repo validation in this workspace still needs `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts`

## Tests Added or Extended

- `backend/tests/pipeline/test_section_recovery.py`
- `backend/tests/pipeline/test_composition_planner.py`
- `backend/tests/pipeline/test_partial_rerun.py`
- `backend/tests/interface/test_api.py`
- `backend/tests/application/test_generation_report_recorder.py`
- `backend/tests/pipeline/test_pipeline_integration.py`
- `frontend/src/routes/textbook/[id]/page.test.ts`
- `frontend/src/lib/generation/viewer-state.test.ts`
- `frontend/src/lib/api/client.test.ts`
- `frontend/src/lib/components/LectioDocumentView.test.ts`

## Public Contract Notes

- no new public API endpoint was added
- existing generation statuses remain unchanged
- the document shape now includes `failed_sections`
- the stream now includes `section_failed`
- existing retry/QC flows remain backward-compatible

## Intentional Non-Goals

- no unbounded retry loops
- no user-facing diagnostics dashboard yet
- no removal of `interaction_decider` until parity is proven over a longer period
- no aggressive parallel fan-out beyond the per-section phase boundary added here

## Pickup Path

If follow-up work is needed, start here:

1. `backend/src/pipeline/nodes/content_generator.py`
2. `backend/src/pipeline/nodes/composition_planner.py`
3. `backend/src/pipeline/nodes/process_section.py`
4. `backend/src/pipeline/graph.py`
5. `backend/src/textbook_agent/interface/api/routes/generation.py`
6. `backend/src/textbook_agent/application/services/generation_report_recorder.py`
7. `frontend/src/routes/textbook/[id]/+page.svelte`
