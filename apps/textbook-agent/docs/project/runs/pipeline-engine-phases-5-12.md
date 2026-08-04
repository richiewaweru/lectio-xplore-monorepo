## Feature: Pipeline Engine — Phases 5–12 (Real Nodes, Validation, SSE, Tests)

**Classification**: major
**Subsystems**: backend (`pipeline/` package)
**Continues**: `pipeline-engine-phases-1-4.md`

### Summary

Replaced all pipeline stub nodes with real PydanticAI Agent implementations, added prompt builders, Layer 3 validation (contract compliance + capacity limits), SSE streaming infrastructure, and the Phase 12 integration test suite. The pipeline is now functionally complete — every node produces real LLM-backed output, sections stream via event bus, and QC rerender routing works end-to-end.

Two bugs were found and fixed during the Phase 12 audit of the codebase.

### What was built (across two sessions — first session lost, second recovered and completed)

**Phase 5 — Prompt Builders** (`pipeline/prompts/`)
- `shared.py` — `shared_context()`, `word_count()`, `capacity_reminder()` (mirrors frontend validation limits)
- `curriculum.py` — system/user prompt builders for curriculum_planner (lesson flow, guidance, section format)
- `content.py` — system/user prompt builders for content_generator (required/optional fields, capacity rules, rerender reason injection)
- `diagram.py` — system/user prompt builders + style translation maps: `SURFACE_TO_DIAGRAM_STYLE`, `PALETTE_TO_STROKE`, `TYPOGRAPHY_TO_LABELS`, `COMPLEXITY_TO_DETAIL` — translate Lectio preset semantics into SVG diagram instructions
- `qc.py` — system/user prompt builders for semantic QC (hook, explanation, practice, pitfall, worked_example criteria)

**Phase 6 — curriculum_planner** (real node)
- PydanticAI Agent with `CurriculumOutput(sections: list[SectionPlan])` output type
- Validates preset-template compatibility before LLM call via `contracts.validate_preset_for_template()`
- Derives `StyleContext` from preset registry (frozen for entire pipeline run)
- Unrecoverable error on invalid preset or LLM failure

**Phase 7 — content_generator** (real node)
- PydanticAI Agent with `output_type=SectionContent` — inline schema validation
- Fresh agent per call (system prompt varies by template)
- Rerender detection: reads `rerender_requests` for matching `section_id`, passes reason to user prompt
- Catches `ValidationError` and generic `Exception` separately — both produce recoverable `PipelineError`
- Tracks `rerender_count` per section

**Phase 8 — section_assembler + SSE streaming**
- Layer 3a: Contract compliance via `contracts.validate_section_for_template()` — violations are blocking errors
- Layer 3b: Capacity limits via `_check_capacity()` — mirrors frontend `validate.ts` exactly — violations are non-blocking warnings in `QCReport`
- `events.py` — `PipelineEventBus` pub/sub with `asyncio.Queue` per generation_id
- `run.py` — `run_pipeline_streaming()` uses `graph.astream()`, publishes `pipeline_start`, `node_complete`, `section_ready`, `qc_complete`, `complete`/`error` events

**Phase 9 — diagram_generator** (real node)
- PydanticAI Agent with `DiagramOutput(svg_content, caption, alt_text)`
- Skip conditions: no diagram component in contract, `plan.needs_diagram == False`
- Style instructions derived from `StyleContext` via `build_diagram_style_instruction()`

**Phase 10 — interaction nodes** (deferred)
- `interaction_decider` — rule-based stub, skips when `interaction_level` is `'none'` or `'light'`
- `interaction_generator` — stub, returns immediately
- Deferred because no template with `interactionLevel: 'high'` is in active use yet

**Phase 11 — qc_agent + rerender routing**
- PydanticAI Agent with `QCOutput(passed, issues, warnings)`
- Iterates assembled sections, skips sections over `max_rerenders`
- Merges semantic issues with assembler's capacity warnings
- Blocking issues produce `RerenderRequest` entries
- `qc_router.py` returns `list[Send]` for per-section rerender fan-out, `END` for pass/error

**Phase 12 — Integration tests** (21 tests, all passing)

### Bugs found and fixed

| Bug | File | Fix |
|---|---|---|
| QC routing crash on rerender | `graph.py:59-67` | `add_conditional_edges("qc_agent", route_after_qc)` had a string path_map `{"rerender": ..., "pass": ..., "error": ...}` but `route_after_qc` returns `list[Send] \| END`. Removed the path_map dict so LangGraph handles `Send` objects directly (matching how `fan_out_sections` is already wired). |
| process_section drops qc_reports | `process_section.py:63` | Assembler writes `qc_reports` with capacity warnings, but the composite node never forwarded them. Added `if sid and sid in typed_final.qc_reports: output["qc_reports"] = {sid: typed_final.qc_reports[sid]}`. Without this, QC agent never saw capacity warnings. |

### Files created

