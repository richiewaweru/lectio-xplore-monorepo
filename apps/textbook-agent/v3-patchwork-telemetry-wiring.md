# v3 Patchwork — Telemetry Wiring

## Root cause

The v3 runner emits SSE payloads to the frontend only.
It never publishes to `event_bus`. The `TelemetryMonitor` subscribes
to `event_bus` — so `GenerationReportRecorder` never starts for v3,
no report is saved, and all errors (including the 34 blocking coherence
issues) disappear silently.

The fix is to publish relevant v3 events to `event_bus` inside
`emit_event` and ensure a v3-compatible recorder is initialised.

---

## File 1 — v3_execution/runtime/runner.py

The `emit_event` callable currently only formats SSE. Add event_bus
publication for events the recorder cares about:

```python
from telemetry.event_bus import event_bus   # already exists

async def emit(event_type: str, payload: dict[str, Any]) -> None:
    body = dict(payload)
    body["type"] = event_type
    # SSE to frontend (existing)
    await queue.put(events.format_sse_payload(event_type, body))
    # Telemetry bus (new) — recorder picks this up
    event_bus.publish(generation_id, body)
```

This is a one-line addition inside `sse_event_stream`. The `run_generation`
function already receives `emit_event` as a parameter — no other changes
needed to the runner itself.

---

## File 2 — generation/v3_studio/router.py

The v3 generate endpoint must initialise the recorder before the SSE
stream opens. Currently nothing initialises a recorder for a v3
generation_id.

```python
from telemetry.service import TelemetryMonitor
from telemetry.generation_descriptor import GenerationDescriptor
from generation.v3_studio.session_store import v3_studio_store

@v3_studio_router.post("/generate/start")
async def start_v3_generation(
    body: GenerateStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    ...

@v3_studio_router.get("/generations/{generation_id}/events")
async def stream_v3_generation(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    monitor: TelemetryMonitor = Depends(get_telemetry_monitor),
):
    stored = await v3_studio_store.get_generation_entry(generation_id)

    # Initialise recorder before stream opens
    await monitor.initialise_v3_recorder(
        generation_id=generation_id,
        user_id=str(current_user.id),
        blueprint_title=stored.blueprint.metadata.title,
        subject=stored.blueprint.metadata.subject,
        template_id=stored.template_id,
    )

    return EventSourceResponse(
        sse_event_stream(
            blueprint=stored.blueprint,
            generation_id=generation_id,
            blueprint_id=stored.blueprint_id,
            template_id=stored.template_id,
        )
    )
```

---

## File 3 — telemetry/service.py

Add `initialise_v3_recorder` to `TelemetryMonitor`. This creates a
recorder for a v3 generation_id using a lean descriptor — no
`PipelineDocument`, no v2 pipeline fields:

```python
async def initialise_v3_recorder(
    self,
    *,
    generation_id: str,
    user_id: str,
    blueprint_title: str,
    subject: str,
    template_id: str,
) -> None:
    """Create a recorder for a v3 generation before the SSE stream opens."""
    if generation_id in self._recorders:
        return

    descriptor = GenerationDescriptor(
        id=generation_id,
        user_id=user_id,
        title=blueprint_title,
        subject=subject,
        template_id=template_id,
        generation_mode="v3",       # new mode value — see below
        resource_type="lesson",
    )

    recorder = GenerationReportRecorder(
        generation=descriptor,
        repository=await self._get_report_repository(),
    )
    self._recorders[generation_id] = recorder
    await recorder.start()
```

---

## File 4 — telemetry/service.py — handle v3 event types

The existing `_REPORT_EVENT_TYPES` set and event routing handles v2
pipeline events. Add the v3 event types so the recorder processes them:

```python
# In _REPORT_EVENT_TYPES (or equivalent routing):
_V3_REPORT_EVENT_TYPES = {
    "generation_started",
    "work_orders_compiled",
    "section_writing_started",
    "component_ready",
    "questions_started",
    "question_ready",
    "visual_generation_started",
    "visual_ready",
    "answer_key_started",
    "answer_key_ready",
    "assembly_started",
    "draft_pack_ready",
    "coherence_review_started",
    "deterministic_review_complete",
    "llm_review_started",
    "llm_review_complete",
    "coherence_report_ready",
    "repair_started",
    "component_patched",
    "repair_failed",
    "repair_escalated",
    "resource_finalised",
    "generation_warning",
    # LLM trace events (already handled):
    "llm_call_started",
    "llm_call_succeeded",
    "llm_call_failed",
}
```

