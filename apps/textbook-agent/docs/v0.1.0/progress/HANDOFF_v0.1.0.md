# Project Handoff Document — v0.1.0

> **Phase:** 1 (Skeleton Complete)
> **Commit:** `52413bd` — Phase 1 skeleton
> **Date:** 2026-03-11
> **Status:** All scaffolding done. Zero runtime logic implemented. Ready for Phase 2 feature work.

---

## 1. What This Project Is

An **AI-agnostic pipeline** that takes a learner profile (JSON) and produces a **personalized HTML textbook**. The system is provider-swappable (Claude / OpenAI) and enforces 7 pedagogical invariants on every piece of generated content.

**Scope boundaries (Phase 1):**
- IN: profile JSON -> structured curriculum -> content -> diagrams -> code -> assembled HTML
- OUT: no chatbot, no audio, no runnable code cells, no user accounts

---

## 2. Architecture Decisions

### 2.1 Domain-Driven Design (4-Layer)

```
Interface  ->  Application  ->  Domain  <-  Infrastructure
(FastAPI,      (Use cases,      (Entities,    (LLM providers,
 CLI)           orchestrator)    nodes,         storage,
                                 ports)         renderer)
```

**The dependency rule:** Domain never imports from any other layer. Infrastructure implements domain ports via dependency inversion. This was chosen to keep LLM provider logic completely decoupled from business rules.

### 2.2 Pipeline Node Architecture

Every pipeline step is a `PipelineNode[TInput, TOutput]` generic:
- Input/output are **always Pydantic models** (schema-validated)
- Built-in retry logic (`max_retries=2`, configurable)
- The `execute()` wrapper handles validation + retry; subclasses only implement `run()`
- If validation fails after all retries -> `PipelineError` with node name + reason

**Why this matters:** Malformed LLM output cannot silently corrupt downstream nodes. The pipeline is self-healing up to `max_retries` attempts.

### 2.3 Provider Agnosticism

All LLM calls go through `BaseProvider.complete(system_prompt, user_prompt, response_schema)`. Swapping providers is a config change (`PROVIDER=openai` in `.env`), not a code change. The `ProviderFactory` registry pattern makes this extensible.

### 2.4 Pedagogical Rules as First-Class Concern

`BASE_PEDAGOGICAL_RULES` (7 invariants) lives in `domain/prompts/base_prompt.py` and is injected into every content-generating node's system prompt. These rules are sacred — they define what makes this a *pedagogically sound* textbook generator rather than a generic text generator.

### 2.5 Renderer is Dumb

`HTMLRenderer` has zero LLM calls. It receives a fully assembled `RawTextbook` and mechanically converts it to HTML via Jinja2. All intelligence lives in the pipeline nodes.

---

## 3. What Has Been Accomplished

### 3.1 Fully Implemented (Production-Ready)

| Component | Location | Notes |
|-----------|----------|-------|
| All 7 Pydantic entities | `domain/entities/` | LearnerProfile, CurriculumPlan, SectionSpec, SectionContent, SectionDiagram, SectionCode, RawTextbook, QualityReport |
| 3 value object enums | `domain/value_objects/` | Depth, NotationLanguage, SectionDepth |
| 3 abstract ports | `domain/ports/` | BaseProvider, FileStoragePort, TextbookRepository |
| Pipeline node base class | `domain/services/node_base.py` | Generic with retry + validation |
| Domain exceptions | `domain/exceptions.py` | PipelineError, NodeValidationError, ProviderConformanceError |
| Planner prompt builder | `domain/prompts/planner_prompts.py` | Demonstrates the prompt-building pattern |
| BASE_PEDAGOGICAL_RULES | `domain/prompts/base_prompt.py` | 7 invariants |
| Application DTOs | `application/dtos/` | GenerationRequest, GenerationResponse, GenerationStatus, GenerationProgress |
| Provider factory | `infrastructure/providers/factory.py` | Registry pattern, returns correct provider by name |
| Settings config | `infrastructure/config/settings.py` | Pydantic Settings, auto-loads from `.env` |
| File storage | `infrastructure/storage/file_storage.py` | Reads profiles, writes outputs |
| File repository | `infrastructure/repositories/file_textbook_repo.py` | Saves HTML + metadata JSON |
| FastAPI app factory | `interface/api/app.py` | CORS, health router, generation router |
| Health check endpoint | `interface/api/routes/health.py` | `GET /health` -> `{"status":"ok","version":"0.1.0"}` |
| Dependency injection | `interface/api/dependencies.py` | Wires settings -> provider -> repository -> orchestrator |
| Frontend types | `frontend/src/lib/types/index.ts` | TypeScript mirrors of all Pydantic schemas |
| Frontend API client | `frontend/src/lib/api/client.ts` | `generateTextbook()`, `getGenerationStatus()`, `healthCheck()` |
| Frontend components | `frontend/src/lib/components/` | ProfileForm, GenerationProgress, TextbookViewer |
| Frontend routing | `frontend/src/routes/` | Home page + `/textbook/[id]` viewer |
| 20 passing tests | `backend/tests/` | Entity validation, provider factory, API endpoints |
| 3 test fixtures | `backend/tests/fixtures/` | Beginner (algebra/14), Intermediate (calculus/17), Advanced (lin. alg./22) |
| Full documentation | `docs/v0.1.0/` | Architecture, Setup, Schemas, Development Workflow |

