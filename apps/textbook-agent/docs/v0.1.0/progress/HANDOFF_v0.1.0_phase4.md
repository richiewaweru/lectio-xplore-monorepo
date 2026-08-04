# Phase 3.2–4.0 Handoff — Runtime Logic & Pipeline Hardening

**Date:** 2026-03-12
**Branch:** `feature/phase-2-runtime-logic`
**Base:** Phase 3.1 complete (76 tests, 0 lint errors)
**Status:** COMPLETE — 88 tests passing, 2 integration tests (deselected by default), 0 lint errors, 0 frontend type errors

---

## What Changed

Three phases implemented in 11 commits, covering persistent job storage, quality re-run logic, real LLM integration tests, structured error handling, and exponential backoff.

### Phase 3.2: Persistent Job Storage + Generation History

| # | Commit | Summary |
|---|--------|---------|
| 1 | `d7a65b9` | Generation entity + GenerationRepository port in domain layer |
| 2 | `87f6918` | SqlGenerationRepository — async SQLAlchemy implementation |
| 3 | `d69d05a` | Wire DB persistence into /generate route + add GET /generations and GET /generations/{id} |
| 4 | `51b0270` | Frontend dashboard shows past generations with status badges and view links |

### Phase 3.3: Quality Re-Run Loop

| # | Commit | Summary |
|---|--------|---------|
| 5 | `fb23632` | `decide_reruns()` — extracts error-severity section IDs from QualityReport |
| 6 | `46758b3` | Orchestrator re-runs only flagged sections (content + diagram + code), re-assembles, re-checks quality |
| 7 | `39699cb` | `max_quality_reruns` config in Settings, wired through dependencies |

### Phase 4.0: Real LLM Integration Tests + Error Hardening

| # | Commit | Summary |
|---|--------|---------|
| 8 | `675e8e8` | Integration tests with real Anthropic API (marked, skipped by default) |
| 9 | `fd498b8` | Structured error handler middleware — PipelineError/ProviderConformanceError → JSON |
| 10 | `b83d2db` | Exponential backoff on node retries (`base_delay * 2^attempt`) |
| 11 | `b8c471d` | Frontend displays user-friendly error messages by error_type |

---

## Current State

### What works
- Generation jobs persist to SQLite via SqlGenerationRepository — survive server restarts
- Dashboard shows past generations with status, date, generation time, and clickable view links
- QualityChecker failures trigger targeted re-runs of only error-severity sections (capped at `max_quality_reruns`)
- Pipeline nodes retry with exponential backoff (configurable `retry_base_delay`)
- API returns structured error JSON with `error_type` classification
- Frontend maps error types to human-friendly messages
- Integration tests prove real LLM round-trip (planner + content generator)

