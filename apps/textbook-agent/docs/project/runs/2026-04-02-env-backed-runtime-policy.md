# Env-Backed Runtime Policy

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** backend, frontend, pipeline, docs, runtime configuration

## Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation
- [x] Self-reviewed against `agents/standards/review.md`
- [ ] Wrote commit message(s) following `agents/standards/communication.md`
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted follow-up work or open questions

## Summary

This change centralizes pipeline execution policy behind env-backed settings and carries that policy through the backend runtime, generation admission control, SSE telemetry, and the Teacher Studio frontend.

The runtime layer now resolves:
- generation admission caps
- mode-specific section, diagram, and QC concurrency
- shared timeout budgets, including whole-generation timeout math
- rerender budgets
- explicit per-node retry policies

It also adds runtime policy and runtime progress events so the UI can show the actual policy in force and truthful queued/running/completed counts while preserving the existing section stream behavior.

## Key Changes

### Backend runtime policy

- Added a dedicated runtime policy resolver in `backend/src/pipeline/runtime_policy.py`.
- Added process-local runtime context registration and limiter ownership in `backend/src/pipeline/runtime_context.py`.
- Added a central runtime progress tracker in `backend/src/pipeline/runtime_progress.py`.
- Extended `backend/src/core/config.py` so env-backed settings are the only source of runtime policy values.
- Updated generation admission and whole-generation timeout handling in `backend/src/generation/service.py`.

### Pipeline execution

- Wired runtime context creation and teardown through `backend/src/pipeline/run.py`.
- Applied section limiter acquisition before section work begins in `backend/src/pipeline/nodes/process_section.py`.
- Applied diagram and QC limiter/progress handling in the section runner and graph execution path.
- Moved node retry policy selection to the runtime layer and passed explicit retry policies into pipeline `run_llm` calls.
- Split diagram timeout behavior into inner retry timeout and outer node-budget timeout while preserving the image-first fallback path.

### Streaming and frontend

- Added `runtime_policy` and `runtime_progress` backend event shapes in `backend/src/pipeline/events.py`.
- Surfaced runtime policy/progress through `backend/src/generation/routes.py` and the generation event stream helpers.
- Updated frontend generation stream types and Teacher Studio rendering so the current policy and live queue/running counters are visible in the UI.

### Env and docs

- Replaced stale policy-like env examples with the live runtime-policy surface in `.env.example`, `backend/.env.example`, and `docker-compose.yml`.
- Documented the new configuration surface in `README.md`.

## Validation Evidence

- `python tools/agent/validate_repo.py --scope all`
- `python tools/agent/check_architecture.py --format text`

Result:
- `backend-ruff`: passed
- `backend-pytest`: 198 passed
- `frontend-check`: passed
- `frontend-build`: passed
- `tooling-pytest`: 8 passed
- `architecture`: no architecture violations found

### Targeted coverage added

- Backend settings/env coverage in `backend/tests/config/test_settings_bootstrap.py`
- Backend runtime policy/progress coverage in `backend/tests/pipeline/test_runtime_policy.py`
- Backend route and SSE coverage in `backend/tests/routes/test_api.py`
- Frontend event typing and generation view coverage in the Teacher Studio/component test suite

## Risks And Follow-up

- Interaction concurrency remains intentionally deferred because the current interaction path is deterministic and not an expensive generation bottleneck.
- Diagram generation now blends existing image-first behavior with the new timeout and retry model; that path is worth watching in live telemetry after rollout.
- A pre-existing whitespace-only change in `backend/tests/routes/test_blocks_generate.py` should stay out of the final commit.
- LangGraph still emits a non-failing annotation warning during graph compile about `RunnableConfig | None`; validation passes despite the warning.