The recorder's `apply_event` already handles `llm_call_*` events from
`run_llm` — those fire automatically via event_bus from `core/llm/runner.py`.
So LLM cost, token counts, and latency for every v3 node (signal extractor,
clarification, architect, section writers, question writers, reviewer) will
appear in the report automatically once the event_bus connection is live.

---

## What the report surfaces for v3

Once wired, every generation report will contain:

**Per-node LLM trace** (already handled by existing recorder):
```
node: v3_lesson_architect
  model: claude-opus-4-6  slot: premium
  thinking_tokens: 4210
  tokens_in: 3840  tokens_out: 2190
  latency_ms: 87400
  status: succeeded

node: v3_section_writer (section: orient)
  model: claude-sonnet-4-6  slot: standard
  tokens_in: 1240  tokens_out: 820
  latency_ms: 6200
  status: succeeded
```

**Coherence review results** (new — currently invisible):
```
coherence_review:
  status: repair_required
  blocking_count: 34
  issues:
    - category: missing_planned_content
      severity: blocking
      message: Section 'practice' planned component 'practice-stack'
               not found in generated output
      repair_executor: section_writer
    ...
```

**Generation summary**:
```
status: complete / failed / partial
total_sections: 3  ready: 2  failed: 1
total_llm_calls: 14
total_tokens_in: 18420  total_tokens_out: 9840
cost_usd: 0.82
generation_time_seconds: 143
```

The 34 blocking errors will be visible in full — category, message,
blueprint reference, and which executor was targeted for repair.

---

## Cut v2/v1 bloat from the report

The existing `GenerationReportSummary` has ~40 fields specific to the
v2 pipeline that are meaningless for v3:

```python
# v2-only fields — zero for v3, confusing in report output:
svg_slots_count
svg_success_slots
svg_failed_slots
svg_intent_retry_count
svg_validation_failure_count
svg_sanitizer_failure_count
raw_svg_generation_count
planned_image_slots
image_slots_count
prompt_builder_calls
curriculum_planned_at
planner_trace_sections
duplicate_term_warnings
validation_repair_attempts
validation_repair_successes
diagram_retries
diagram_timeouts
sections_without_media
media_slots_planned
media_slots_ready
media_slots_failed
media_frame_retries
```

**Do not delete these fields** — v2 tests and v2 reports depend on them.

Instead, add a `pipeline_version` field to the report:

```python
class GenerationReport(BaseModel):
    ...
    pipeline_version: Literal["v2", "v3"] = "v2"
```

The `log_final_summary` and any report serialization can then branch
on `pipeline_version` and omit v2-only fields from v3 report output.
This keeps backward compatibility while cleaning up v3 visibility.

---

## Implementation order

```
Step 1 — router.py
  Add initialise_v3_recorder() call before EventSourceResponse
  Verify recorder is created before SSE stream opens

Step 2 — runner.py
  Add event_bus.publish() inside emit() in sse_event_stream
  One line addition

Step 3 — telemetry/service.py
  Add initialise_v3_recorder() method
  Add _V3_REPORT_EVENT_TYPES routing
  Add pipeline_version to GenerationReport

Step 4 — Verify
  Run a full generation
  Check report exists in DB after resource_finalised
  Confirm coherence issues are visible with category + message
  Confirm LLM cost/tokens visible per node
```

---

## Verification

```
□ After resource_finalised, report exists for that generation_id
□ Report contains llm_call entries for v3_lesson_architect,
  v3_section_writer, v3_question_writer
□ Architect entry has thinking_tokens field
□ coherence_report_ready event results in issues array in report
□ The 34 blocking errors are visible with category, message,
  blueprint_ref, suggested_repair_executor
□ Report log_final_summary prints to Railway logs
□ pipeline_version = "v3" in report output
□ v2 reports unaffected — pipeline_version = "v2" by default
```
