# Env-Backed Runtime Policy Handoff

**Extends**: `docs/project/runs/2026-04-02-env-backed-runtime-policy.md`  
**Status**: ready to merge  
**Branch**: `feat/env-backed-runtime-policy`

## What Changed

- Added env-backed runtime policy resolution for generation admission, mode-specific concurrency, timeout budgets, rerender limits, and explicit retry policies.
- Added process-local runtime context registration and runtime progress tracking for truthful queue/running/completed counters.
- Wired runtime policy and runtime progress events into the generation SSE stream while preserving existing `progress_update` compatibility.
- Updated Teacher Studio stream typing and status rendering so the frontend surfaces runtime policy values and live runtime counters.
- Updated env examples, Docker config, and README documentation to expose the new runtime-policy knobs cleanly.

## What Was Validated

- `python tools/agent/validate_repo.py --scope all`
- `python tools/agent/check_architecture.py --format text`
- Validation result: backend ruff passed, backend pytest passed with 198 tests, frontend check passed, frontend build passed, tooling pytest passed with 8 tests, architecture check passed.

## What Is Left

- Commit the coherent runtime-policy package.
- Push the feature branch, open the PR with the runbook/handoff links, and merge after the GitHub flow completes.

## Where To Start Next Time

1. `backend/src/pipeline/runtime_policy.py` for the env-to-policy mapping.
2. `backend/src/pipeline/runtime_context.py` and `backend/src/pipeline/runtime_progress.py` for limiter ownership and progress emission.
3. `backend/src/pipeline/run.py`, `backend/src/pipeline/nodes/process_section.py`, and `backend/src/pipeline/nodes/section_runner.py` for runtime enforcement.
4. `backend/src/generation/service.py` and `backend/src/generation/routes.py` for admission control and SSE delivery.
5. `frontend/src/lib/components/studio/GenerationView.svelte` and `frontend/src/routes/textbook/[id]/+page.svelte` for the UI surface.

## Notes

- Interaction concurrency is intentionally not part of this change.
- `backend/tests/routes/test_blocks_generate.py` formatting-only churn was intentionally excluded from the final package.
- LangGraph emits a non-failing graph compile warning about the `config` annotation shape during tests; the repo validation still passes.
