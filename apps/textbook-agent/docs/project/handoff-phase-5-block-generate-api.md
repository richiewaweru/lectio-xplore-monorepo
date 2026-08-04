# Handoff: Phase 5 — `POST /api/v1/blocks/generate` (Lesson Builder)

This backend capability supports the **Lectio Lesson Builder** Phase 5 spec: single-block JSON generation with schema guidance from exported Lectio contracts.

## Endpoint

- **Method / path:** `POST /api/v1/blocks/generate`
- **Auth:** Bearer JWT (same as other protected routes).
- **Registration:** `backend/src/generation/routes.py` (router prefix `/api/v1`, route `/blocks/generate`).

## Implementation

| File | Role |
| --- | --- |
| `backend/src/pipeline/block_generate.py` | Request/response models, `run_block_generation`, LLM call, trace events (`source="block_generate"`) |
| `backend/src/pipeline/prompts/block_gen.py` | System/user prompts from component registry + Pydantic `SectionContent` field schemas where applicable |
| `backend/src/pipeline/contracts.py` | Helpers such as `get_component_registry_entry`, `get_section_field_for_component` (as used by block_gen) |

## Tests

- `backend/tests/pipeline/test_block_gen_prompts.py`
- `backend/tests/routes/test_blocks_generate.py`

Run from `backend/` with venv and `PYTHONPATH=src`:

```bash
python -m pytest tests/pipeline/test_block_gen_prompts.py tests/routes/test_blocks_generate.py -q
```

## Consumer

**Repo:** [lectio-lesson-builder](https://github.com/richiewaweru/lectio-lesson-builder) — see its `docs/handoffs/phase-5-ai-assistance.md` for env vars, UI behavior, and E2E notes.

The builder calls this endpoint with `Authorization: Bearer <token>` and JSON matching its `BlockGenerateRequest` type (`src/lib/api/ai-client.ts`).
