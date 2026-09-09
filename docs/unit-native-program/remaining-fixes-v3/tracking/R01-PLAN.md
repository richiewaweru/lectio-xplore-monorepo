# R01 Plan — Complete interaction authoring

## Scope

Implement R1 from `SPECIFICATION.md`: provider-authored prompt, config and feedback survive normal production; convert-approved preserves approved stem and keys; trusted policy fields remain code-owned. Package `@lectio/learn` exposes a generate-mode **authoring envelope** around the unchanged runtime config schema.

## Phase steps

1. **Package envelope (`packages/lectio-learn`)**
   - Add `buildAuthoringEnvelopeSchema(configSchema)` in `views.ts` for the eight core interactions.
   - Writer view: `payload_schema` = envelope (generate provider output); add `config_schema` = runtime config; keep `payload_schema_ref` on config.
   - Extend `field_guidance` with `prompt`, `feedback.correct`, `feedback.incorrect`, `feedback.partial`.
   - Update eight interaction instruction files under `contracts/authoring/instructions/` to require student-facing question and feedback (brief is context only).
   - Regenerate exports (`npm run export-contracts`) and sync backend contracts.

2. **Backend adapter (`authoring_adapter.py`)**
   - Mode-aware `_payload_schema_validator`: generate validates envelope; convert validates `config_schema`.
   - Config evaluators validate `payload.config` when envelope-shaped.
   - `interaction_contract_from_authoring_result`: generate uses authored `prompt`/`config`/`feedback`; convert uses approved stem and preserved keys; strip model `id`/`assessment_mode`/`concept_refs`; no brief fallback.
   - Convert missing stem/key → `INCOMPATIBLE_APPROVED_ITEM` via `AuthoringEngineError`.
   - Convert feedback: preserve when present; else documented conversion default (convert-only).
   - Pass `approved_item` into contract assembly from all callers.

3. **Tests**
   - Update A04 / P06 / remaining_fixes mocks to return `{prompt, config, feedback}` for generate.
   - Make `test_r00_incomplete_activity.py` pass without weakening assertions.
   - Add `tests/remaining_fixes/test_r01_*.py` for R01-G01..G04.

4. **Evidence and tracking**
   - Run focused pytest; save logs under `evidence/r01/`.
   - Update `GATES.csv` R01 rows, `STATE.json`, `R01-REPORT.md` with exact commit SHA.

5. **Commit** — `feat(learn): author complete activity envelope not brief-as-prompt` (stage only R01 files).

## Done criteria

- R01-G01: Provider prompt/config/feedback survive `build_closed_learn_production` and `run_learn_work_order_authoring`.
- R01-G02: Approved stem preserved; missing stem/key fails with `INCOMPATIBLE_APPROVED_ITEM`.
- R01-G03: Model-supplied trusted fields stripped; assembly owns id/assessment_mode/concept_refs.
- R01-G04: All eight core interactions pass generate and convert tests with canonical config schema.