### 3.2 Stubbed (Skeleton Only — `NotImplementedError`)

| Component | Location | What It Needs |
|-----------|----------|---------------|
| CurriculumPlannerNode | `domain/services/planner.py` | LLM call via provider to generate CurriculumPlan from LearnerProfile |
| ContentGeneratorNode | `domain/services/content_generator.py` | LLM call to generate SectionContent per section |
| DiagramGeneratorNode | `domain/services/diagram_generator.py` | LLM call to generate SVG diagrams |
| CodeGeneratorNode | `domain/services/code_generator.py` | LLM call to generate code examples |
| AssemblerNode | `domain/services/assembler.py` | Pure Python assembly (NO LLM), `retry_on_failure=False` |
| QualityCheckerNode | `domain/services/quality_checker.py` | LLM call to evaluate textbook quality |
| 4 prompt builders | `domain/prompts/{content,diagram,code,quality}_prompts.py` | Follow pattern from `planner_prompts.py` |
| AnthropicProvider.complete() | `infrastructure/providers/anthropic_provider.py` | Anthropic API structured output call |
| OpenAIProvider.complete() | `infrastructure/providers/openai_provider.py` | OpenAI API structured output call |
| HTMLRenderer.render() | `infrastructure/renderer/html_renderer.py` | Jinja2 template + CSS assembly |
| TextbookAgent.generate() | `application/orchestrator.py` | Chain all 6 nodes + renderer + save |
| 2 use cases | `application/use_cases/` | Thin wrappers calling orchestrator |
| Generation API routes | `interface/api/routes/generation.py` | Currently return HTTP 501 |
| CLI logic | `interface/cli/main.py` | Argument parsing done, execution logic missing |
| Frontend API wiring | `frontend/src/routes/+page.svelte` | TODO: call `generateTextbook()` |
| Frontend textbook fetch | `frontend/src/routes/textbook/[id]/+page.svelte` | TODO: fetch HTML from backend |

---

## 4. Implementation Order for Phase 2

Per the proposal and `DEVELOPMENT_WORKFLOW.md`, build in this dependency order:

### Step 1: LLM Provider Implementations
**Files:** `infrastructure/providers/anthropic_provider.py`, `openai_provider.py`

Implement `complete()` method:
- Accept `system_prompt`, `user_prompt`, `response_schema` (Pydantic model class)
- Call the provider's API with structured output / JSON mode
- Parse response into `response_schema` instance
- Return validated Pydantic object

**Test:** Create a mock provider for unit tests. Integration tests with real API keys are optional.

### Step 2: Prompt Builders
**Files:** `domain/prompts/{content,diagram,code,quality}_prompts.py`

Follow the pattern from `planner_prompts.py`:
- Inject `BASE_PEDAGOGICAL_RULES`
- Include learner context (age, depth, language)
- Specify expected JSON schema in the prompt
- Return formatted system prompt string

### Step 3: Pipeline Nodes (in order)
1. **CurriculumPlannerNode** — Most critical. Generates the section plan that drives everything else.
2. **ContentGeneratorNode** — Called once per section. Produces 6 pedagogical fields.
3. **DiagramGeneratorNode** — Called for sections where `needs_diagram=True`. Produces SVG.
4. **CodeGeneratorNode** — Called for sections where `needs_code=True`. Produces code + explanation.
5. **AssemblerNode** — Pure Python. Combines all outputs into `RawTextbook`. No LLM.
6. **QualityCheckerNode** — Evaluates the assembled textbook. Returns pass/fail + issues.

