# M4-M6 and M10 delivery evidence (2026-08-09)

## Truthful recovery and ready navigation

Studio now consumes backend `next_action` without fallback inference:

- `retry_items`, `retry_teaching`, and `retry_native` use checkpointed native retry;
- `retry_visuals` uses the dedicated visual-only endpoint;
- terminal or unknown actions expose no retry button;
- `ready` stops polling and streams, then navigates exactly once to
  `/studio/generations/<id>`.

Focused Studio result: **28 tests passed**. The matrix covers all four retry actions,
unknown/terminal behavior, dedicated visual dispatch, and duplicate ready events.

## Native viewer and PDF

- Native identity is resolved before rendering/adaptation.
- Missing or malformed native V2 returns/furnishes an explicit native contract error and never
  falls through to V3 pack rendering.
- Valid V2 bypasses the legacy `SectionContent` adapter.
- `edition=teacher|student` is authoritative from request through print URL and `@lectio/page`.
- Native V2 suppresses the generic legacy answer appendix, so the teacher key renders once;
  student edition hides it.
- Native visual blocks remain in the V2 document used by both editions.

Backend command:

```powershell
uv run pytest tests/generation/test_pdf_export_service.py tests/generation/test_native_pdf_exports.py tests/planning/test_phase02_visual_pdf_routes.py -q --tb=short
```

Result: **20 passed**, one pre-existing Pydantic warning.

Frontend integrated command (native routing, Studio, viewer, and print): result
**10 files passed, 54 tests passed**. `svelte-check` reports zero errors and three pre-existing
unused-CSS warnings in `routes/units/[id]/+page.svelte`.

## Visual-provider telemetry

The existing event/TelemetryMonitor/`llm_calls` pipeline now records actual image-provider
attempts separately from local document patching. Rows/events contain actual generation ID,
generation-derived user attribution, provider, model, visual node, attempt, latency, outcome,
retryability, and error class.

```powershell
uv run pytest tests/v3_execution/test_visual_provider_telemetry.py tests/core/test_llm_runner.py tests/services/test_telemetry_service.py tests/planning/test_planning_trace_events.py -q --tb=short
```

Result: **11 passed**, one pre-existing Pydantic warning.

Ruff passes across every changed backend Python file. `git diff --check` is clean.

## Remaining live proof

- authenticated browser recovery and automatic viewer navigation;
- actual teacher/student PDF byte inspection for answer visibility, visual presence, and layout;
- persisted live telemetry query with zero relevant dropped-attribution warnings;
- provider-backed M7-M9 and final matrix runs.
