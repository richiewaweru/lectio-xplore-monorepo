# Pipeline Speed & Targeted Retry — Implementation Handoff

**Created:** 2026-03-22
**Source proposals:** `PIPELINE_IMPROVEMENTS_PROPOSAL_final touches.md` (6 changes) + `FIELD_RETRY_PROPOSAL_final touches.md` (field-level retry)
**Goal:** Cut total generation time from ~90-120s → ~40-60s, perceived wait from ~45s → ~8s, and avoid wasting correct content on failures.

---

## Current State (baseline)

| Metric                  | Current        |
|-------------------------|----------------|
| Time to first content   | 45-60s         |
| Total generation (4 sec)| 90-120s        |
| Draft total time        | 90-120s (same) |
| Post-generation QC wait | 20-40s         |
| Diagram failure cost    | 25-40s (full)  |
| Max diagram wait        | unbounded      |
| Content prompt tokens   | ~850           |

---

## Phase Map (simplest → most complex)

```
Phase 1 ─ Lean Capacity Rules            ~30 min   Risk: LOW     Files: 2
Phase 2 ─ Stream Section Titles           ~30 min   Risk: LOW     Files: 1
Phase 3 ─ Draft Mode Uses FAST Model      ~45 min   Risk: LOW     Files: 1-2
Phase 4 ─ Diagram Timeout Guard           ~45 min   Risk: LOW     Files: 1
Phase 5 ─ Per-Section QC                  ~1.5 hrs  Risk: MEDIUM  Files: 3
Phase 6 ─ Component-Level Retry (Diagram) ~2 hrs    Risk: MEDIUM  Files: 2-3
Phase 7 ─ Field-Level Retry (Text)        ~2 hrs    Risk: MEDIUM  Files: 4-5
```

Dependencies: Phases 1-4 are fully independent. Phase 6 depends on Phase 5. Phase 7 depends on Phase 6.

---

## Phase 1 — Lean Capacity Rules

**What:** Only emit capacity rules for fields the current template actually uses. A `focus-flow` section never produces `timeline` or `comparison_grid`, but today the model reads those rules anyway — wasted tokens and diluted attention.

**Files to change:**
```
MOD  backend/src/pipeline/prompts/shared.py       ← replace capacity_reminder()
MOD  backend/src/pipeline/prompts/content.py      ← call new function
```

**Steps:**
- [ ] In `shared.py`: keep `capacity_reminder()` but deprecate it. Add `_CAPACITY_RULES` dict keyed by field name and `capacity_reminder_for_fields(active_fields: list[str]) -> str`.
- [ ] In `content.py` `build_content_system_prompt()`: replace `{capacity_reminder()}` with `{capacity_reminder_for_fields(required + optional)}`. The `required` and `optional` variables are already computed there.

**Verify:**
```bash
python -c "
from pipeline.prompts.content import build_content_system_prompt
for tid in ['guided-concept-path', 'focus-flow', 'timeline-narrative']:
    p = build_content_system_prompt(tid, tid, 'test')
    tokens = len(p) // 4
    cap_start = p.find('Capacity')
    cap_block = p[cap_start:cap_start+400] if cap_start >= 0 else 'none'
    print(f'{tid}: ~{tokens} tokens')
    print(cap_block)
    print()
"
```
- `focus-flow` must NOT show timeline or comparison_grid rules
- Token count is lower than before

**Done when:** Diagnostic passes. `uv run pytest` still green.

---

## Phase 2 — Stream Section Titles Immediately

**What:** After curriculum planning (~6s), emit `SectionStartedEvent` per section so the teacher sees the outline immediately instead of staring at a blank screen until content arrives at ~15-25s.

**Files to change:**
```
MOD  backend/src/pipeline/nodes/curriculum_planner.py   ← publish events
```

**Steps:**
- [ ] In `curriculum_planner`, after `result = await run_llm(...)` and before `return`:
  ```python
  from pipeline.events import SectionStartedEvent, event_bus
  for plan in result.output.sections:
      event_bus.publish(
          state.request.generation_id or '',
          SectionStartedEvent(
              generation_id=state.request.generation_id or '',
              section_id=plan.section_id,
              title=plan.title,
              position=plan.position,
          ),
      )
  ```
- [ ] `SectionStartedEvent` already exists in `pipeline/events.py` and is already handled by the frontend `/textbook/[id]` page — no frontend changes needed.

**Verify:** Generate a lesson. In the browser network tab, `section_started` events arrive BEFORE any `section_ready` event. Titles match final generated section titles.

