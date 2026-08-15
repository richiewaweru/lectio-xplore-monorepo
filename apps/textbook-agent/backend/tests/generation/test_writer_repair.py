"""Informed repair path includes prior output and validation errors."""

from __future__ import annotations

import pytest

from generation.page_objects import (
    ContentValidationError,
    WriterContext,
    dispatch_writer_async,
)
from generation.page_objects.registry import normalize_persisted_document_json
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


def _aside_ctx() -> WriterContext:
    return WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "s1-aside",
                "position": 0,
                "intent": "diagnose-misconception",
                "object": "aside",
                "evidence": "soil is not food",
                "brief": "The roots take in water; the leaves make food.",
            }
        ),
        use_llm=True,
        section_id="section-1",
        generation_id="gen-rich-text",
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
async def test_rich_text_document_is_unwrapped_for_plain_aside_body() -> None:
    rich_body = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Roots take in water."}],
            }
        ],
    }
    provider = ScriptedWriterProvider(
        scenarios={
            "rich_text": {
                "responses": {
                    "s1-aside": [
                        {"attempt": 1, "mode": "dict", "value": {"body": rich_body}},
                    ]
                }
            }
        },
        scenario_name="rich_text",
    )
    result = await dispatch_writer_async(_aside_ctx(), provider=provider)
    assert result.content["body"] == "Roots take in water."
    assert provider.call_count() == 1


def test_persisted_document_normalizes_rich_text_aside() -> None:
    document = {
        "lectio_document": {
            "sections": [
                {
                    "blocks": [
                        {
                            "object": "aside",
                            "content": {
                                "body": '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"Use the leaves."}]}]}'
                            },
                        }
                    ]
                }
            ]
        }
    }
    normalized = normalize_persisted_document_json(document)
    assert normalized["lectio_document"]["sections"][0]["blocks"][0]["content"]["body"] == "Use the leaves."


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
