# Phase 2 Handoff — Runtime Logic Implementation

**Date:** 2026-03-11
**Branch:** `feature/phase-2-runtime-logic`
**Base commit:** `e8796d6` (Phase 1 skeleton + Phase 1 handoff)
**Status:** Phase 2 COMPLETE — all runtime logic implemented, 64 tests passing, 0 lint errors

---

## What Was Done

Phase 2 brought the Phase 1 skeleton to life. Every `raise NotImplementedError` stub in the backend has been replaced with working runtime logic. The full pipeline now runs end-to-end: `LearnerProfile JSON → pipeline → rendered HTML textbook`.

### Implementation Summary

| Step | Component | Files Changed/Created | Status |
|------|-----------|----------------------|--------|
| 1 | MockProvider + test infrastructure | `tests/conftest.py` | Done |
| 2 | Prompt builder tests | `tests/domain/test_prompts.py` (new) | Done |
| 3 | AnthropicProvider.complete() | `infrastructure/providers/anthropic_provider.py` | Done |
| 4 | OpenAIProvider.complete() | `infrastructure/providers/openai_provider.py` | Done |
| 5 | 5 LLM pipeline nodes | `domain/services/{planner,content_generator,diagram_generator,code_generator,quality_checker}.py` | Done |
| 6 | AssemblerNode (pure Python) | `domain/services/assembler.py` | Done |
| 7 | HTML Renderer + CSS + Jinja2 | `infrastructure/renderer/{html_renderer.py,assets/base.css,assets/prism.css,templates/textbook.html.j2}`, `tests/infrastructure/test_renderer.py` | Done |
| 8 | Orchestrator | `application/orchestrator.py`, `tests/application/test_orchestrator.py` | Done |
| 9 | Use cases | `application/use_cases/{generate_textbook,check_quality}.py` | Done |
| 10 | API routes + background tasks | `interface/api/{routes/generation.py,dependencies.py,app.py}`, `tests/interface/test_api.py` | Done |
| 11 | Frontend API wiring | `frontend/src/{lib/api/client.ts,routes/+page.svelte,routes/textbook/[id]/+page.svelte}` | Done |

### New Files Created

- `backend/src/textbook_agent/infrastructure/providers/json_utils.py` — shared JSON extraction helper (strips markdown code fences)
- `backend/src/textbook_agent/domain/ports/renderer.py` — `RendererPort` abstract interface (DDD compliance)
- `backend/src/textbook_agent/infrastructure/renderer/templates/textbook.html.j2` — Jinja2 template
- `backend/tests/domain/test_prompts.py` — 18 prompt builder tests
- `backend/tests/domain/test_nodes.py` — 8 pipeline node tests
- `backend/tests/infrastructure/test_renderer.py` — 8 renderer tests
- `backend/tests/application/__init__.py` — package init
- `backend/tests/application/test_orchestrator.py` — 3 orchestrator tests

---

## Architecture Decisions Made During Phase 2

### 1. RendererPort abstraction
The orchestrator (`application` layer) was initially importing `HTMLRenderer` directly from `infrastructure`, violating DDD layering. Fixed by introducing `domain/ports/renderer.py` with a `RendererPort` ABC. `HTMLRenderer` now implements `RendererPort`, and the orchestrator depends only on the port.

### 2. Provider initialization
`dependencies.py` now passes `api_key` and `model` from `Settings` to the provider factory. Previously it called `ProviderFactory.get(name)` with no credentials.

### 3. Background task via asyncio.create_task
`POST /api/v1/generate` returns 202 immediately and spawns the generation via `asyncio.create_task()`. Status is tracked in an in-memory `dict[str, GenerationStatus]` on `app.state.jobs`. This avoids Celery/Redis complexity while supporting progress polling.

### 4. Progress callback
`TextbookAgent` accepts an optional `on_progress: Callable[[str], None]` callback. The API route uses this to update the job store at each node boundary, enabling real-time progress tracking via `GET /api/v1/status/{id}`.

### 5. Prompt builders were already implemented
The Phase 1 handoff stated prompt builders were stubbed, but they were actually fully implemented in the Phase 1 commit. Phase 2 added comprehensive tests (18 tests in `test_prompts.py`).

---

## Test Coverage

**Total: 64 tests, all passing**

| Module | Tests | Description |
|--------|-------|-------------|
| `tests/domain/test_entities.py` | 12 | Entity schema validation |
| `tests/domain/test_prompts.py` | 18 | Prompt builder output validation |
| `tests/domain/test_nodes.py` | 8 | Pipeline node execution with MockProvider |
| `tests/infrastructure/test_providers.py` | 4 | Provider factory |
| `tests/infrastructure/test_renderer.py` | 8 | HTML rendering output |
| `tests/application/test_orchestrator.py` | 3 | Full pipeline with MockProvider |
| `tests/interface/test_api.py` | 5 | Health, generate (202), status (404), poll-to-completion |
| `tests/tooling/` | 6 | Architecture guard + commit tooling |

