# R02 Plan — Exact sources and teaching context

## Scope

Implement R2 and R3 from `SPECIFICATION.md` together: one approved-source resolver for all Learn authoring entrypoints; thread pinned preparation (objective, facts, terminology, level, constraints, dependencies) through native production and work-order authoring; mode-specific completeness validation before provider invoke.

## Phase steps

1. **Source resolver (`learn/generation/source_resolver.py`)**
   - Resolve only `order.approved_item_ids` against the pool (never `approved_items[0]`).
   - Empty refs → zero scoped items, `generate` mode, no conversion.
   - Missing ID, duplicate pool IDs, incompatible action/type → fail before `AuthoringEngine.execute`.
   - Pass only resolved items into `_input_map` / `approved_items_when_converting`.
   - Multi-source only when capability converter supports it; else typed incompatibility.
   - Preserve sequence IDs and accepted-answer array structure in converters.

2. **Teaching context (`learn/generation/preparation_context.py`)**
   - `LearnPreparationContext` model and `learn_preparation_context_from_state(state)`.
   - Extend `build_closed_learn_production_async` and `produce_learn_from_approved_teaching` to accept/preload context from pinned `shared_preparation_packet`.
   - Remove hardcoded `allowed_facts=[]` / `terminology=[]` in native production.
   - Merge objective/level/constraints into `lesson_context` for engine inputs.

3. **Authoring adapter + engine validation**
   - Wire resolver through `run_learn_authoring`, `run_learn_work_order_authoring`, `author_learn_work_orders`.
   - Add `_validate_teaching_context` before invoke: blank objective → `MISSING_AUTHORING_INPUT`; empty facts on generate when required; optional empty terminology; convert may omit duplicated facts.
   - Fix `interaction_writer` approved-item resolution via resolver.

4. **Print audit (minimal)**
   - Note `run_print_authoring` still uses pool positional binding; out of R02 Learn gate scope unless trivial fix aligns with shared pattern.

5. **Tests**
   - `tests/remaining_fixes/test_r02_*.py` for R02-G01..G06.
   - Ensure R00 source-leak and empty-context tests pass (update empty-context test to pass `preparation_context` — assertion unchanged).
   - Update A04/P06/P08 callers only if they relied on `[0]` fallback.

6. **Evidence and tracking**
   - Run focused pytest; save logs under `evidence/r02/`.
   - Update `GATES.csv` R02 rows, `STATE.json`, `R02-REPORT.md`.

7. **Commit** — `fix(authoring): exact source resolver and pinned teaching context` (stage only R02 files).

## Done criteria

- R02-G01: No-ref work order gets zero approved items; stays in generate.
- R02-G02: Explicit q2 only in model-visible inputs/prompts; q1 sentinel absent.
- R02-G03: Missing/duplicate/incompatible refs fail pre-provider; multi-source rules enforced.
- R02-G04: Unit preparation→Learn route passes real objective/facts/level/constraints/dependencies.
- R02-G05: Required blank context fails; optional empty terminology and convert-without-facts remain valid.
- R02-G06: Canonical IDs, numeric values, accepted-answer alternatives preserved without lossy coercion.
