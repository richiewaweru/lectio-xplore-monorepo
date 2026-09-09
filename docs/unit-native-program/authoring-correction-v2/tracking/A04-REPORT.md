# A04 Report — Learn content and interaction authoring

Status: PASS

## Summary
Native Learn production now authors content and interaction work orders through the shared `infra.authoring` engine before ordered assembly. Planning briefs are inputs to authoring requests, not final lesson payloads. Assembly consumes validated authoring results keyed by work order id and rejects missing or mismatched results.

The eight core interactions (`choice`, `multi-select`, `fill-blank`, `numeric`, `short-response`, `match-pairs`, `classify`, `sequence`) route through `run_learn_authoring` for both approved conversion and provider generation. Heuristic brief parsing for answer keys was removed. Interaction provenance now records teaching plan identity and hash alongside work-order linkage.

## Gates
- A04-G01 PASS: `test_a04_g01_native_production_authors_content_before_assembly`
- A04-G02 PASS: parametrized core interaction convert/generate tests
- A04-G03 PASS: `test_a04_g03_malformed_approved_keys_fail_without_guessing` plus A00 arbitrary-answer regressions
- A04-G04 PASS: evaluator/render checks in core interaction parametrized tests
- A04-G05 PASS: `test_a04_g05_assembly_rejects_missing_results`
- A04-G06 PASS: `test_a04_g06_policy_content_schemas_and_ordering_preserved`

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a04/backend-a04-tests.txt`

Validation commands:
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a04_learn_authoring.py tests/authoring_correction/test_a00_arbitrary_answers.py tests/authoring_correction/test_a00_brief_as_content.py tests/print_learn/test_p06_learn_authoring_gates.py` -> 42 passed

Completion wording: Offline corrective gates passed; live/model-quality verification deferred.