**Done when:** Teacher sees outline at ~6s instead of blank screen until ~15s.

---

## Phase 3 — Draft Mode Uses FAST Model

**What:** Draft mode should use Haiku (FAST) for content generation, not Sonnet (STANDARD). Draft is the fast iteration pass; teacher generates in ~20s, reads, then clicks Enhance for full quality.

**Files to change:**
```
MOD  backend/src/pipeline/providers/registry.py   ← verify/update NODE_MODEL_SLOTS
```

**Steps:**
- [ ] Check current `NODE_MODEL_SLOTS` mapping for `content_generator`. It currently maps to `ModelSlot.STANDARD`.
- [ ] The mode-aware routing via `get_node_text_model("content_generator", generation_mode=...)` should resolve draft → FAST. Verify the draft profile in `_MODE_PROFILES` uses FAST for the STANDARD slot (it may already), or add explicit draft entry in `NODE_REQUIREMENTS` if that pattern is used.
- [ ] Verify by running a draft generation and checking `LLMCallSucceededEvent.model_name` — should be Haiku for `content_generator`.

**Verify:**
```bash
# Run a draft generation and check LLM events
# LLMCallSucceededEvent.model_name should be haiku for content_generator
# LLMCallSucceededEvent.model_name should be haiku for qc_agent (already is)
```

**Expected impact:**
```
Draft (haiku):     4-section lesson ~20-30s total
Balanced (sonnet): 4-section lesson ~45-60s total (unchanged)
```

**Done when:** Draft generation uses Haiku for content. `uv run pytest` green.

---

## Phase 4 — Diagram Timeout Guard

**What:** Wrap diagram generation's `run_llm` call in `asyncio.wait_for(timeout=25.0)`. A hanging diagram call currently blocks the entire section indefinitely.

**Files to change:**
```
MOD  backend/src/pipeline/nodes/diagram_generator.py   ← wrap in wait_for
```

**Steps:**
- [ ] Import `asyncio` at top.
- [ ] Wrap the existing `result = await run_llm(...)` call:
  ```python
  try:
      result = await asyncio.wait_for(
          run_llm(...),
          timeout=25.0,
      )
  except asyncio.TimeoutError:
      return {
          "completed_nodes": ["diagram_generator"],
          "errors": [PipelineError(
              node="diagram_generator",
              section_id=sid,
              message="Diagram generation timed out (25s) — section delivered without diagram",
              recoverable=True,
          )],
      }
  ```
- [ ] Existing error handling below remains unchanged for non-timeout errors.

**Verify:** Temporarily set timeout to 0.001s, run a generation with diagrams, confirm the section ships without a diagram and error is marked `recoverable=True`. Restore to 25.0s.

**Done when:** No section can be blocked indefinitely by a diagram call. `uv run pytest` green.

---

## Phase 5 — Per-Section QC (⚠️ Medium Risk)

**What:** Move QC from a post-join batch node into the per-section `process_section` composite. Currently QC waits for ALL sections to finish (~24s) then runs 4 sequential LLM calls (~20-40s). Moving it inline means QC runs as each section finishes — saving 20-40s.

**Files to change:**
```
MOD  backend/src/pipeline/nodes/qc_agent.py         ← scope to current_section_id only
MOD  backend/src/pipeline/nodes/process_section.py   ← add qc_agent to step chain
MOD  backend/src/pipeline/graph.py                   ← remove top-level qc_agent node
```

**Steps:**
- [ ] **qc_agent.py** — Scope to single section:
  - Read `state.current_section_id` instead of iterating `assembled_sections`
  - If no `current_section_id` or no assembled section for it, return early
  - Skip if rerender limit exceeded for this section
  - Run LLM evaluation on just this one section
  - Return `qc_reports: {sid: report}` (dict merge reducer handles the rest)

- [ ] **process_section.py** — Add QC as final step:
  ```python
  from pipeline.nodes.qc_agent import qc_agent
  for step in [
      content_generator,
      diagram_generator,
      interaction_decider,
      interaction_generator,
      section_assembler,
      qc_agent,              # ← ADD
  ]:
  ```
  Also forward `qc_reports` in the output dict.

- [ ] **graph.py** — Remove top-level QC node:
  ```python
  # REMOVE: workflow.add_node("qc_agent", qc_agent)
  # REMOVE: workflow.add_edge("process_section", "qc_agent")
  # CHANGE: workflow.add_conditional_edges("qc_agent", route_after_qc)
  # TO:     workflow.add_conditional_edges("process_section", route_after_qc)
  ```

