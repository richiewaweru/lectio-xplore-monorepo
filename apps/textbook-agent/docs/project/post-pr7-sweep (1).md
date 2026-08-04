# Post-PR7 sweep — single coordinated change

**Date:** 2026-04-24
**Codebase state confirmed by scan.** All changes below are pending. Nothing overlaps.
**Approach:** one PR, one sweep. Unit tests only. No integration tests.

---

## What the scan confirmed is already done

- `visual_resolution.py` — deleted. `process_section.py` now imports from `pipeline.media.slot_state`. `section_assembler.py` no longer imports it.
- `visual_placements` — live on `SectionPlan`, populated by `visual_router`, iterated by `media_planner`.
- `_visual_context_block()` — phase-aware, reads `visual_placements`.
- `VisualSlot` — has `content_brief`, `sizing`, `block_target`, `problem_index`.
- `intelligent_image_prompt.py` — exists, `RENDER_MODE` output, `parse_intelligent_image_output()` works.
- `build_diagram_user_prompt()` — injects `content_brief` when present.
- `simulation_generator.py` — LLM-driven, `_SIMULATION_SYSTEM_PROMPT` with 4-control ceiling and Play/Pause/Reset rule.
- `reporting.py` — `visual_commitment` removed from `GenerationPlannerTraceSection`, `visual_placements_count` present.
- `generation/service.py` — passes `visual_placements=list(section.visual_placements)`, no `visual_commitment`.
- `test_api.py` — asserts `"visual_commitment" not in payload["runtime_curriculum_outline"][0]`.

---

## What still needs doing

### 1. `GenerationReportOutlineSection` — `visual_commitment` field `[TG]`

**File:** `pipeline/reporting.py`

The scan shows `GenerationReportOutlineSection` still has:
```python
visual_commitment: str | None = None
```
Replace with:
```python
visual_placements_count: int = 0
```

Where it's populated in `telemetry/recorder.py` (`_handle_curriculum_planned`), replace reading `visual_commitment` from the payload with `visual_placements_count`.

**Test:** `tests/services/test_generation_report_recorder.py` — find any fixture passing `visual_commitment` and update to `visual_placements_count`.

---

### 2. Timeout config `[TG]`

**File:** `backend/src/core/config.py`

```python
# Update defaults:
pipeline_timeout_curriculum_seconds: float = Field(default=90.0, gt=0)       # was 60.0
pipeline_timeout_diagram_node_budget_seconds: float = Field(default=90.0, gt=0)  # was 60.0

# Add new field after diagram timeout fields:
pipeline_timeout_interaction_seconds: float = Field(default=60.0, gt=0)
```

**File:** `backend/.env` and `backend/.env.example`

```properties
PIPELINE_TIMEOUT_CURRICULUM_SECONDS=90
PIPELINE_TIMEOUT_DIAGRAM_NODE_BUDGET_SECONDS=90
PIPELINE_TIMEOUT_INTERACTION_SECONDS=60
```

**File:** `pipeline/media/executors/simulation_generator.py`

Wire the timeout into `_generate_simulation_markup()`. Find where `run_llm` is awaited and wrap:

```python
from core.config import settings
import asyncio

result = await asyncio.wait_for(
    run_llm_fn(
        generation_id=state.request.generation_id or "",
        node="interaction_generator",
        agent=agent,
        model=model,
        section_id=state.current_section_id,
        generation_mode=state.request.mode,
        user_prompt=build_simulation_prompt(
            section_title=section.header.title,
            slot=slot,
            frame=frame,
        ),
    ),
    timeout=settings.pipeline_timeout_interaction_seconds,
)
```

**Test:** `tests/config/test_settings_bootstrap.py` — update any assertion on `pipeline_timeout_curriculum_seconds` default (was 60.0 → now 90.0) and add assertion for `pipeline_timeout_interaction_seconds == 60.0`.

---

### 3. Observability additions `[TG]`

**File:** `pipeline/reporting.py` — add new fields:

```python
class GenerationReportSection(BaseModel):
    # ... existing fields ...
    visual_placements_count: int = 0
    visual_placements_summary: list[str] = Field(default_factory=list)
    slot_render_modes: dict[str, str] = Field(default_factory=dict)
    simulation_type_selected: str | None = None
    simulation_goal_selected: str | None = None

class GenerationReportSummary(BaseModel):
    # ... existing fields ...
    image_slots_count: int = 0
    svg_slots_count: int = 0
    prompt_builder_calls: int = 0
```

**File:** `pipeline/events.py` — add four new event types:

```python
class VisualPlacementsCommittedEvent(BaseModel):
    type: Literal["visual_placements_committed"] = "visual_placements_committed"
    generation_id: str
    section_id: str
    placements_count: int
    placements_summary: list[str]

class SlotRenderModeResolvedEvent(BaseModel):
    type: Literal["slot_render_mode_resolved"] = "slot_render_mode_resolved"
    generation_id: str
    section_id: str
    slot_id: str
    render_mode: str
    decided_by: str

class SimulationTypeSelectedEvent(BaseModel):
    type: Literal["simulation_type_selected"] = "simulation_type_selected"
    generation_id: str
    section_id: str
    simulation_type: str
    simulation_goal: str

class IntentResolvedEvent(BaseModel):
    type: Literal["intent_resolved"] = "intent_resolved"
    generation_id: str
    topic_type: str
    learning_outcome: str
    resolved_by: str
    template_override: str | None = None
```