### What doesn't work / known gaps
- `.env.example` files contain a real Google Client ID (should be reverted to placeholder — not part of this branch's scope)
- No Alembic migrations — relies on `create_all()` for new columns. Existing databases need manual `ALTER TABLE` or DB deletion
- Integration tests require `ANTHROPIC_API_KEY` in env — CI will skip them

---

## Detailed File Changes

### Domain Layer (new)

| File | Change |
|------|--------|
| `domain/entities/generation.py` | **Created** — Generation entity (id, user_id, subject, context, status, output_path, error, quality_passed, generation_time_seconds, timestamps) |
| `domain/ports/generation_repository.py` | **Created** — abstract port: create, update_status, find_by_id, list_by_user |
| `domain/entities/__init__.py` | Added `Generation` export |
| `domain/services/rerun_strategy.py` | **Created** — `decide_reruns(report) -> list[str]` extracts error-severity section IDs |
| `domain/services/node_base.py` | Added exponential backoff: `asyncio.sleep(base_delay * 2**attempt)`, logging, `NodeValidationError` non-retriable |

### Application Layer

| File | Change |
|------|--------|
| `application/orchestrator.py` | Quality re-run loop: detect failed sections, re-generate content/diagram/code, re-assemble, re-check. Capped at `max_quality_reruns`. Reports `quality_reruns` count. |
| `application/dtos/generation_request.py` | Added `quality_reruns: int = 0` to GenerationResponse |
| `application/dtos/generation_status.py` | Added `error_type: str | None = None` |
| `application/use_cases/generate_textbook.py` | Passes `max_quality_reruns` through to orchestrator |

### Infrastructure Layer

| File | Change |
|------|--------|
| `infrastructure/database/models.py` | Extended GenerationModel: context, error, quality_passed, generation_time_seconds, completed_at columns |
| `infrastructure/repositories/sql_generation_repo.py` | **Created** — full async implementation, auto-sets completed_at on terminal statuses |
| `infrastructure/config/settings.py` | Added `max_quality_reruns: int = 2` |

### Interface Layer

| File | Change |
|------|--------|
| `interface/api/routes/generation.py` | DB writes on job start/complete/fail, GET /generations (paginated), GET /generations/{id} with ownership check, error_type classification |
| `interface/api/dependencies.py` | Added `get_generation_repository()` factory, passes `max_quality_reruns` to use case |
| `interface/api/middleware/error_handler.py` | **Created** — exception handlers for PipelineError (502), ProviderConformanceError (502), NodeValidationError (422) |
| `interface/api/app.py` | Registers error handlers |

### Frontend

| File | Change |
|------|--------|
| `src/lib/types/index.ts` | Added `GenerationHistoryItem` interface, `error_type` on GenerationStatus |
| `src/lib/api/client.ts` | Added `getGenerations(limit, offset)` |
| `src/routes/dashboard/+page.svelte` | Past Generations section, friendly error messages by type, status badge styling |

### Tests

| File | Change |
|------|--------|
| `tests/domain/test_entities.py` | +3 tests: Generation entity validation |
| `tests/domain/test_rerun_strategy.py` | **Created** — 4 tests for decide_reruns |
| `tests/domain/test_nodes.py` | +2 tests: retry with backoff timing validation |
| `tests/application/test_orchestrator.py` | +2 tests: RerunMockProvider for quality rerun loop, cap at max |
| `tests/infrastructure/test_generation_repo.py` | **Created** — 6 tests with in-memory SQLite |
| `tests/interface/test_api.py` | +3 tests: list_generations, generate_and_poll, structured error responses |
| `tests/integration/test_real_pipeline.py` | **Created** — 2 integration tests (planner + content gen with real API) |
| `backend/pyproject.toml` | Registered `integration` marker, excluded from default run |

---

## Validated

```
88 passed, 2 deselected in 16.22s
ruff: All checks passed!
svelte-check: 0 errors, 0 warnings
```

---

## Not Done Yet

In priority order:

1. **Alembic migration system** — currently relying on `create_all()`, which doesn't add columns to existing tables
2. **PDF export** — deferred until text pipeline proven with real LLMs
3. **Token refresh** — 7-day JWT sufficient for dev
4. **Rate limiting / CSRF / CSP** — separate security hardening phase
5. **Rich media (DALL-E, TTS)** — after pipeline is solid
6. **Executable notebooks** — future milestone

---

## Start Here

- **To verify**: `cd backend && uv run pytest` (88 pass), `uv run ruff check src/ tests/` (clean)
- **To run integration tests**: `ANTHROPIC_API_KEY=sk-... uv run pytest -m integration`
- **To extend the quality re-run loop**: see `application/orchestrator.py` lines 85–130, controlled by `domain/services/rerun_strategy.py`
- **To add new error types**: extend `interface/api/middleware/error_handler.py` and update `friendlyErrorMessage()` in the dashboard

---

## Risks

- **Database migration**: Any existing `textbook_agent.db` won't have the new Generation columns. Delete the DB file or run manual ALTER TABLEs.
- **In-memory + DB dual-write**: `app.state.jobs` dict still used for real-time polling; DB is source of truth for history. If these diverge, polling may show stale data until page refresh.
- **Quality re-run cost**: Each rerun iteration re-invokes the LLM for flagged sections. With `max_quality_reruns=2`, worst case is 3x the normal content generation cost for failing sections.

---

## For the Next Agent

1. **Generation entity** lives at `domain/entities/generation.py` — tracks every textbook generation job.
2. **DB persistence** is dual-write: `app.state.jobs` for real-time status polling + `SqlGenerationRepository` for history.
3. **Quality re-run** only re-generates sections with `severity == "error"` — warnings are ignored. See `domain/services/rerun_strategy.py`.
4. **Exponential backoff** is on `node_base.py` with `retry_base_delay = 1.0` (overridable per-node or in tests). `NodeValidationError` is never retried.
5. **Error classification**: `ProviderConformanceError` → `"provider_error"`, `PipelineError` → `"pipeline_error"`, anything else → `"unknown_error"`. Frontend maps these to friendly messages.
6. **Integration tests** use `claude-haiku-4-5-20251001` for cost. They're excluded from default `pytest` via `addopts = "-m 'not integration'"`.