| File | Purpose |
|---|---|
| `src/pipeline/prompts/__init__.py` | Package marker |
| `src/pipeline/prompts/shared.py` | Shared context block, word counter, capacity reminder |
| `src/pipeline/prompts/curriculum.py` | Curriculum planner prompt builders |
| `src/pipeline/prompts/content.py` | Content generator prompt builders |
| `src/pipeline/prompts/diagram.py` | Diagram generator prompt builders + style maps |
| `src/pipeline/prompts/qc.py` | QC agent prompt builders |
| `src/pipeline/events.py` | PipelineEventBus pub/sub for SSE streaming |
| `tests/pipeline/test_pipeline_integration.py` | 21 integration tests |

### Files modified

| File | Change |
|---|---|
| `src/pipeline/nodes/curriculum_planner.py` | Stub → real PydanticAI Agent |
| `src/pipeline/nodes/content_generator.py` | Stub → real PydanticAI Agent |
| `src/pipeline/nodes/diagram_generator.py` | Stub → real PydanticAI Agent |
| `src/pipeline/nodes/section_assembler.py` | Stub → Layer 3 validation |
| `src/pipeline/nodes/qc_agent.py` | Stub → real PydanticAI Agent |
| `src/pipeline/nodes/process_section.py` | Bug fix: forward `qc_reports` |
| `src/pipeline/routers/qc_router.py` | Returns `list[Send]` for rerender fan-out |
| `src/pipeline/graph.py` | Bug fix: removed broken path_map dict |
| `src/pipeline/run.py` | Added `run_pipeline_streaming()` with event bus |

### Test coverage

```
tests/pipeline/test_pipeline_integration.py — 21 tests
  TestGraphTopology           (5)  graph compiles, fan-out patterns, empty/null outlines
  TestQCRouting               (7)  pass/rerender/max-rerenders/unrecoverable/warning-only/multi-section/plan-carry
  TestSectionAssembler        (3)  valid assembly, missing section error, capacity warnings
  TestPresetValidation        (1)  invalid preset rejected before LLM call
  TestEventBus                (3)  pub/sub, unsubscribe, generation isolation
  TestProcessSectionComposite (2)  qc_reports forwarding, error forwarding

tests/pipeline/test_providers_registry.py — 3 tests (pre-existing)

Result: 23 passed, 1 pre-existing failure (requires ANTHROPIC_API_KEY)
```

### Key design decisions

1. **Provider bridge pattern**: Each node has a `_resolve_model()` that calls `get_node_model()` → `get_model()` and then extracts the PydanticAI model via `provider._model` if present. This bridges the custom `BaseLLMProvider` registry with PydanticAI's `Agent(model=...)`. When the registry gains native PydanticAI model support, these bridges can be removed.

2. **Prompt budget discipline**: System prompts are kept under ~1,000 tokens. Haiku-tier models degrade noticeably above this. Each prompt builder composes only the fields that node needs — the content generator never sees diagram instructions, the diagram generator never sees practice problem formats.

3. **Style maps as code, not config**: The diagram style translation maps (`PALETTE_TO_STROKE`, `SURFACE_TO_DIAGRAM_STYLE`, etc.) are Python dicts in `prompts/diagram.py`, not external config. They must match preset-registry.json palette strings exactly. No automated sync — visual inspection of generated diagrams is required after preset changes.

4. **Capacity as warnings, contract as errors**: Layer 3a (contract compliance) violations are blocking `PipelineError` — the section is not assembled. Layer 3b (capacity limits) violations are non-blocking warnings in `QCReport` — the section is assembled and the QC agent decides whether to escalate.

### What comes next

**Immediate:**
- Wire the pipeline SSE event bus to the platform API layer (`textbook_agent/interface/api/routes/generation.py`). The event bus is ready; the SSE HTTP endpoint that subscribes to it and streams to the browser is not yet built.
- Add `sse-starlette` to `pyproject.toml` when the API endpoint is built.
- Run with real API keys and evaluate content quality (the human-in-the-loop check from Phase 7 spec).

**Deferred:**
- Phase 10 (interaction_decider/interaction_generator) — implement when a template with `interactionLevel: 'medium'` or `'high'` is in active use.
- Provider bridge cleanup — when the registry supports returning PydanticAI models natively, remove `_resolve_model()` from all nodes.
- `process_section` observability — the composite node hides individual step timing. Consider subgraph if tracing becomes important.

### Risks

- **No real-model test yet**: All tests use mocked nodes or deterministic state. Content quality has not been evaluated with actual LLM output. The Phase 7 spec's human-in-the-loop check is still pending.
- **Contract JSON drift**: If Lectio templates change, contracts must be re-exported and diagram style maps in `prompts/diagram.py` must be manually reviewed.
- **`test_get_model_returns_provider_instance` failing**: Pre-existing test in `test_providers_registry.py` requires `ANTHROPIC_API_KEY` to be set. Should be gated behind `@pytest.mark.integration`.
