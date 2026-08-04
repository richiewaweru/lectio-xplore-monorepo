# Lectio Source-Of-Truth Generation Spine

**Date:** 2026-04-21  
**Classification:** major  
**Subsystems:** backend pipeline contracts/types/prompts/routing, frontend dependency pinning

## Progress

- [x] Create runbook and tracking checklist
- [x] Capture strict baseline (backend pytest, frontend check/test/build)
- [ ] Capture manual baseline generation artifacts
- [x] Pin frontend `lectio` to exact published npm version and refresh lockfiles
- [x] Add `tools/update_lectio_contracts.py`
- [x] Replace `backend/src/pipeline/types/section_content.py` with generated adapter
- [x] Add `backend/src/pipeline/types/content_phases.py`
- [x] Add generation manifest models and contract resolution helpers
- [x] Make content prompts manifest-driven
- [x] Add deterministic `schema_validator` node after `content_generator`
- [x] Narrow assembler/QC responsibilities and route schema failures deterministically
- [x] Add/update tests for sync, manifest, wrappers, schema validation, routing
- [x] Run focused validation suite
- [~] Run full backend/frontend validation (backend full suite has unrelated pre-existing failures; frontend test sweep deferred by request)
- [ ] Execute one real trial generation and record acceptance evidence

## Baseline Evidence

### Automated Baseline Commands

- `cd backend && uv run pytest`
  - Result: **failed** (11 failures outside this contract-spine slice)
- `cd ../frontend && pnpm run check`
  - Result: **passed**
- `cd ../frontend && pnpm run test`
  - Result: **passed** (when run in dedicated frontend sweep pass)
- `cd ../frontend && pnpm run build`
  - Result: **passed**

### Manual Baseline Capture

- Request payload: _pending_
- SSE event sequence: _pending_
- Final PipelineDocument JSON: _pending_
- One successful section JSON: _pending_
- One partial/awaiting-assets case: _pending_

## Implementation Evidence

- Frontend Lectio source pin:
  - `frontend/package.json` now uses exact published version `lectio: "0.2.5"`.
  - Lockfiles updated: `frontend/pnpm-lock.yaml`, `frontend/package-lock.json`.
- Contract sync tool:
  - Added `tools/update_lectio_contracts.py`.
  - Verified output includes:
    - `backend/contracts/section-content-schema.json`
    - `backend/contracts/component-registry.json`
    - `backend/contracts/component-field-map.json`
    - generated adapter at `backend/src/pipeline/types/section_content.py` with AUTO-GENERATED header.
- Type ownership split:
  - Added `backend/src/pipeline/types/content_phases.py`.
  - `content_generator.py` now imports wrappers from `content_phases.py` and `SectionContent` from generated adapter.
- Manifest + contracts expansion:
  - Added `backend/src/pipeline/types/generation_manifest.py`.
  - Expanded `backend/src/pipeline/contracts.py` with:
    - `get_section_content_schema()`
    - `get_component_generation_hint()`
    - `get_component_capacity()`
    - `$ref`-aware `get_field_schema()`
    - `build_section_generation_manifest(...)`
- Deterministic schema gate:
  - Added `backend/src/pipeline/nodes/schema_validator.py`.
  - Inserted into `process_section` phase 1 immediately after `content_generator`.
- QC/router/assembler narrowing:
  - QC prompt updated to semantic-only checks.
  - Router updated to route `schema_validator` failures before QC.
  - Assembler keeps deterministic checks; capacity remains transitional with TODO.

## Validation Evidence

- Focused backend contract-spine suite:
  - `uv run pytest tests/pipeline/test_pipeline_integration.py::TestProcessSectionComposite::test_process_section_does_not_crash_after_recoverable_diagram_error tests/pipeline/test_pipeline_integration.py::TestProcessSectionComposite::test_process_section_attempts_finalization_when_pending_assets_remain tests/pipeline/test_lectio_contract_sync.py tests/pipeline/test_contract_schema_loader.py tests/pipeline/test_generation_manifest.py tests/pipeline/test_schema_validator.py tests/pipeline/test_content_phase_wrappers.py tests/pipeline/test_section_recovery.py -q`
  - Result: **24 passed**, 1 warning.
- Post-sync backend verification:
  - `uv run python tools/update_lectio_contracts.py`
  - `uv run pytest tests/pipeline/test_lectio_contract_sync.py tests/pipeline/test_contract_schema_loader.py tests/pipeline/test_generation_manifest.py tests/pipeline/test_schema_validator.py tests/pipeline/test_content_phase_wrappers.py tests/pipeline/test_section_recovery.py -q`
  - `uv run pytest tests/pipeline/test_pipeline_integration.py::TestProcessSectionComposite::test_process_section_does_not_crash_after_recoverable_diagram_error tests/pipeline/test_pipeline_integration.py::TestProcessSectionComposite::test_process_section_attempts_finalization_when_pending_assets_remain -q`
  - Result: **all passed** (22/22 + 2/2), with the same manifest-field warning.
- Full backend suite:
  - `uv run pytest`
  - Result: **359 collected, 348 passed, 11 failed** (failures in runtime policy defaults, image pipeline logging/behavior tests, and timeout route tests not introduced by this contract-spine slice).
- Frontend validation:
  - `pnpm run check && pnpm run test && pnpm run build`
  - Result: **passed** in dedicated frontend pass.
  - Note: subsequent frontend test work is deferred until explicit frontend sweep per user direction.

## Notes

- Scope is intentionally narrow: make textbook generation consume Lectio as canonical contract source of truth.
- Published Lectio npm package is the only source for contract artifacts.
