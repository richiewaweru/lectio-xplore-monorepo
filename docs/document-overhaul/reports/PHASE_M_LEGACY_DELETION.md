# Phase M — Legacy Deletion Report

**Date:** 2026-09-11  
**Branch:** `refactor/document-model-overhaul`  
**Goal:** Hard-delete ordinary `component_lectio` production path. Production Learn generation uses LearnDocument v2 / `native_learn` only.

## Deleted paths

### Backend package
- `apps/textbook-agent/backend/src/learn/generation/component_lectio/` (entire directory)
  - `__init__.py`
  - `coverage_audit.py`
  - `errors.py`
  - `fixtures.py`
  - `lane_dispatch.py`
  - `launcher.py`
  - `payload_strategies.py`
  - `payload_validation.py`
  - `pipeline.py`
  - `service.py`

### Learn-owned Print helper
- `packages/lectio-learn/src/lib/print/RuledLines.svelte`
- Export removed from `packages/lectio-learn/src/lib/print/index.ts`
- Call sites inlined local ruled-line markup:
  - `ShortAnswerQuestion.svelte`
  - `StudentTextbox.svelte`
  - `PracticeStack.svelte`
  - `ReflectionPrompt.svelte`

### Obsolete tests (deleted)
- `tests/generation/test_component_lectio_e2e.py`
- `tests/generation/test_component_lectio_final_contract.py`
- `tests/generation/test_component_lectio_lifecycle.py`
- `tests/generation/test_component_lectio_prelive.py`
- `tests/v3_execution/test_component_lectio_runtime.py`

### Obsolete tests (gutted / skipped)
- `tests/routes/test_d6b_unit_learn_publish.py` — module skipped (Phase M)
- `tests/authoring_correction/test_a04_learn_authoring.py` — payload_strategies audit skipped
- `tests/routes/test_builder_lessons.py` — Component Lectio open cases now expect HTTP 410
- `tests/application/test_p03_realization_gates.py` — pipeline default / learn marker → `native_learn`

## Production retarget

| Surface | Change |
|---|---|
| `learn/generation/native_execution.py` | Uses `produce_learn_document_from_teaching`; persists LearnDocument v2; `source_type=learn_document`; `control.pipeline=native_learn`; **no** `PageDocumentRepository` import — prep from `GenerationModel.chunked_state_json` / caller |
| `infra/config.py` | `GenerationPipeline` = `native_learn` \| `learn_document`; default `native_learn` |
| `pipeline_dispatch.py` | Admits only active markers; treats historical Component Lectio as inert/retired |
| `units_dispatch.py` | Raises retired / document-path required (no launcher) |
| `canonical.py` | Canonical pipelines = `native_learn`, `learn_document` |
| `units_routes.py` | Builder open uses native Learn document path; dispatch returns 410 on retired |
| Builder service/routes | Open for `native_learn` / `learn_document`; Component Lectio open → HTTP 410 |
| Pack repository/routes | `list_canonical_by_user` / `canonical_generations_for_pack` |
| Release routes | Active sources exclude Component Lectio |
| Realizations classify | Learn marker = `native_learn` / `learn_document` |

## Search commands run

```bash
rg -n "component_lectio|ExplanationBlock|RuledLines" apps/textbook-agent/backend/src packages/lectio-learn/src --glob '!**/migrations/**'
rg -n "from learn\.generation\.component_lectio|import component_lectio" apps/textbook-agent/backend/src
rg -n "RuledLines" packages/lectio-learn/src apps/textbook-agent/backend/src
rg -n "component_lectio" apps/textbook-agent/backend/src --glob '!**/migrations/**'
```

### Import evidence
- **Zero** `from learn.generation.component_lectio` / `import component_lectio` in production `backend/src`.
- **Zero** `RuledLines` references under `packages/lectio-learn/src` and `backend/src`.

## Remaining `component_lectio` references (intentional, non-production-path)

Allowed outside pure migrations/docs only where required to reject historical rows or match existing DB schema:

| Location | Why kept |
|---|---|
| `learn/generation/pipeline_dispatch.py` | Historical marker set + retired error text for old chunked_state rows |
| `learn/authoring/builder/service.py` | Retired stub that always raises; detects old pipeline marker |
| `learn/authoring/builder/routes.py` | HTTP 410 for `source_type` / open endpoint used by old clients |
| `infra/database/models.py` | Partial unique index `uq_editable_lessons_component_generation` still matches live DB DDL from migration `20260905_0034` |
| `**/migrations/**` | Historical Alembic / data backfill — **not deleted** |

## Remaining `ExplanationBlock` references

Frontend `packages/lectio-learn` still ships ExplanationBlock components, templates, schema validators, and demos. Backend only retains `"ExplanationBlock"` inside `document/composition.py` `LEGACY_LEARN_COMPONENT_IDS` (denylist so document realizers never select it). Full frontend component registry deletion is deferred to Phase N package cleanup.

## Test results

```text
cd apps/textbook-agent/backend
uv run python -m pytest tests/document tests/learn tests/print_learn/test_document_realizers.py tests/print_learn/test_print_document_align.py -q --tb=line
```

**Result:** `29 passed, 1 warning` (GenerationFieldContract schema field name warning — pre-existing).

## Acceptance notes

- Production Learn persistence is LearnDocument v2 via document realizer.
- Ordinary Component Lectio package is gone; Units/Builder dispatch cannot launch it.
- Historical migrations preserved.
- Frontend ExplanationBlock cleanup intentionally left for Phase N.
