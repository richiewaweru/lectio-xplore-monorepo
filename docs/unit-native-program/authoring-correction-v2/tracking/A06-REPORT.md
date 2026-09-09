# A06 Report — Integrated offline acceptance

Status: PASS

## Summary
Integrated offline acceptance re-ran the full Authoring Correction v2 gate suite with mocked provider boundaries only. P07 runtime assembly now authors work orders before ordered assembly. P08 Learn production injects `P08LearnMockProvider` through `produce_learn_from_approved_teaching`. Dual-path, evaluation, invalid-payload, publish immutability and definition regressions are covered in `test_a06_integrated_offline.py`.

Live/model-quality verification remains DEFERRED. Historical live evidence is unchanged.

## Gates
- A06-G01 PASS: attributable commands, evidence paths and tracking artefacts recorded
- A06-G02 PASS: `test_a06_g02_dual_path_same_revision_mocked_only`
- A06-G03 PASS: `test_a06_g03_core_interactions_evaluate_and_reload`, `test_a06_g03_invalid_payload_rejected_at_provider_boundary`
- A06-G04 PASS: `test_a06_g04_publish_v1_immutable_v2_hash`
- A06-G05 PASS: `test_a06_g05_definition_edit_changes_contract_hash`, `test_a06_g05_assembly_still_rejects_missing_authored_results`
- A06-G06 PASS: this report separates offline completion from deferred live verification

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a06/full-offline-gates.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a06/backend-a06-tests.txt`

Validation commands:
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction tests/print_learn/test_p04_native_selection_gates.py tests/print_learn/test_p06_learn_authoring_gates.py tests/print_learn/test_p07_learn_runtime_gates.py tests/print_learn/test_p08_integration_gates.py` → 100 passed
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a06_integrated_offline.py` → 8 passed

Completion wording: Offline corrective gates passed; live/model-quality verification deferred.