**Verify:**
```
t=15s  section 1 assembles → QC runs immediately → section_ready fires
t=18s  section 2 assembles → QC runs immediately → section_ready fires
t=21s  section 3 assembles → QC runs immediately → section_ready fires
t=24s  section 4 assembles → QC runs immediately → section_ready fires
# No post-generation QC wait
```

**Caution:** This is the first change that modifies the graph topology. Test with a full 4-section generation. Verify `qc_reports` state merges correctly when multiple `process_section` instances write concurrently.

**Done when:** QC runs per-section inline. No post-join QC wait. `uv run pytest` green. End-to-end generation produces identical output quality.

---

## Phase 6 — Component-Level Retry (Diagram-Only)

**What:** When QC flags only the diagram as blocking, retry just the diagram — not the entire section. Preserves a perfectly good hook, explanation, and practice set.

**Depends on:** Phase 5 (per-section QC must be inline first, so `route_after_qc` reads per-section `qc_reports`)

**Files to change:**
```
MOD  backend/src/pipeline/routers/qc_router.py  ← route diagram failures to retry_diagram
MOD  backend/src/pipeline/graph.py               ← register retry_diagram node + edges
NEW  (inline in graph.py or separate file)       ← retry_diagram async function
```

**Steps:**
- [ ] **qc_router.py** — Add diagram-specific routing:
  ```python
  _DIAGRAM_FIELDS = {'diagram', 'diagram_series', 'diagram_compare'}

  def route_after_qc(state):
      # ... existing blocking check ...
      block_type = blocking[0].get('block', '')
      if block_type in _DIAGRAM_FIELDS:
          sends.append(Send('retry_diagram', base))
      else:
          sends.append(Send('process_section', base))
  ```

- [ ] **graph.py** — Add `retry_diagram` node:
  ```python
  async def retry_diagram(state, *, provider_overrides=None):
      # Re-run diagram_generator → section_assembler → qc_agent only
      # Text content in generated_sections[sid] is preserved exactly
  ```
  Wire: `workflow.add_node("retry_diagram", retry_diagram)` + `workflow.add_conditional_edges("retry_diagram", route_after_qc)`

**Verify:** Seed a section with a valid hook/explanation/practice but a broken diagram SVG. Trigger QC. Confirm only diagram regenerates. Confirm text fields are byte-for-byte identical.

**Expected impact:**
```
Diagram failure cost:  Before 25-40s → After 8-15s
```

**Done when:** Diagram-only failures retry only the diagram. `uv run pytest` green.

---

## Phase 7 — Field-Level Retry (Targeted Text Fix)

**What:** When QC flags a specific TEXT field (e.g., `practice` problems not graduated in difficulty), regenerate ONLY that field using the rest of the section as context. One FAST model call (~3-5s) instead of full `process_section` rerun (~25-40s).

**Depends on:** Phase 6 (router already handles diagram routing; this adds text field routing)

**Files to create/change:**
```
NEW  backend/src/pipeline/prompts/field_regen.py      ← prompt builders
NEW  backend/src/pipeline/nodes/field_regenerator.py   ← node logic
MOD  backend/src/pipeline/routers/qc_router.py         ← add retry_field route
MOD  backend/src/pipeline/graph.py                     ← register retry_field node
MOD  backend/src/pipeline/providers/registry.py        ← add field_regenerator to NODE_REQUIREMENTS
```

**Steps:**
- [ ] **prompts/field_regen.py** — Create with:
  - `RETRYABLE_FIELDS` set: `hook`, `explanation`, `practice`, `worked_example`, `definition`, `pitfall`, `glossary`, `what_next`
  - `build_field_regen_system_prompt(template_id)` — lean system prompt with template tone/guidance
  - `build_field_regen_user_prompt(section, failing_field, reason)` — serializes section minus the failing field as context

- [ ] **nodes/field_regenerator.py** — Create with:
  - Reads `current_section_id`, `generated_sections`, `rerender_requests`
  - Finds matching `RerenderRequest` for current section
  - Skips if `block_type` not in `RETRYABLE_FIELDS`
  - Calls LLM with `output_type=str` (raw JSON, field schema varies)
  - Parses JSON → patches section via `section.model_copy(update={field: value})`
  - Updates both `generated_sections` and `assembled_sections`
  - Clears processed `rerender_request`

