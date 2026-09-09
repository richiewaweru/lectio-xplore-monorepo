# R01 Report — Complete interaction authoring

Phase/status: **PASS**

Plan before implementation: `tracking/R01-PLAN.md`

Base commit/current tested commit and worktree identity: `fcee5b1e83d0f01373e9f6ec7608d0b538588d7c` (`feat(learn): author complete activity envelope not brief-as-prompt`).

## Files and behavior changed

### Package `@lectio/learn`
- `src/lib/learn/capabilities/views.ts`: `buildAuthoringEnvelopeSchema()` wraps runtime config for eight core interactions; writer view exports envelope as `payload_schema` and preserves runtime shape in `config_schema`.
- Eight instruction files under `contracts/authoring/instructions/`: require student-facing prompt and feedback; brief is context only.
- Regenerated `contracts/learn-writer-view.v1.json` and synced to backend.

### Backend
- `authoring_adapter.py`: mode-aware definition schema (envelope for generate, config for convert); assembly uses authored prompt/config/feedback; convert preserves approved stem and keys; strips model trusted fields; convert-only default feedback when approved lacks feedback.
- `interaction_writer.py`, `work_orders.py`: pass approved item into contract assembly; include `config_schema` in definition payload.
- `_convert_fill_blank`: preserve `blank_ids` and `case_sensitive` from approved items.

### Tests
- Updated A04, P06, P08 provider mocks to return `{prompt, config, feedback}` envelopes for generate.
- `test_r00_incomplete_activity.py` passes without weakened assertions.
- Added `tests/remaining_fixes/test_r01_interaction_envelope.py` covering R01-G01..G04.

## Before/after regression evidence

| Before | After |
| --- | --- |
| `interaction_contract_from_authoring_result` used `order.brief` as prompt and generic feedback | Provider-authored prompt and feedback survive `run_learn_work_order_authoring` and `build_closed_learn_production` |
| Generate provider returned config-only | Engine validates full envelope; assembly extracts trusted fields from code |

Evidence: `evidence/r01/pytest-r01-all.txt` — 35 passed (R01 suite + R00 incomplete + A04).

## Gate IDs, exact test references, commands, exit results

| Gate | Status | Tests | Command | Exit |
| --- | --- | --- | --- | --- |
| R01-G01 | PASS | `test_r01_g01_*` | `uv run pytest -q tests/remaining_fixes/test_r01_interaction_envelope.py::test_r01_g01_provider_prompt_feedback_survive_work_order_authoring tests/remaining_fixes/test_r01_interaction_envelope.py::test_r01_g01_provider_prompt_feedback_survive_closed_production` | 0 |
| R01-G02 | PASS | `test_r01_g02_*`, A04 convert cases with stem | `uv run pytest -q tests/remaining_fixes/test_r01_interaction_envelope.py -k g02` | 0 |
| R01-G03 | PASS | `test_r01_g03_model_trusted_fields_stripped` | same file | 0 |
| R01-G04 | PASS | `test_r01_g04_*`, A04 generate/convert | `uv run pytest -q tests/authoring_correction/test_a04_learn_authoring.py tests/remaining_fixes/test_r01_interaction_envelope.py -k g04` | 0 |

## Actual routes/calls exercised

- `run_learn_work_order_authoring` → `run_learn_authoring` → `AuthoringEngine.execute` (generate + convert-approved)
- `build_closed_learn_production` → `author_learn_work_orders` → contract assembly
- `write_interaction_from_request` compatibility path

## Mock boundaries

- Provider mocks return envelope JSON; no live LLM calls.

## Conversion policy (convert-only)

When approved item lacks feedback, assembly applies `_CONVERT_DEFAULT_FEEDBACK` (`Correct.` / `Not yet — try again.`). Approved feedback objects and `feedback_correct`/`feedback_incorrect` fields are preserved when present.

## Remaining defects/environment blockers

- R00 regressions for R2–R4 (approved-source leak, empty teaching context, keyword selection) remain failing by design until R02–R03.
- `short-response` convert without accepted answer still selects `teacher-review` when no answer key is present (work-order capability contract; not brief substitution).

## Next phase

R02 — exact approved-source ownership.
