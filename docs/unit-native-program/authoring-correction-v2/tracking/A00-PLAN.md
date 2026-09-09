# A00 Baseline Plan

## Scope

Create only baseline documentation and failing regression tests for Authoring Correction Pack v2 A00. Do not implement product fixes, weaken existing tests, mark the new tests xfail, or alter production code.

## Phase Steps

1. Confirm branch and baseline identity.
   - Branch: `feat/unit-print-learn`
   - Expected HEAD: `998e9f36e75f81899a6405a5d199e2f246bcbf9c`
   - Preserve all pre-existing dirty work, especially P05 image evidence, `.tmp`, backend logs/data, and P09 scripts.

2. Read source-of-truth pack material.
   - `README.md`
   - `ARCHITECTURE.md`
   - `SOURCE_MAP.md`
   - `acceptance/POLICY.md`
   - `acceptance/KNOWN_ANSWER_CASES.json`
   - `phases/A00.md`
   - `docs/unit-native-program/COMMAND_MAP.md`

3. Trace production entrypoints.
   - Print: Unit approval enters native Print production through `execute_after_teaching_approval`, closed selection in `build_closed_print_production_plan`, writing through `write_form_blocks`, and provider dispatch through `dispatch_writer_async`.
   - Learn: approved shared teaching enters `produce_learn_from_approved_teaching`, closed Learn production through `build_closed_learn_production`, selection via `build_learn_selection_snapshot`, work orders via `compile_learn_work_orders`, interaction authoring through `write_interaction_from_work_order`, and assembly through `assemble_ordered_learn_document`.

4. Add failing tests under `apps/textbook-agent/backend/tests/authoring_correction/`.
   - Arbitrary Learn answer heuristics: numeric first number, fill-blank last word, and choice invalid-correct fallback.
   - Learn content assembly: brief must not be copied as finished content.
   - Print table provider failure: failed table writing must surface typed failure, not Lit leaf/Covered leaf fallback content.
   - Learn selection: content selection must be semantic, not `content_candidates[0]`.
   - Learn fallback budget: exhausted fallback candidates must remain excluded.

5. Run only the new A00 tests with focused pytest commands.
   - Capture stdout/stderr failure evidence under `evidence/a00/`.
   - Record exact commands, exit status, and intended failure reasons in the baseline.

## Done Criteria

- `tracking/A00-BASELINE.md` records branch/head, dirty work, command map, real call graphs, and requirement mapping.
- `tracking/A00-REQUIREMENT_MAP.md` maps pack requirements to source files and tests.
- New tests fail on the current baseline for the intended defects without xfail markers.
- Evidence files under `evidence/a00/` contain the pytest failures.
