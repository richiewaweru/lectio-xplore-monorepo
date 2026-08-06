"""Informed repair path includes prior output and validation errors."""

from __future__ import annotations

import pytest

from generation.page_objects import (
    ContentValidationError,
    WriterContext,
    dispatch_writer_async,
)
from generation.page_objects.scripted_provider import ScriptedWriterProvider
from v3_blueprint.planning.models import PlannedBlock


def _prose_ctx() -> WriterContext:
    return WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "s1-prose",
                "position": 0,
                "intent": "explain",
                "object": "prose",
                "evidence": "need explanation",
                "brief": "Explain that light supplies energy.",
            }
        ),
        use_llm=True,
        section_id="section-1",
        generation_id="gen-repair-1",
    )


@pytest.mark.asyncio
async def test_repair_includes_prior_output_and_errors() -> None:
    provider = ScriptedWriterProvider(
        scenarios={
            "wrong_schema_then_valid": {
                "responses": {
                    "s1-prose": [
                        {
                            "attempt": 1,
                            "mode": "dict",
                            "value": {"items": [{"text": "not prose"}]},
                        },
                        {"attempt": 2, "mode": "valid"},
                    ]
                }
            }
        },
        scenario_name="wrong_schema_then_valid",
        default_valid={"prose": {"paragraphs": ["Light supplies energy."]}},
    )
    result = await dispatch_writer_async(_prose_ctx(), provider=provider)
    assert result.content["paragraphs"]
    assert provider.call_count() == 2
    repair = provider.repair_prompts()
    assert len(repair) == 1
    prompt = repair[0]
    assert "previous_invalid_output" in prompt
    assert "validation_errors" in prompt
    assert "Explain that light supplies energy." in prompt
    assert "prose" in prompt
    assert "items" in prompt or "paragraphs" in prompt


@pytest.mark.asyncio
async def test_invalid_json_then_valid_repairs() -> None:
    provider = ScriptedWriterProvider(
        scenarios={
            "invalid_json_then_valid": {
                "responses": {
                    "s1-prose": [
                        {"attempt": 1, "mode": "raw", "value": '{"paragraphs": ['},
                        {"attempt": 2, "mode": "valid"},
                    ]
                }
            }
        },
        scenario_name="invalid_json_then_valid",
        default_valid={"prose": {"paragraphs": ["Repaired prose."]}},
    )
    result = await dispatch_writer_async(_prose_ctx(), provider=provider)
    assert result.content["paragraphs"] == ["Repaired prose."]
    assert provider.call_count() == 2


@pytest.mark.asyncio
async def test_permanently_invalid_raises_validation() -> None:
    provider = ScriptedWriterProvider(
        scenarios={
            "permanently_invalid": {
                "responses": {
                    "s1-prose": [
                        {"attempt": 1, "mode": "dict", "value": {"paragraphs": []}},
                        {"attempt": 2, "mode": "dict", "value": {"wrong": True}},
                    ]
                }
            }
        },
        scenario_name="permanently_invalid",
    )
    with pytest.raises(ContentValidationError):
        await dispatch_writer_async(_prose_ctx(), provider=provider)
    assert provider.call_count() == 2
