## Feature: Pipeline Engine — Phases 1–4 (Types, State, Contracts, Graph Shell)

**Classification**: major
**Subsystems**: backend (new `pipeline/` package)

### Summary

Built the self-contained LangGraph generation pipeline at `backend/src/pipeline/`. This is Workstream 1 of the Pipeline-First architecture: the engine that will replace the old orchestrator-based generation flow. The pipeline has zero knowledge of auth, HTTP, database, or config — platform imports from it, never the reverse.

The pipeline runs end-to-end with stub nodes, producing Lectio-compatible `SectionContent` JSON per section. All stubs return the exact shapes that real LLM-backed implementations must honour.

### What was built

**Phase 1 — Types** (`pipeline/types/`)
- `section_content.py` — Full mirror of Lectio's `types.ts` (21 optional fields on `SectionContent`, all component content models, literal types for `GradeBand`, `Difficulty`, etc.)
- `template_contract.py` — `TemplateContractSummary`, `GenerationGuidance`, `TemplatePresetSummary`
- `requests.py` — `PipelineRequest`, `SectionPlan`, `GenerationMode` enum

**Phase 2 — State + Providers** (`pipeline/state.py`, `pipeline/providers/`)
- `TextbookPipelineState` — Pydantic model with LangGraph reducer annotations (`Annotated[list, operator.add]` for append-only, `Annotated[dict, _merge_dicts]` for concurrent fan-out writes)
- `StyleContext`, `PipelineError`, `RerenderRequest`, `QCReport`
- `registry.py` — `ModelTier` enum (FAST/STANDARD/CREATIVE), `get_model()` with override injection for testing, `get_node_model()` convenience

**Phase 3 — Contracts Bridge** (`pipeline/contracts.py`)
- Reads Lectio's exported JSON contracts from `backend/contracts/`
- `lru_cache`-backed loaders: `get_contract()`, `get_preset()`, `list_template_ids()`
- Validation helpers: `validate_section_for_template()`, `get_capacity_limits()`, `validate_preset_for_template()`
- `clear_cache()` for test isolation
- 13 JSON contract files exported from Lectio via `npm run export-contracts`

**Phase 4 — Graph Shell** (`pipeline/graph.py`, `pipeline/nodes/`, `pipeline/routers/`)
- LangGraph `StateGraph` with `Send` fan-out pattern for per-section parallelism
- Composite `process_section` node runs the full per-section chain as a single fan-out unit (content_generator → diagram_generator → interaction_decider → interaction_generator → section_assembler)
- `qc_agent` stub marks all sections as passed
- `qc_router` routes: `"rerender"` (blocking issues + retries left), `"pass"` (all clear), `"error"` (unrecoverable)
- `run.py` — Public entrypoint with `run_pipeline(request, contract)`, re-exports key types

### Files created (pipeline package)

| File | Purpose |
|---|---|
| `src/pipeline/__init__.py` | Package marker |
| `src/pipeline/run.py` | Public entrypoint — only file platform imports from |
| `src/pipeline/graph.py` | LangGraph graph definition + fan-out |
| `src/pipeline/state.py` | `TextbookPipelineState` + supporting models |
| `src/pipeline/contracts.py` | Lectio JSON contract reader |
| `src/pipeline/types/__init__.py` | Package marker |
| `src/pipeline/types/section_content.py` | Lectio type mirrors (~450 lines) |
| `src/pipeline/types/template_contract.py` | Template + preset summaries |
| `src/pipeline/types/requests.py` | Pipeline input types |
| `src/pipeline/providers/__init__.py` | Package marker |
| `src/pipeline/providers/registry.py` | Model tier registry |
| `src/pipeline/nodes/__init__.py` | Package marker |
| `src/pipeline/nodes/process_section.py` | Composite per-section fan-out node |
| `src/pipeline/nodes/curriculum_planner.py` | Stub — generates section plans |
| `src/pipeline/nodes/content_generator.py` | Stub — generates minimal SectionContent |
| `src/pipeline/nodes/diagram_generator.py` | Stub — injects placeholder SVG |
| `src/pipeline/nodes/interaction_decider.py` | Rule-based, no LLM |
| `src/pipeline/nodes/interaction_generator.py` | Stub — skips if no spec |
| `src/pipeline/nodes/section_assembler.py` | Stub — passes section through |
| `src/pipeline/nodes/qc_agent.py` | Stub — marks all as passed |
| `src/pipeline/routers/__init__.py` | Package marker |
| `src/pipeline/routers/qc_router.py` | QC routing logic |
| `tests/pipeline/__init__.py` | Test package marker |

