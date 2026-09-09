# A02 Report — Reusable authoring engine

> **R00 reopen (2026-09-09, reviewed HEAD `db157f0`):** A02 gates are **REOPENED**. Historical PASS evidence under `evidence/a02/` is preserved as historical only. R00 regressions show production Learn authoring still substitutes brief-as-prompt and binds positional approved pool items. See `remaining-fixes-v3/tracking/R00-REPORT.md`.

Status: REOPENED (historical report below recorded PASS at prior HEAD)
Tested commit: A02 commit at `git HEAD` on `feat/unit-print-learn`

## Summary
- Added `infra.authoring`, a shared async authoring engine with typed request/result/provenance models, schema validation, registered semantic validators, deterministic approved-item conversion, bounded provider transport retries and bounded invalid-output repairs.
- Added Print and Learn authoring adapters that translate existing A01 work orders into the shared engine contract while keeping domain validators/converters inside their owning packages. `print/` and `learn/` do not import each other.
- Kept production migration out of scope for A02: existing Print `dispatch_writer_async` and Learn ordered production paths are unchanged and ready for A03/A04 adapter calls.

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a02/backend-a02-tests.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a02/compileall-a02.txt`

## Commands
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a02_shared_authoring_engine.py`
- `cd apps/textbook-agent/backend; uv run python -m compileall -q src/infra/authoring src/print/generation/authoring_adapter.py src/learn/generation/authoring_adapter.py tests/authoring_correction/test_a02_shared_authoring_engine.py`

## Gate Results
- A02-G01: PASS. Print and Learn adapters both execute through `AuthoringEngine.execute` and provider calls use the same `AuthoringProviderCall` mechanism with distinct package schemas.
- A02-G02: PASS. Captured generate prompts contain only the selected scoped request and exclude unrelated approved items, catalogue markers, sibling schema markers and other-path settings.
- A02-G03: PASS. Malformed provider output is repaired with the original scoped request and precise validation errors; repeated invalid output raises `REPAIR_EXHAUSTED`.
- A02-G04: PASS. Missing definitions, missing required inputs and missing generate providers raise typed failures instead of returning placeholder content.
- A02-G05: PASS. Results include work order, source identities, teaching revision, definition hash and input hash; provider transport retries and invalid-output repairs are separately capped.

Note: `uv run ruff check ...` was attempted but `ruff` is not installed in the current backend environment (`program not found`). Focused pytest and Python compile checks passed.

Offline corrective gates passed; live/model-quality verification deferred.
