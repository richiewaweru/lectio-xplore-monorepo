# A06 Report — Integrated offline acceptance

> **R00 reopen (2026-09-09, reviewed HEAD `db157f0`):** A06 gates are **REOPENED**. Historical integrated-suite evidence under `evidence/a06/` is preserved as historical only.

> **R04 supersession (2026-09-09):** Overstated A06 tests (`deepcopy` reload, hash-only publish, `dispatch_writer_async` dual-path, evaluator-only interaction checks) were removed or skipped. Real evidence lives in remaining-fixes-v3 **R04-G01..G06** (`tests/remaining_fixes/test_r04_*.py`, `interaction-shells.r04.test.ts`).

Status: REOPENED — superseded integrated claims; partial regressions remain in `test_a06_integrated_offline.py`

## Summary
Historical report below recorded PASS at prior HEAD using evidence that R04 audit found insufficient per POLICY.md. R04 implements honest persistence, publish, runtime, failure-retry, component-mount, and instruction-drift gates.

Live/model-quality verification remains DEFERRED.

## Gates (current)
- A06-G01 PASS: tracking artefacts exist
- A06-G02 SUPERSEDED → R04-G01 `test_r04_g01_dual_path_persistence`
- A06-G03 PARTIAL: invalid-payload regression retained; interaction/runtime → R04-G03/G05
- A06-G04 SUPERSEDED → R04-G02 `test_r04_g02_publish_builder`
- A06-G05 PARTIAL: writer-request instruction drift + assembly regression; full instruction/release → R04-G06
- A06-G06 PASS: offline vs live separation (unchanged)

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a06/full-offline-gates.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a06/backend-a06-tests.txt`

Validation commands:
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction tests/print_learn/test_p04_native_selection_gates.py tests/print_learn/test_p06_learn_authoring_gates.py tests/print_learn/test_p07_learn_runtime_gates.py tests/print_learn/test_p08_integration_gates.py` → 100 passed
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a06_integrated_offline.py` → 8 passed

Completion wording: Offline corrective gates passed; live/model-quality verification deferred.
