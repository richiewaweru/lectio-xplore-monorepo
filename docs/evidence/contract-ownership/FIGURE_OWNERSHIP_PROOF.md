# Figure ownership proof

Status: **PASS — figure provider ownership fully proven**

## Baseline

- Starting HEAD: `30589f61e4c1b913f8a7fd44a4397d7c592e7759`
- Casa pack expected ancestor: `048f54ff42bd36596f22bb48c9d01d89bbb96f6d` (ancestor of current HEAD)
- Resulting HEAD: uncommitted proof changes on `30589f6`

## Files changed

- `apps/textbook-agent/backend/src/generation/page_objects/scripted_provider.py`
- `apps/textbook-agent/backend/src/generation/page_objects/prompts.py`
- `apps/textbook-agent/backend/tools/run_native_e2e_fixture.py`
- `apps/textbook-agent/backend/tests/generation/test_form_content_models.py`
- `apps/textbook-agent/backend/tests/generation/test_native_all_forms_e2e.py`
- `apps/textbook-agent/backend/tests/generation/test_writer_repair.py`
- `apps/textbook-agent/backend/tests/planning/test_path_structural_models.py`

Evidence artifacts:

- `docs/evidence/contract-ownership/live-figure-writer-result.json`
- `docs/evidence/contract-ownership/_run_live_figure_writer.py`

## Focused tests

Command (from `apps/textbook-agent/backend`):

```bash
pytest -q \
  tests/generation/test_form_content_models.py \
  tests/generation/test_writer_repair.py \
  tests/generation/test_native_all_forms_e2e.py \
  tests/planning/test_contract_ownership.py \
  tests/planning/test_teaching_plan_draft.py \
  tests/v3_execution/test_item_executor.py \
  tests/planning/test_path_structural_models.py \
  tests/planning/test_path_structural_repair.py \
  tests/planning/test_path_structural_validation.py
```

Result: **101 passed**, 1 warning, 29.98s.

No unexpected regressions in that set.

## Schema proof

- `WRITER_PROVIDER_OUTPUTS["figure"]` is `FigureWriterContent`.
- Canonical persist model remains `FigureContent` with runtime fields.
- `FigureWriterAsset.properties == {"kind"}` on both the Pydantic JSON schema and the DeepSeek strict projection.
- Provider mutation with `request_id`, `status`, and `src` raises `ValidationError`.

Covered by `test_figure_provider_schema_excludes_runtime_owned_asset_fields`.

## Mutation proof

- `ScriptedWriterProvider(mode="valid")` validates against `output_model`.
- A valid-mode figure payload that authors `request_id` / `status` is rejected at the provider boundary.
- `mode="dict"` and `mode="raw"` remain unvalidated fault-injection for repair tests.

Covered by `test_scripted_valid_mode_rejects_provider_owned_figure_identity`, `test_figure_missing_alt_then_valid`, `test_invalid_json_then_valid`, and `test_repair_includes_prior_output_and_errors`.

## Prompt proof

- Figure writer and repair prompts include `## OBJECT-SPECIFIC RULES` from `figure-brief-writer-v1.txt`.
- Both prompts state `Do not output \`request_id\`` and that the backend owns runtime asset identity.
- Non-figure writer prompts stay on the generic system prompt.

Covered by `test_figure_writer_and_repair_prompts_state_runtime_identity_ownership`.

## Materialization proof

Semantic provider output:

```json
{
  "asset": {"kind": "image"},
  "alt_text": "A pending figure of a leaf",
  "caption": "Caption"
}
```

becomes:

- `WriterOutcome.status = visual_pending`
- `content.asset.status = pending`
- `request_id = stable_figure_request_id(generation_id="gate9-figure", block_id="s2-figure")`
- `content.asset.request_id` matches that id
- provider dump `asset` contains only `kind`

Covered by `test_figure_missing_alt_then_valid`.

Gate 9 fixture defaults now strip runtime-owned figure fields before `mode="valid"` validation, so persisted `request_id` is not fed back as fake provider output.

## Real native figure generation

Native writer route: `dispatch_writer_async` → `_llm_write` with `FigureWriterContent`.

| Field | Value |
| --- | --- |
| generation_id | `figure-ownership-live-proof` |
| block_id | `s2-figure` |
| model | `deepseek-v4-flash` (`openai_compatible`, FAST slot) |
| structured mode | `strict_tool` |
| schema | `FigureWriterContent` |
| prompt ownership rules | present |
| pydantic-ai output retries | 0 |
| strict-schema retry happened | no |
| live schema error | `asset.media_brief` extra_forbidden |
| request_id in rejected payload | no |
| native fallback used | yes (same as production figure/table handler) |
| writer status | `visual_pending` |
| asset.status | `pending` |
| asset.request_id | `fig-req-e26a503faaa737cad86553da` |
| matches `stable_figure_request_id` | yes |

The live model tried to attach a media brief as an extra document field. The provider schema rejected it. Runtime identity was not taken from the model. The native figure writer then stamped the code-owned request id and `pending` status.

Artifact: `docs/evidence/contract-ownership/live-figure-writer-result.json`.

## Verdict

**PASS — figure provider ownership fully proven**
