# A03 Report — Print authoring engine migration

Status: PASS

## Summary
Normal Print `dispatch_writer_async` now routes LLM-written forms through the package-backed Print authoring adapter and shared `infra.authoring` engine. The whole-lesson executor attaches the selected `PrintWorkOrder` to each writer context so provider prompts carry work-order identity, definition hash, scoped request data, package instructions, and the exact selected payload schema.

The legacy normal-path prompt bypass and advisory `_writer_contract` fallback were removed from `registry.py`. Table and figure provider/repair failures now surface as typed failures instead of falling back to stub content; figures continue to produce explicit `visual_pending` pending assets only after a successful brief.

Approved `questions` and `choices` remain on the deterministic `assemble_questions` / `assemble_choices` path, preserving item IDs, answer keys, and student/teacher separation.

## Gates
- A03-G01 PASS: `test_a03_g01_dispatch_writer_uses_package_instructions_and_schema`
- A03-G02 PASS: `test_a03_g02_table_failure_is_typed_and_never_returns_leaf_stub` plus updated A00 Print table fallback regression
- A03-G03 PASS: `test_a03_g03_approved_question_and_choice_conversion_is_exact`
- A03-G04 PASS: `test_a03_g04_offline_print_forms_and_figure_lifecycle`
- A03-G05 PASS: `test_a03_g05_retry_one_failed_block_preserves_siblings_and_order`

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a03/backend-a03-tests.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a03/backend-a03-print-validations.txt`

Validation commands:
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a03_print_authoring_migration.py` -> 5 passed
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a00_print_table_fallback.py tests/authoring_correction/test_a01_authoring_definitions.py tests/authoring_correction/test_a02_shared_authoring_engine.py tests/authoring_correction/test_a03_print_authoring_migration.py tests/generation/test_writer_repair.py` -> 22 passed

Completion wording: Offline corrective gates passed; live/model-quality verification deferred.