---

## Key Files Reference

### Backend — Domain Layer (no framework imports)
- `domain/ports/llm_provider.py` — `BaseProvider` interface
- `domain/ports/renderer.py` — `RendererPort` interface (NEW)
- `domain/ports/textbook_repository.py` — `TextbookRepository` interface
- `domain/services/planner.py` — `CurriculumPlannerNode`
- `domain/services/content_generator.py` — `ContentGeneratorNode`
- `domain/services/diagram_generator.py` — `DiagramGeneratorNode`
- `domain/services/code_generator.py` — `CodeGeneratorNode`
- `domain/services/assembler.py` — `AssemblerNode` (pure Python, no LLM)
- `domain/services/quality_checker.py` — `QualityCheckerNode`
- `domain/prompts/` — All prompt builders (planner, content, diagram, code, quality)

### Backend — Application Layer
- `application/orchestrator.py` — `TextbookAgent.generate()` — full pipeline orchestration
- `application/use_cases/generate_textbook.py` — `GenerateTextbookUseCase`
- `application/use_cases/check_quality.py` — `CheckQualityUseCase`

### Backend — Infrastructure Layer
- `infrastructure/providers/anthropic_provider.py` — Anthropic SDK integration
- `infrastructure/providers/openai_provider.py` — OpenAI SDK integration
- `infrastructure/providers/json_utils.py` — JSON extraction helper (NEW)
- `infrastructure/renderer/html_renderer.py` — Jinja2 + CSS renderer
- `infrastructure/renderer/templates/textbook.html.j2` — HTML template (NEW)
- `infrastructure/renderer/assets/base.css` — Full dark-theme design system
- `infrastructure/renderer/assets/prism.css` — Code syntax highlighting

### Backend — Interface Layer
- `interface/api/routes/generation.py` — POST /generate (202), GET /status/{id}, GET /textbook/{path}
- `interface/api/dependencies.py` — DI container with proper credential passing
- `interface/api/app.py` — FastAPI app with job store in state
- `interface/cli/main.py` — CLI stub (not implemented, not in scope)

### Frontend
- `src/lib/api/client.ts` — `startGeneration()`, `pollUntilDone()`, `getGenerationStatus()`
- `src/routes/+page.svelte` — Profile form → generate → poll → redirect to viewer
- `src/routes/textbook/[id]/+page.svelte` — Fetch and display generated HTML

---

## What Is NOT Done (Phase 3 Candidates)

1. **CLI implementation** — `interface/cli/main.py` remains a stub. Deliberately excluded from Phase 2 scope.
2. **Quality loop re-run** — `QualityChecker` generates a report but does not re-run failed nodes. Phase 3 concern.
3. **PDF output** — Only HTML rendering is implemented. PDF would require a new `RendererPort` implementation.
4. **Real LLM integration tests** — All tests use `MockProvider`. Tests marked `@pytest.mark.integration` for real LLM calls do not exist yet.
5. **Frontend styling** — Frontend components have no CSS. Only functional wiring was implemented.
6. **Authentication/rate limiting** — CORS is `*`, no auth on endpoints.
7. **Persistent job storage** — Jobs are in-memory only (`app.state.jobs` dict). Server restart loses all state.
8. **Error recovery** — No retry at the API level if a generation fails.

---

## How to Verify

```bash
# Backend tests (all 64 should pass)
cd backend && uv run pytest tests/ -v

# Lint (should be clean)
cd backend && uv run ruff check src/ tests/

# Start backend server
cd backend && uv run uvicorn textbook_agent.interface.api.app:app --reload

# Start frontend
cd frontend && npm run dev

# Test API manually
# POST http://localhost:8000/api/v1/generate with body:
# {"subject": "algebra", "age": 14, "context": "test", "depth": "survey", "language": "plain"}
# -> Returns 202 with generation_id
# GET http://localhost:8000/api/v1/status/{generation_id}
# -> Returns GenerationStatus with progress updates

# Health check
# GET http://localhost:8000/health -> {"status": "ok", "version": "0.1.0"}
```

---

## For the Next Agent

If you are picking up this project:

1. **Run `cd backend && uv run pytest`** to verify everything is green.
2. **Read `CLAUDE.md`** at project root for project conventions.
3. **Read `docs/PROPOSAL_v1.0.md`** for the full product spec.
4. The **architecture guard** (`tests/tooling/test_check_architecture.py`) enforces DDD layer boundaries. If you get a violation, you likely need to create a port in `domain/ports/` rather than importing infrastructure directly.
5. **All LLM nodes follow the same pattern**: build prompt → `asyncio.to_thread(provider.complete, ...)` → return result. The `PipelineNode.execute()` base handles validation and retry.
6. **MockProvider** in `conftest.py` returns canned Pydantic instances keyed by `response_schema` type. To test a new node, add a canned response to `_MOCK_RESPONSES`.
7. **The CLI is intentionally unimplemented** — focus is on API + frontend.