- [ ] **routers/qc_router.py** — Extend routing:
  ```python
  _TEXT_FIELDS = {'hook', 'explanation', 'practice', 'worked_example',
                  'definition', 'pitfall', 'glossary', 'what_next'}

  if block_type in _DIAGRAM_FIELDS:
      sends.append(Send('retry_diagram', base))
  elif block_type in _TEXT_FIELDS:
      sends.append(Send('retry_field', base))     # ← NEW
  else:
      sends.append(Send('process_section', base))  # full retry fallback
  ```

- [ ] **graph.py** — Register:
  ```python
  workflow.add_node("retry_field", field_regenerator)
  workflow.add_conditional_edges("retry_field", route_after_qc)
  ```

- [ ] **providers/registry.py** — Add `field_regenerator` to NODE_REQUIREMENTS/NODE_MODEL_SLOTS using FAST (short targeted output).

**Verify:**
1. Generate a section normally
2. Seed a bad `practice` field into `qc_reports` with `severity: blocking`
3. Run `route_after_qc` — confirm it returns `Send('retry_field', ...)`
4. Run `field_regenerator` — confirm:
   - Only `practice` field changes in `generated_sections`
   - `hook`, `explanation`, `what_next` are byte-for-byte identical
   - `rerender_requests` is cleared for the section
   - New `practice` is coherent with the rest of the section

**Expected impact:**
```
Text field failure cost:  Before 25-40s → After 3-5s
```

**Done when:** Text field failures retry only the specific field. All other fields preserved. `uv run pytest` green.

---

## End-to-End Measurement Plan

Run a calculus lesson (4 sections, `guided-concept-path`, `blue-classroom`) before and after each phase. Record from `LLMCallSucceededEvent` events:

| Metric                  | Before   | After Phase 1 | After Phase 2 | After Phase 3 | After Phase 4 | After Phase 5 | After Phase 6 | After Phase 7 |
|-------------------------|----------|---------------|---------------|---------------|---------------|---------------|---------------|---------------|
| Content prompt tokens   | ~850     | ~700          | ~700          | ~700          | ~700          | ~700          | ~700          | ~700          |
| Time to first content   | 45-60s   | 45-60s        | **8-12s**     | 8-12s         | 8-12s         | 8-12s         | 8-12s         | 8-12s         |
| Draft total time        | 90-120s  | 90-120s       | 90-120s       | **20-30s**    | 20-30s        | 20-30s        | 20-30s        | 20-30s        |
| Max diagram wait        | unbounded| unbounded     | unbounded     | unbounded     | **25s**       | 25s           | 25s           | 25s           |
| Post-generation QC wait | 20-40s   | 20-40s        | 20-40s        | 20-40s        | 20-40s        | **0s**        | 0s            | 0s            |
| Diagram failure cost    | 25-40s   | 25-40s        | 25-40s        | 25-40s        | 25-40s        | 25-40s        | **8-15s**     | 8-15s         |
| Text field failure cost | 25-40s   | 25-40s        | 25-40s        | 25-40s        | 25-40s        | 25-40s        | 25-40s        | **3-5s**      |
| **Total generation**    | 90-120s  | 85-115s       | 85-115s       | 85-115s       | 85-115s       | **40-60s**    | 40-60s        | 40-60s        |

---

## Quick Reference — What NOT to Touch

- **No frontend changes** — all phases are backend-only (events already handled)
- **No Lectio changes** — rendering is unaffected
- **No state schema changes** — existing `TextbookPipelineState` fields suffice
- **No contract changes** — template contracts stay as-is
- `pipeline` must never import `generation` or `planning` (app boundary)
- `BASE_PEDAGOGICAL_RULES` in `domain/prompts/base_prompt.py` are sacred — do not modify

---

## Files Index

All paths relative to `backend/src/pipeline/`:

| File                          | Phase(s)  | Action |
|-------------------------------|-----------|--------|
| `prompts/shared.py`           | 1         | MOD    |
| `prompts/content.py`          | 1         | MOD    |
| `nodes/curriculum_planner.py` | 2         | MOD    |
| `providers/registry.py`       | 3, 7      | MOD    |
| `nodes/diagram_generator.py`  | 4         | MOD    |
| `nodes/qc_agent.py`           | 5         | MOD    |
| `nodes/process_section.py`    | 5         | MOD    |
| `graph.py`                    | 5, 6, 7   | MOD    |
| `routers/qc_router.py`        | 6, 7      | MOD    |
| `prompts/field_regen.py`      | 7         | NEW    |
| `nodes/field_regenerator.py`  | 7         | NEW    |
