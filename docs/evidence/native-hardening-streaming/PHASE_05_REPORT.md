## Phase 05 report — visual dispatch and patching

### Files changed
- `src/planning/whole_lesson/visual_dispatch.py` (new) — maps pending figures → VisualGeneratorWorkOrder → execute_visual → apply_visual_completion
- `src/planning/whole_lesson/executor.py` — after awaiting_visuals, dispatch pending visuals idempotently

### Behavior
- Reuses existing `execute_visual` / `VisualGeneratorWorkOrder` (no second pipeline)
- Stable request_id lineage via `stable_figure_request_id`
- Ready assets are not redispatched
- Callback patches same document; revision bumps only on material change (existing apply_visual_completion)

### Tests
V01/V02/V07 unit tests passed; PDF route suite still green