### Files modified

| File | Change |
|---|---|
| `backend/pyproject.toml` | Added `langgraph`, `pydantic-ai`, `pytest`, `pytest-asyncio` deps; added `src/pipeline` to packages |
| `.gitignore` | Added `backend/contracts/*.json` |
| `backend/.env.example` | Added `LECTIO_CONTRACTS_DIR` |
| `backend/contracts/.gitkeep` | Created (holds Lectio JSON exports) |

### Key design decisions

1. **Composite fan-out node**: LangGraph's `Send` fans out to a single node, not a chain. Regular edges after a fan-out target merge state and lose per-section context. Solution: `process_section` runs the full per-section chain internally and returns merged outputs.

2. **Dict merge reducers**: Fan-out nodes write to the same dict fields concurrently. Plain dict fields use last-write-wins, which drops data. Solution: `Annotated[dict, _merge_dicts]` reducer on `generated_sections`, `assembled_sections`, `interaction_specs`, `qc_reports`, `rerender_count`.

3. **`TextbookPipelineState.parse()`**: LangGraph 1.1.x passes dicts to nodes even when `StateGraph` is parameterized with a Pydantic model. Every node calls `TextbookPipelineState.parse(state)` at the top to get typed attribute access.

4. **`run_pipeline()` generates `thread_id`**: `MemorySaver` checkpointer requires a `thread_id` in config. Each `run_pipeline()` call generates a fresh UUID. This supports future streaming/resumption.

### Progress

- [x] Phase 1: Types — created and verified imports
- [x] Phase 2: State + providers — created and verified with TestModel injection
- [x] Phase 3: Contracts — exported from Lectio, bridge verified with all 10 templates
- [x] Phase 4: Graph shell — full end-to-end graph run with 2-section fan-out
- [x] Existing backend tests pass (161 passed, 6 deselected)

### Validation evidence

```
# Phase 4 diagnostic (2 sections, guided-concept-path template)
completed_nodes: [curriculum_planner, content_generator x2, diagram_generator x2,
                  interaction_decider x2, interaction_generator x2,
                  section_assembler x2, qc_agent]
assembled_sections: [s-01, s-02]
qc_reports: [s-01, s-02]  (both passed)
errors: []
PHASE 4 DIAGNOSTIC: PASS

# Existing backend tests
uv run python -m pytest tests/ --ignore=tests/pipeline -q
161 passed, 6 deselected in 31.48s
```

### What comes next

**Immediate (Workstream 1 continued):**
- Phase 5+: Replace stub nodes with real LLM-backed implementations one at a time (curriculum_planner first, then content_generator, etc.)
- Each stub's docstring declares its replacement phase and state contract

**Later (Workstream 2):**
- Restructure backend: rename `textbook_agent/` → `platform/`, flatten DDD layers
- Wire `platform/api/routes/generation.py` to call `pipeline.run.run_pipeline()`
- Delete old generation code (orchestrator, domain services, prompts)

### Risks and follow-up

- **Stub fidelity**: Stubs return minimal content. Real nodes must honour the same return shape (dict keys, reducer compatibility). Each stub's docstring is the contract.
- **`process_section` opacity**: The composite node hides individual step timing from LangGraph's built-in tracing. When real LLM calls are added, consider whether to break it back into a subgraph for better observability.
- **Contract JSON drift**: If Lectio templates change, contracts must be re-exported (`npm run export-contracts -- --out ../backend/contracts`). No automated sync yet.
- **`grade_band` values**: `PipelineRequest.grade_band` is a free string but `SectionHeaderContent.grade_band` is `Literal['primary', 'secondary', 'advanced']`. Real curriculum_planner must map input to valid literals.
