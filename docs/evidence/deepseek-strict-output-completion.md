# DeepSeek Strict Structured Output — Completion Report

## 1. Repository state

- Before SHA: `55dfcaff4a212ca1dab0c0a0495a502c12f98ccf`
- After SHA: uncommitted (implementation in working tree)
- Branch: current checkout
- Default mode: `DEEPSEEK_STRUCTURED_MODE=prompted_json` (rollback-safe default)

## 2. Architecture implemented

```text
canonical schema (Pydantic or Lectio JSON Schema)
→ SchemaSource + fingerprint
→ DeepSeekJsonSchemaTransformer (strict projection)
→ ToolOutput(strict=True) on api.deepseek.com/beta
→ run_llm telemetry + outer repair unchanged
→ canonical Pydantic/Lectio validation
→ semantic validators
→ accept / bounded repair / fail
```

Rollback: set `DEEPSEEK_STRUCTURED_MODE=prompted_json`.

## 3. Files changed

| File | Purpose |
|---|---|
| `src/core/llm/schema.py` | Canonical schema extraction, fingerprint, post-validation |
| `src/core/llm/deepseek_schema.py` | DeepSeek strict JSON Schema projection |
| `src/core/llm/transport.py` | Beta URL + structured model builder |
| `src/core/llm/runner.py` | Structured-call telemetry fields |
| `src/core/events.py` | LLM event schema metadata |
| `src/core/config.py` | `DEEPSEEK_STRUCTURED_MODE` setting |
| `src/v3_execution/llm_helpers.py` | `structured_output_for_model`, `prepare_structured_agent`, `run_structured_agent` |
| `src/v3_execution/runtime/writer_schema.py` | Dynamic section-writer JSON Schema from Lectio contracts |
| `src/v3_execution/models.py` | `QuestionWriterOutput` typed contract |
| All structured LLM call sites | Migrated to `prepare_structured_agent` / `run_structured_agent` |
| `docs/project/V3_PROVIDER_COMPATIBILITY.md` | Updated policy |
| `tests/core/test_deepseek_schema.py` | Transformer unit suite A1–A9 |
| `tests/core/test_llm_transport.py` | Beta URL / structured model tests |
| `tests/core/test_deepseek_integration.py` | Gated live spike + request-shape proof |
| `tests/v3_execution/test_llm_helpers.py` | Strict vs prompted selection |
| `tests/v3_execution/test_writer_schema.py` | Dynamic Lectio writer schema tests |

## 4. PydanticAI compatibility

- Installed version: **1.107.1**
- `ToolOutput(strict=True)`: yes
- `StructuredDict`: yes
- Transformer: `DeepSeekJsonSchemaTransformer` extends `OpenAIJsonSchemaTransformer`
- Dependency upgrade: **not required**

## 5. Test results

| Command | Passed | Failed | Notes |
|---|---:|---:|---|
| Focused regression suite (102 tests) | 102 | 0 | schema, transport, helpers, planner, studio, blueprint |
| Native E2E mock fixture | all scenarios | 0 | `tools/run_native_e2e_fixture.py --provider mock` |
| Live DeepSeek integration | skipped | — | `DEEPSEEK_API_KEY` not set in this environment |

## 6. Live proof status

- Live typed strict call: **not run** (no API key in CI/local shell)
- Request-shape / beta model proof: **passed offline** (`test_prepare_structured_agent_uses_beta_model_for_deepseek_strict`)
- To run live spike: `ALLOW_PAID_LLM_TESTS=true DEEPSEEK_STRUCTURED_MODE=strict_tool pytest -m integration tests/core/test_deepseek_integration.py`

## 7. End-to-end proof

- Native mock E2E: **passed** (`all_valid_out_of_order` and sibling scenarios reached `ready`)
- Real provider native lesson: **not run** (requires `DEEPSEEK_API_KEY` + `--provider real`)

## 8. Intentionally out of scope

| Node | Reason |
|---|---|
| `v3_answer_key_generator` | Deterministic, no LLM |
| Image generation | Binary output |
| `v2_merge_critic` | Prompt stub only; no Agent wired |

## 9. Rollback

```text
DEEPSEEK_STRUCTURED_MODE=prompted_json
```

Downstream Pydantic/Lectio validation remains enabled.

## 10. Enable strict mode

After live DeepSeek spike passes in your environment:

```text
DEEPSEEK_STRUCTURED_MODE=strict_tool
```

Then rerun native E2E with `--provider real`.
