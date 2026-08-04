# Handoff: Shell Platform Restructure + Generation Runtime Refresh

**PR**: [#15](https://github.com/richiewaweru/text-book-generator/pull/15)  
**Merge commit**: `52ca915`  
**Primary commits**: `7a08b60`, `f549ca6`, `dd0f17a`  
**Date**: `2026-03-31`  
**Status**: merged to `main`

---

## Context

This change was the large platform restructure that moved the backend from the older `textbook_agent` package layout into the current explicit package split:

- `backend/src/core/`
- `backend/src/generation/`
- `backend/src/planning/`
- `backend/src/telemetry/`
- `backend/src/pipeline/`
- `backend/src/app.py`

The goal was to make the runtime boundaries match the project architecture docs and the guard scripts, while also keeping Teacher Studio, generation, telemetry, and the native Lectio frontend flow working on the new layout.

---

## What Changed

## 1. Backend package split and composition root

The old `backend/src/textbook_agent/` tree was flattened and replaced by top-level packages with narrower responsibilities.

### New package ownership

| Package | Role |
| --- | --- |
| `core/` | auth, config, database, shared entities, shared repositories, shared LLM utilities, error handling, and core HTTP routes |
| `generation/` | generation DTOs, persistence, routes, orchestration, recovery, and report recording bridge code |
| `planning/` | Teacher Studio planning models, prompt building, route layer, and section/spec generation |
| `telemetry/` | report persistence, telemetry APIs, LLM call persistence, and monitoring/service glue |
| `pipeline/` | standalone generation engine, prompts, contracts, nodes, providers, and execution runtime |

### Main composition entrypoint

- `backend/src/app.py` is now the FastAPI composition root
- it wires the route groups from `core`, `planning`, `generation`, and `telemetry`
- startup now handles migration, telemetry monitor configuration, runtime metadata, and stale generation cleanup

### Removed legacy layout

The old `backend/src/textbook_agent/` modules were deleted after their responsibilities were moved into the new top-level packages.

---

## 2. Data/storage/runtime infrastructure

The restructure also added operational plumbing that did not exist in the same explicit form before.

### Database + migration layer

- Alembic config was added through `backend/alembic.ini`
- migration runner and env files live under `backend/src/core/database/migrations/`
- committed migrations now include:
  - initial schema
  - JSON generation storage
  - LLM call persistence
  - relaxed LLM call generation id
  - generation heartbeat
  - lesson shares

### Runtime and deployment scaffolding

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`
- root `.env.example`
- backend `.env.example`
- helper scripts:
  - `backend/scripts/migrate_sqlite_to_postgres.py`
  - `backend/scripts/phase5_smoke.py`

These changes make local environment bootstrap, container execution, and DB migration behavior much more explicit than the previous setup.

---

## 3. Generation package ownership

Generation is no longer just the old route layer pasted into the flattened tree. It now owns clearer app responsibilities.

### Important files

- `backend/src/generation/routes.py`
- `backend/src/generation/service.py`
- `backend/src/generation/dependencies.py`
- `backend/src/generation/repositories/`
- `backend/src/generation/entities/`
- `backend/src/generation/dtos/`

### Notable behavior

- generation routes remain the public entrypoint for `/api/v1/generations` flows
- generation still bridges planning specs into pipeline execution
- document persistence and report persistence are wired through dedicated repository packages
- stale generation recovery stayed intact during the move

### Architecture fix made during publish

During validation, the architecture guard failed because a block-generation route had been placed in `core` while importing directly from `pipeline`.

That was corrected before publish by:

- deleting `backend/src/core/routes/blocks.py`
- moving the endpoint registration into `backend/src/generation/routes.py`
- updating the associated route tests

This matters because it was the only architecture violation discovered during the publish pass, and it was fixed before the PR merged.

---

## 4. Planning + pipeline runtime changes

The restructure also included substantive runtime updates, not just file moves.

### Planning

Key files:

- `backend/src/planning/dtos.py`
- `backend/src/planning/llm_config.py`
- `backend/src/planning/models.py`
- `backend/src/planning/prompt_builder.py`
- `backend/src/planning/routes.py`
- `backend/src/planning/service.py`

Planning was aligned to the new shell structure so Teacher Studio continues to feed committed planning specs into generation without importing pipeline internals directly.

### Pipeline

Key files:

- `backend/src/pipeline/adapter.py`
- `backend/src/pipeline/block_generate.py`
- `backend/src/pipeline/contracts.py`
- `backend/src/pipeline/events.py`
- `backend/src/pipeline/llm_runner.py`
- `backend/src/pipeline/providers/registry.py`
- `backend/src/pipeline/prompts/block_gen.py`
- `backend/src/pipeline/run.py`

Notable runtime additions/changes:

- single-block generation support became first-class through `block_generate.py`
- prompt and contract loading were updated around the current Lectio component registry
- runner/provider wiring was simplified
- telemetry/reporting hooks remained connected after the move
- pipeline stayed architecture-guard clean with no imports from `generation`, `planning`, or `telemetry`

---

## 5. Telemetry extraction

Telemetry moved into its own package rather than living as loosely grouped report code.

### Key files

- `backend/src/telemetry/routes.py`
- `backend/src/telemetry/service.py`
- `backend/src/telemetry/recorder.py`
- `backend/src/telemetry/repositories/sql_llm_call_repo.py`
- `backend/src/telemetry/repositories/sql_generation_report_repo.py`

### Why this matters

- report recording and LLM-call persistence are easier to reason about
- telemetry boundaries are now explicit and match `agents/project.md`
- route/service/repository ownership is no longer mixed with generation package concerns

---

## 6. Frontend alignment

The frontend was updated to match the new backend runtime shape rather than remaining pinned to older assumptions.

### Key files touched

- `frontend/src/routes/dashboard/+page.svelte`
- `frontend/src/routes/textbook/[id]/page.test.ts`
- `frontend/src/lib/components/ProfileForm.svelte`
- `frontend/src/lib/components/TeacherStudio.svelte`
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/errors.ts`
- `frontend/src/lib/types/index.ts`

### Main themes

- dashboard and textbook-view flows were kept aligned with generation-centric fetching
- Teacher Studio and ProfileForm still use Lectio template/preset metadata
- error handling and test coverage were updated for the new API behavior
- viewer-related types/tests stayed compatible with native Lectio section rendering

---

## 7. Tooling and docs

The restructure included repo-governance updates so the codebase and the checks describe the same shape.

### Tooling

- `tools/agent/check_architecture.py`
- `tools/agent/validate_repo.py`
- `tools/agent/tests/test_check_architecture.py`

### Docs

- `docs/project/ARCHITECTURE.md`
- `docs/project/SETUP.md`
- `docs/project/DEVELOPMENT_WORKFLOW.md`
- `docs/project/SCHEMAS.md`
- `docs/project/agent-context.md`
- `docs/project/context-summary.yaml`

These docs were refreshed so the new package split, validation commands, and boundary rules are documented instead of implied.

---

## Validation

The merged work passed both local and GitHub validation after the follow-up CI fixes landed.

### Local validation run before merge

- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope all`

### Local results

- architecture guard: passed
- backend ruff: passed
- backend pytest: `182 passed`
- frontend check: passed
- frontend build: passed
- tooling pytest: `8 passed`

### GitHub required checks on PR #15

- `agent-governance`: passed
- `architecture-guard`: passed
- `backend-quality`: passed
- `frontend-quality`: passed

---

## Known Follow-Ups / Risks

### 1. Lectio packaging is still temporary

The frontend dependency on `lectio` is currently satisfied by vendored built artifacts and committed contract exports. That was necessary to make CI self-contained, but it is not the ideal long-term package flow.

See the companion handoff:

- `docs/project/handoff-lectio-ci-temporary-vendoring.md`

### 2. Frontend chunking warnings still exist

Before the final vendored setup reduced the direct CI failure, the frontend build was already surfacing chunking/circular-bundle concerns around Lectio runtime/template bundles. The build is green, but chunk strategy should still be revisited later if bundle hygiene becomes a priority.

### 3. This was a broad structural merge

Future work on top of this change should prefer smaller PRs because:

- regressions are easier to isolate
- ownership boundaries are now explicit
- package-level drift will be easier to spot if follow-ups are scoped narrowly

---

## Where To Start

If someone needs to resume work or audit the current state, start here:

1. `backend/src/app.py`
2. `backend/src/core/`
3. `backend/src/generation/routes.py`
4. `backend/src/planning/routes.py`
5. `backend/src/pipeline/`
6. `docs/project/ARCHITECTURE.md`
7. `docs/project/agent-context.md`

If the question is specifically about CI/package behavior, start with the companion handoff instead of this one.

