# Gap Fixes — Independent Retry Flows & Instrumentation Handoff

**Extends**: `docs/project/runs/pipeline-stabilization-recovery-parallelization-handoff.md`
**Branch**: `codex/pipeline-stabilization-recovery-parallel`
**Status**: validated — 139 tests passing (up from 128)

---

## What Was Fixed

Four high-severity gaps in the Codex stabilization implementation were corrected:

### Gap 0 — Diagram and interaction have fully independent retry budgets

Previously, diagram and interaction failures competed for the same `max_rerenders` pool. A failed diagram could exhaust the retry budget before an interaction failure got a chance to recover.

**Now:** `diagram_retry_count` (max 1) and `interaction_retry_count` (max 1) are tracked separately per section. Neither consumes `max_rerenders`, which is reserved for text-field and full-section rerenders.

- `state.py` — added `interaction_retry_count: Annotated[dict[str, int], _merge_dicts]`
- `qc_router.py` — added `_INTERACTION_FIELDS = {"simulation", "simulation_block"}`, `"interaction"` scope in `_classify_retry_scope`, and per-scope budget gating before `Send("retry_interaction", ...)`
- `graph.py` — added `retry_interaction` node (re-runs `interaction_generator → section_assembler → qc_agent`, increments `interaction_retry_count`, does NOT increment `rerender_count`)

**Routing logic:**
- Diagram-only QC block → `retry_diagram` (gated by `diagram_retry_count >= 1`)
- Interaction-only QC block → `retry_interaction` (gated by `interaction_retry_count >= 1`)
- Mixed diagram+interaction only → drains diagram first, interaction on the next QC pass
- Text-field blocks → `retry_field` (unchanged, uses `max_rerenders` pool)
- Full rerenders → `process_section` (unchanged, uses `max_rerenders` pool)

### Gap 1 — `diagram_generator` now emits NodeStartedEvent/NodeFinishedEvent in the parallel path

When `diagram_generator` ran inside `_run_parallel_phase`, it had no instrumentation — its latency and status never appeared in `GenerationReport.sections[i].nodes`. `_run_interaction_path` was already instrumented (it calls `run_section_steps` internally) but `diagram_generator` was a bare call.

**Now:** `_run_parallel_phase` accepts `pre_instrumented: frozenset[str] = frozenset()`. Steps not in the set are wrapped with `NodeStartedEvent`/`NodeFinishedEvent`. Steps in the set (like `interaction_path`) are called directly to avoid double-instrumentation.

- `section_runner.py` — `_run_parallel_phase` has new `_call` inner wrapper; exception branch now appends `PipelineError` instances (not plain dicts); `interaction_retry_count` added to the dict-merge key set
- `process_section.py` — passes `pre_instrumented=frozenset({"interaction_path"})` to `_run_parallel_phase`

### Gap 3A — Interaction type picker deduplicated

`_interaction_type` in `composition_planner.py` and `_pick_simulation_type` in `interaction_decider.py` were identical. Divergence would cause the composition plan and interaction spec to disagree silently.

**Now:** `pick_interaction_type` (exported) lives in `composition_planner.py` as the canonical implementation. `interaction_decider.py` imports and delegates to it; its local copy is removed.

### Gap 3B & Gap 2 — Missing unit test coverage

**New test files:**
- `backend/tests/pipeline/test_composition_planner.py` — 7 tests: skip when no section generated, diagram enabled/disabled per plan and contract, interaction disabled in DRAFT mode, subject-based interaction type routing
- `backend/tests/pipeline/test_partial_rerun.py` — 4 tests: `fan_out_sections` filters to `target_section_ids`, full fan-out without targets, `_seed_initial_state` pre-populates non-targeted sections, does not seed targeted sections

---

## Validation

```
cd backend && uv run pytest
139 passed
```

All 128 prior tests continue to pass. The 11 new tests cover the gap-fix paths.

---

## Key Files Changed

| File | Change |
|------|--------|
| `backend/src/pipeline/state.py` | Added `interaction_retry_count` |
| `backend/src/pipeline/routers/qc_router.py` | `_INTERACTION_FIELDS`, `"interaction"` scope, per-budget gating |
| `backend/src/pipeline/graph.py` | `retry_interaction` node + edge |
| `backend/src/pipeline/nodes/section_runner.py` | `pre_instrumented` param, `_call` wrapper, `PipelineError` in exception branch |
| `backend/src/pipeline/nodes/process_section.py` | Passes `pre_instrumented=frozenset({"interaction_path"})` |
| `backend/src/pipeline/nodes/composition_planner.py` | `_interaction_type` → `pick_interaction_type` (exported) |
| `backend/src/pipeline/nodes/interaction_decider.py` | Imports `pick_interaction_type`, removes local duplicate |
| `backend/tests/pipeline/test_composition_planner.py` | New: 7 tests |
| `backend/tests/pipeline/test_partial_rerun.py` | New: 4 tests |

---

## Pickup Path

The retry infrastructure is now complete. If future work is needed:

1. **Add interaction retry to `reporting.py`** — `interaction_retry_count` and `interaction_timeout_count` counters could be surfaced in `GenerationReportSummary` the same way diagram metrics are
2. **Frontend interaction failure state** — `retry_interaction` failures will arrive as `section_failed` events on the SSE bus; the frontend already handles these but the error message could distinguish "interaction unavailable" from a full section failure
3. **`retry_diagram` budget check in `qc_router`** — the router now checks `diagram_retry_count >= 1` before routing, but `retry_diagram` itself also has a guard (`prior_retry_count >= 1`). The router check is the primary gate; the node-level guard is belt-and-suspenders and could be simplified on a future cleanup pass.
