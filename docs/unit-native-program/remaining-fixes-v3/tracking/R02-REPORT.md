# R02 Report — Exact sources and teaching context

Phase/status: **PASS**

Plan before implementation: `tracking/R02-PLAN.md`

Base commit: `b86f4b02` (`feat(learn): author complete activity envelope not brief-as-prompt`).

## Files and behavior changed

### Source resolver
- `learn/generation/source_resolver.py`: `resolve_learn_work_order_sources()` resolves only `order.approved_item_ids`; empty refs → generate with zero scoped items; missing/duplicate/multi-source failures before provider invoke.
- `authoring_adapter.py`: all authoring entrypoints use resolver; `_input_map` receives scoped items only; `_validate_teaching_context()` enforces objective/facts for generate.
- `interaction_writer.py`: contract assembly uses resolver primary item, not `approved_items[0]`.
- Converters: sequence IDs preserved without slugify; short-response preserves `accepted_answers` arrays.

### Teaching context
- `learn/generation/preparation_context.py`: `LearnPreparationContext`, `learn_preparation_context_from_state()`, `lesson_context_from_preparation()`.
- `native_production.py`: accepts `preparation_context`; threads `allowed_facts`, `terminology`, and merged `lesson_context` into `author_learn_work_orders` (no hardcoded empty lists).
- `native_execution.py`: loads pinned state via `PageDocumentRepository` when `preparation_context` omitted; passes context into closed production.

### Tests
- Added `tests/remaining_fixes/test_r02_source_resolver.py`, `test_r02_teaching_context.py`, `test_r02_conversion_preservation.py`.
- R00 source-leak and empty-context tests pass; R01/A04 callers updated with explicit preparation inputs where generate validation requires them.

## Preparation threading

```
shared_preparation_packet (pinned page generation state)
  → learn_preparation_context_from_state()
  → produce_learn_from_approved_teaching(preparation_context=…)
  → build_closed_learn_production_async(preparation_context=…)
  → lesson_context_from_preparation() + allowed_facts + terminology
  → author_learn_work_orders → run_learn_authoring → AuthoringEngine.execute
```

Direct callers may pass `LearnPreparationContext` explicitly (tests, scripts). Production path loads from `preparation_generation_id` without reloading unrelated current data.

## Gate results

| Gate | Status | Evidence |
| --- | --- | --- |
| R02-G01 | PASS | `test_r02_g01_*`, R00 source-leak no-ref test |
| R02-G02 | PASS | `test_r02_g02_*`, R00 explicit q2 test |
| R02-G03 | PASS | `test_r02_g03_*` |
| R02-G04 | PASS | `test_r02_g04_*`, R00 empty-context test |
| R02-G05 | PASS | `test_r02_g05_*` |
| R02-G06 | PASS | `test_r02_g06_*` |

Command: `cd apps/textbook-agent/backend; uv run pytest -q tests/remaining_fixes/ -k "r00_approved or r00_empty or r00_incomplete or r01 or r02"` — 32 passed.

Evidence: `evidence/r02/pytest-r02-all.txt`

## Deferred

- Print `run_print_authoring` still binds `approved_items[0]` when pool is passed; Learn gates do not require Print resolver in R02.
- R03 keyword-selection regression (`test_r00_keyword_selection`) remains open for semantic selector work.