### Step 4: Orchestrator
**File:** `application/orchestrator.py`

Wire the 6 nodes together:
```
profile -> planner -> [content, diagrams, code] per section -> assembler -> quality check
```

Handle the quality loop: if QualityChecker flags issues, re-run flagged nodes.

### Step 5: HTML Renderer
**File:** `infrastructure/renderer/html_renderer.py`

Create Jinja2 template that produces self-contained HTML:
- CSS from `renderer/assets/base.css` and `prism.css` (already exist)
- Embed SVG diagrams inline
- Syntax-highlighted code blocks
- Table of contents from CurriculumPlan

### Step 6: Wire Interface Layer
- Update `generation.py` routes to call use cases (replace 501 stubs)
- Implement CLI execution logic
- Wire frontend to call real API endpoints

### Step 7: End-to-End Testing
- Run all 3 fixtures through the full pipeline
- Verify HTML output is valid and readable
- Check quality reports pass for all profiles

---

## 5. Known Issues & Potential Pitfalls

### 5.1 Watch Out For

| Issue | Where | Risk | Mitigation |
|-------|-------|------|------------|
| **Domain importing infrastructure** | Any `domain/` file | Breaks DDD contract | Never import from `infrastructure/` or `interface/` in domain. Use ports. |
| **LLM calls outside providers** | Pipeline nodes | Coupling to specific API | All LLM calls MUST go through `BaseProvider.complete()` |
| **Missing BASE_PEDAGOGICAL_RULES injection** | New prompt builders | Pedagogically unsound output | Every content-generating prompt builder must include the rules |
| **Schema drift between backend/frontend** | Entity changes | Type errors at runtime | Update `frontend/src/lib/types/index.ts` whenever Pydantic schemas change |
| **XSS via TextbookViewer** | `frontend/src/lib/components/TextbookViewer.svelte` | Security vulnerability | Uses `{@html}` — ensure all HTML is sanitized by backend renderer |
| **Provider API key missing** | `.env` file | Runtime crash | Check for empty key before making API calls, fail fast with clear message |
| **uv not on PATH (Windows)** | Development setup | Commands fail | Run `export PATH="$HOME/.local/bin:$PATH"` or use full path |
| **Async consistency** | Node `run()` methods | Mixed sync/async | All nodes are async. Provider `complete()` must also be async. |
| **Test expectations after implementation** | `test_api.py` | Tests expect 501 | Update tests to expect 200 with real responses once routes are implemented |

### 5.2 Design Decisions That Should NOT Be Changed

1. **Pipeline node base class** — The generic `PipelineNode[TInput, TOutput]` with `execute()` wrapper is load-bearing. Don't bypass it.
2. **Pydantic schema validation** — Every inter-node contract is a Pydantic model. Don't pass raw dicts.
3. **Provider factory pattern** — Don't instantiate providers directly. Always use `ProviderFactory.get()`.
4. **BASE_PEDAGOGICAL_RULES** — These 7 rules are non-negotiable. They define the product's pedagogical identity.
5. **Assembler has no LLM** — It's pure mechanical assembly. Keep it that way.
6. **4-layer DDD** — Interface -> Application -> Domain <- Infrastructure. Don't shortcut.

### 5.3 Design Decisions That CAN Be Evolved

1. **CORS `allow_origins=["*"]`** — Fine for dev, should be restricted for production
2. **File-based storage** — `FileTextbookRepository` works for Phase 1. Could move to DB later.
3. **Synchronous generation** — Current API stubs are synchronous. May need background tasks (Celery/ARQ) for real generation that takes minutes.
4. **Frontend styling** — Minimal/unstyled currently. Can add Tailwind, design system, etc.
5. **Additional providers** — Factory supports registration of new providers beyond Claude/OpenAI.

---

## 6. Test Fixtures Reference

Three learner profiles exercise different complexity levels:

### Beginner (`tests/fixtures/stem_beginner.json`)
```json
{
  "subject": "algebra",
  "age": 14,
  "context": "Just starting out. Letters in math confuse me.",
  "depth": "survey",
  "language": "plain"
}
```

