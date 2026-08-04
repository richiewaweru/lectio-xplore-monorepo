## Bugfix: Stabilize Inline QC and Targeted Retry Flow

**Classification**: major  
**Scope**: backend pipeline retry/QC state management, diagnostics publishing, retry composites, regression coverage  
**Root cause**:
- The inline-QC rollout was only partially integrated.
- `process_section` published `SectionReportUpdatedEvent.source="section_assembler"` even though the event contract only accepts `assembler | qc_agent`.
- Pending retry requests used an append-only list reducer, so retries could not be consumed or cleared safely after a repair attempt.
- `qc_agent` still iterated all assembled sections even though the graph had moved QC inline per section.
- Retry composites did not share the same merge/report/error behavior as the main section pipeline, which let retry budgets and QC state drift.

### Progress
- [x] Reproduced the failing code path from the `SectionReportUpdatedEvent` validation error
- [x] Identified the rollout mismatches behind the immediate crash and the latent retry-state bug
- [x] Implemented the stabilization fix across state, routing, QC, and retry composites
- [x] Added regression and lifecycle coverage for diagnostics, per-section QC, retry routing, and retry composites
- [x] Ran targeted validation and full repo validation
- [x] Self-reviewed the diff and recorded remaining risks

### Validation Evidence

| Command | Result |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest backend/tests/pipeline/test_pipeline_integration.py -q` | Passed (`34 passed`) |
| `backend/.venv/Scripts/python.exe -m pytest backend/tests/application/test_generation_report_recorder.py -q` | Passed (`4 passed`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts backend/.venv/Scripts/python.exe -m pytest backend/tests/interface/test_generation_tracing.py -q` | Passed (`2 passed`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts backend/.venv/Scripts/python.exe -m pytest backend/tests/interface/test_api.py -q` | Passed (`12 passed`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts backend/.venv/Scripts/python.exe tools/agent/check_architecture.py --format text` | Passed (`No architecture violations found.`) |
| `LECTIO_CONTRACTS_DIR=C:\Projects\Textbook agent\backend\contracts backend/.venv/Scripts/python.exe tools/agent/validate_repo.py --scope all` | Passed |

## Summary

This pass keeps the March 22 inline-QC and targeted-retry direction, but makes the flow internally consistent again.

The immediate production blocker was a diagnostics event mismatch: the runtime published `source="section_assembler"` while the event schema only allowed `assembler` or `qc_agent`. Fixing that alone would have removed the crash, but would still have left retry state stuck in an append-only reducer and QC running at the wrong scope. This pass closes that larger gap.

## What Changed

| Area | Outcome | Primary files |
| --- | --- | --- |
| Diagnostics normalization | Section report events now normalize assembler output to `source="assembler"` while leaving QC output as `source="qc_agent"`. | `backend/src/pipeline/nodes/section_runner.py` |
| Retry state model | Pending retries moved from append-only list semantics to a consumable per-section mapping that supports queue, overwrite, and clear via tombstones. | `backend/src/pipeline/state.py` |
| Shared section execution | Added a shared section-step runner so `process_section`, `retry_diagram`, and `retry_field` all use the same merge, diagnostics, retry budget, and error/report logic. | `backend/src/pipeline/nodes/section_runner.py`, `backend/src/pipeline/nodes/process_section.py`, `backend/src/pipeline/graph.py` |
| Per-section QC | `qc_agent` now evaluates only `current_section_id`, preserves assembler warnings for that section, emits at most one retry request for that section, and clears stale pending retries after success or budget exhaustion. | `backend/src/pipeline/nodes/qc_agent.py` |
| Targeted retry composites | `retry_diagram` now runs `diagram_generator -> section_assembler -> qc_agent`; `retry_field` now runs `field_regenerator -> section_assembler -> qc_agent`. Both preserve untouched section content and refresh QC state. | `backend/src/pipeline/graph.py`, `backend/src/pipeline/nodes/field_regenerator.py` |
| Retry routing | `route_after_qc` now prefers existing pending retry requests when retry nodes re-enter the router, stays section-scoped when `current_section_id` is set, and still falls back to full `process_section` for multi-field or unknown blocking failures. | `backend/src/pipeline/routers/qc_router.py` |
| Streaming/result merging | Runtime merging now respects the new retry-state reducer, and retry composites emit streamed section updates the same way `process_section` does. | `backend/src/pipeline/run.py`, `backend/src/pipeline/runtime_diagnostics.py`, `backend/src/pipeline/nodes/content_generator.py` |
| Regression coverage | Added tests for the original crash, normalized event sources, per-section QC scoping, retry-state lifecycle, router branch selection, and both retry composites. | `backend/tests/pipeline/test_pipeline_integration.py` |

## Public Contract Changes

None.

The public SSE/report contract stays the same:
- `SectionReportUpdatedEvent.source` still exposes only `assembler | qc_agent`
- generation `report_url` behavior is unchanged
- `section_manifest` and existing report payload shapes are unchanged

The only contract shift in this pass is internal:
- `TextbookPipelineState.rerender_requests` is now treated as a per-section keyed structure rather than an append-only list

## Key Implementation Notes

1. Retry budget persistence matters:
   - Retry composites now increment `rerender_count` internally and return that diff back into LangGraph state.
   - Without that round-trip, retries would appear bounded during a single node run but the global state would not remember the increment.

2. Retry clearing now uses tombstones:
   - `qc_agent` writes `{section_id: None}` when a retry should be cleared.
   - The custom reducer removes that pending retry entry instead of re-appending stale state.

3. Retry nodes no longer clear requests themselves:
   - `field_regenerator` and `retry_diagram` focus on patching section content.
   - `qc_agent` is now the authoritative place that decides whether a retry remains queued, changes scope, or clears.

4. Monkeypatched tests stay stable:
   - The shared section runner accepts canonical node names explicitly, so diagnostics and `completed_nodes` remain stable under tests and sub-node patching.

## Remaining Risks / Deferred Work

| Area | Follow-up |
| --- | --- |
| Wider speed handoff tree | This pass stabilizes the retry/QC core only. The existing dirty tree still contains adjacent in-progress files outside this fix scope: `backend/src/pipeline/api.py`, `backend/src/pipeline/nodes/curriculum_planner.py`, `backend/src/pipeline/nodes/diagram_generator.py`, `backend/src/pipeline/prompts/content.py`, `backend/src/pipeline/prompts/shared.py`, `backend/src/pipeline/providers/registry.py`, `backend/src/pipeline/prompts/field_regen.py`, and `docs/project/PIPELINE_SPEED_HANDOFF.md`. |
| Contracts env bootstrap | Repo-root interface/full validation currently needs `LECTIO_CONTRACTS_DIR` pointed at `backend/contracts`. If that env/bootstrap behavior should be automatic, handle it separately from this bugfix. |
| Retry semantics for future repair types | Current routing supports diagram-only, single retryable text field, or full rerun. If future retry types need multi-artifact repair, extend `_classify_retry_scope` deliberately instead of widening current branches ad hoc. |

## Start Here Next Time

1. `backend/src/pipeline/nodes/section_runner.py`
2. `backend/src/pipeline/state.py`
3. `backend/src/pipeline/nodes/qc_agent.py`
4. `backend/src/pipeline/graph.py`
5. `backend/src/pipeline/routers/qc_router.py`
6. `backend/tests/pipeline/test_pipeline_integration.py`