**File:** `telemetry/service.py` — add to `_REPORT_EVENT_TYPES`:

```python
"visual_placements_committed",
"slot_render_mode_resolved",
"simulation_type_selected",
"intent_resolved",
```

**File:** `telemetry/recorder.py` — add four handlers:

```python
def _handle_visual_placements_committed(self, payload):
    section = self._ensure_section(payload["section_id"])
    section.visual_placements_count = payload.get("placements_count", 0)
    section.visual_placements_summary = payload.get("placements_summary", [])

def _handle_slot_render_mode_resolved(self, payload):
    section = self._ensure_section(payload["section_id"])
    section.slot_render_modes[payload["slot_id"]] = payload["render_mode"]
    if payload["render_mode"] == "image":
        self._report.summary.image_slots_count += 1
    else:
        self._report.summary.svg_slots_count += 1
    if payload.get("decided_by") == "intelligent_image_prompt":
        self._report.summary.prompt_builder_calls += 1

def _handle_simulation_type_selected(self, payload):
    section = self._ensure_section(payload["section_id"])
    section.simulation_type_selected = payload.get("simulation_type")
    section.simulation_goal_selected = payload.get("simulation_goal")

def _handle_intent_resolved(self, payload):
    pass  # reserved — intent resolution events not yet fired by PR 7 LLM calls
```

Wire them in `apply_event()` alongside the existing handlers.

**Publish events at the right nodes:**

`planning/visual_router.py` — after populating placements per section:
```python
from pipeline.events import VisualPlacementsCommittedEvent
event_bus.publish(generation_id, VisualPlacementsCommittedEvent(
    generation_id=generation_id,
    section_id=section.id,
    placements_count=len(section.visual_placements),
    placements_summary=[
        f"{p.block}:{p.slot_type}:{p.sizing}"
        for p in section.visual_placements
    ],
))
```

`pipeline/nodes/media_planner.py` — after `build_intelligent_image_prompt` resolves render mode:
```python
from pipeline.events import SlotRenderModeResolvedEvent
event_bus.publish(generation_id, SlotRenderModeResolvedEvent(
    generation_id=generation_id,
    section_id=sid,
    slot_id=slot.slot_id,
    render_mode=preferred_render.value,
    decided_by="intelligent_image_prompt",
))
```

`pipeline/media/executors/simulation_generator.py` — after `_parse_simulation_output`:
```python
from pipeline.events import SimulationTypeSelectedEvent
event_bus.publish(generation_id, SimulationTypeSelectedEvent(
    generation_id=state.request.generation_id or "",
    section_id=state.current_section_id or "",
    simulation_type=parsed.simulation_type,
    simulation_goal=parsed.goal,
))
```

---

### 4. Frontend type cleanup `[Frontend]`

**File:** `frontend/src/lib/types/index.ts`

Remove legacy fields:

```typescript
// RuntimeProgressSnapshot — remove:
diagram_running?: number;
diagram_queued?: number;

// RuntimeConcurrencyPolicy — remove:
max_diagram_concurrency?: number;

// RuntimeTimeoutPolicy — rename:
// diagram_inner_timeout_seconds → media_inner_timeout_seconds
// diagram_node_budget_seconds  → media_node_budget_seconds

// ProgressUpdateStage — remove:
| 'generating_diagram'
```

Verify nothing reads removed fields:
```bash
grep -r "diagram_running\|diagram_queued\|max_diagram_concurrency\|diagram_inner_timeout\|diagram_node_budget\|generating_diagram" frontend/src/
```
Must return zero results after removal.

---

## Tests — unit only

| Test file | What to add/update |
|---|---|
| `tests/services/test_generation_report_recorder.py` | Replace `visual_commitment` fixture fields with `visual_placements_count`. Add test: `VisualPlacementsCommittedEvent` populates `section.visual_placements_summary`. Add test: `SimulationTypeSelectedEvent` populates `section.simulation_type_selected`. |
| `tests/config/test_settings_bootstrap.py` | Update curriculum default assertion (60→90). Update diagram node budget default assertion (60→90). Add assertion for `pipeline_timeout_interaction_seconds == 60.0`. |
| `tests/pipeline/test_media_prompts.py` | Already covers `content_brief` and `RENDER_MODE` — no changes needed. |

---

## Verification

After the sweep:

```bash
# No visual_commitment anywhere
grep -r "visual_commitment" backend/src/ --include="*.py"

# No legacy frontend fields
grep -r "diagram_running\|diagram_queued\|max_diagram_concurrency\|generating_diagram" frontend/src/

# Timeout field exists in config
grep "pipeline_timeout_interaction_seconds" backend/src/core/config.py

# New event types registered
grep "visual_placements_committed\|slot_render_mode_resolved\|simulation_type_selected" backend/src/telemetry/service.py
```

All must return the expected results.

---

## Scope boundaries

**In scope:**
- `GenerationReportOutlineSection.visual_commitment` → `visual_placements_count`
- Timeout config: two default updates + one new field + simulation wiring
- Observability: four new events, four new report fields, recorder handlers, publish sites
- Frontend: four legacy type field removals

**Out of scope:**
- `diagram_outcomes` → `media_outcomes` state key rename (PR 10 — deferred)
- `IntentResolvedEvent` publish sites (PR 7 LLM normalizer not yet firing events)
- `prompt_used` field on `VisualFrameResult` (deferred — optional debug feature)
- Lectio schema changes (`PracticeProblem.diagram`, `WorkedExampleContent.diagram`)