### Intermediate (`tests/fixtures/stem_intermediate.json`)
```json
{
  "subject": "calculus",
  "age": 17,
  "context": "I understand derivatives but integration confuses me.",
  "depth": "standard",
  "language": "math_notation"
}
```

### Advanced (`tests/fixtures/stem_advanced.json`)
```json
{
  "subject": "linear algebra",
  "age": 22,
  "context": "Need eigenvalues, eigenvectors, and SVD for machine learning applications.",
  "depth": "deep",
  "language": "math_notation"
}
```

**Every pipeline node must handle all three profiles correctly.** Use these as your primary test inputs.

---

## 7. Quick Start for the Next Developer

```bash
# 1. Clone and navigate
cd "c:/Projects/Textbook agent"

# 2. Backend setup
cd backend
export PATH="$HOME/.local/bin:$PATH"  # Windows: ensure uv is on PATH
uv sync --all-extras
cp .env.example .env
# Edit .env: add your ANTHROPIC_API_KEY or OPENAI_API_KEY

# 3. Verify everything works
uv run pytest              # Should see 20 passing
uv run uvicorn textbook_agent.interface.api.app:app --reload
# Visit http://localhost:8000/health -> {"status":"ok","version":"0.1.0"}

# 4. Frontend setup (separate terminal)
cd ../frontend
npm install
cp .env.example .env
npm run dev
# Visit http://localhost:5173

# 5. Key docs to read
# - docs/PROPOSAL_v1.0.md           (product specification)
# - docs/v0.1.0/ARCHITECTURE.md     (system design)
# - docs/v0.1.0/SCHEMAS.md          (entity reference)
# - docs/v0.1.0/DEVELOPMENT_WORKFLOW.md  (build order + rules)
# - CLAUDE.md                       (project quick reference)
```

---

## 8. File Map (Key Files Only)

```
backend/src/textbook_agent/
  domain/
    entities/learner_profile.py      # INPUT schema
    entities/curriculum_plan.py      # Node 1 output (contains SectionSpec)
    entities/section_content.py      # Node 2 output (6 pedagogical fields)
    entities/section_diagram.py      # Node 3 output (SVG)
    entities/section_code.py         # Node 4 output
    entities/textbook.py             # Node 5 output (assembled)
    entities/quality_report.py       # Node 6 output
    services/node_base.py            # PipelineNode[TInput, TOutput] base
    services/planner.py              # Node 1 (STUB)
    services/content_generator.py    # Node 2 (STUB)
    services/diagram_generator.py    # Node 3 (STUB)
    services/code_generator.py       # Node 4 (STUB)
    services/assembler.py            # Node 5 (STUB, no LLM)
    services/quality_checker.py      # Node 6 (STUB)
    ports/llm_provider.py            # BaseProvider abstract
    prompts/base_prompt.py           # 7 SACRED RULES
    prompts/planner_prompts.py       # IMPLEMENTED (pattern reference)
  application/
    orchestrator.py                  # TextbookAgent (STUB)
    dtos/generation_request.py       # Request/Response DTOs
  infrastructure/
    providers/factory.py             # ProviderFactory (DONE)
    providers/anthropic_provider.py  # Claude adapter (STUB)
    providers/openai_provider.py     # OpenAI adapter (STUB)
    config/settings.py               # Pydantic Settings (DONE)
    renderer/html_renderer.py        # HTMLRenderer (STUB)
    storage/file_storage.py          # FileSystemStorage (DONE)
    repositories/file_textbook_repo.py  # FileTextbookRepository (DONE)
  interface/
    api/app.py                       # FastAPI factory (DONE)
    api/routes/health.py             # GET /health (DONE)
    api/routes/generation.py         # POST /generate, GET /status (501 STUBS)
    cli/main.py                      # CLI skeleton (STUB)

frontend/src/
  lib/types/index.ts                 # TS mirrors of Pydantic schemas
  lib/api/client.ts                  # HTTP client (3 functions)
  lib/components/ProfileForm.svelte  # Input form
  lib/components/GenerationProgress.svelte
  lib/components/TextbookViewer.svelte
  routes/+page.svelte                # Home (TODO: wire API)
  routes/textbook/[id]/+page.svelte  # Viewer (TODO: fetch HTML)
```

---

*This handoff document is versioned alongside the v0.1.0 documentation. Future phases should create their own handoff documents in the corresponding version directory.*
