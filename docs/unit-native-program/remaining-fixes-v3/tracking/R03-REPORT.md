# R03 Report — Model selector for ambiguous shortlists

Phase/status: **PASS**

Plan before implementation: `tracking/R03-PLAN.md`

Base commit: `d39f8177` (after R02).

## Files and behavior changed

### Shared selector (`infra/authoring/capability_selector.py`)
- `select_capability_from_shortlist`: sole candidate automatic; ambiguous shortlists invoke configured `choose` (default `run_capability_selector` via `native_capability_selector` slot).
- Bounded repair on same shortlist; exhaustion raises `CapabilitySelectionError` with no keyword fallback.
- Payload includes eligible IDs, choose_when/reject_when, block brief/intent/action, teaching context.

### Learn
- `select_learn_with_model_async` / `build_learn_selection_snapshot_async`: production path for content and interaction when len>1.
- `build_closed_learn_production_async` awaits async snapshot builder; accepts injectable `choose`.
- `select_learn_deterministically` and `rank_learn_*` retained as explicitly named test utilities only.

### Print
- `select_print_with_model_async` / `build_print_selection_snapshot_async`.
- `build_closed_print_production_plan_async`; executor awaits it.
- Sealed `FormPlan` consumed via `sealed_form_plan` without reselecting.
- Removed `prefer_figure_for_visual_slots` hardcoded overrides; visual constraints narrow shortlist before selector.
- `print/generation/source_resolver.py`: resolve `source_refs` only in `run_print_authoring`.

### Agents / config
- `run_capability_selector` in `curriculum/agents.py`.
- `NATIVE_CAPABILITY_SELECTOR` slot in v3 config.
- Prompt: `resources/native-capability-selector-v1.txt`.

## Selector wiring

**Learn:** `build_closed_learn_production_async` → `build_learn_selection_snapshot_async` → `select_learn_with_model_async` → `select_capability_from_shortlist` → `default_capability_choose` → `run_capability_selector`.

**Print:** `build_closed_print_production_plan_async` → `build_print_selection_snapshot_async` → `select_print_with_model_async` → same shared selector. Sealed planner output skips selector when `sealed_form_plan` is supplied.

## Gate results

| Gate | Status | Evidence |
| --- | --- | --- |
| R03-G01 | PASS | `test_r03_g01_*` |
| R03-G02 | PASS | `test_r03_g02_*` |
| R03-G03 | PASS | `test_r03_g03_*`, R00 keyword regression |
| R03-G04 | PASS | `test_r03_g04_*` |
| R03-G05 | PASS | `test_r03_g05_*` |

Command: `cd apps/textbook-agent/backend; uv run pytest -q tests/remaining_fixes/` — 40 passed.

Evidence: `evidence/r03/pytest-r03-all.txt`

## Deferred

- Live LLM verification of `run_capability_selector` on real provider (unit tests mock `choose`).
- A05/P04 tests still call `select_learn_deterministically` / `rank_*` as explicit test utilities.
