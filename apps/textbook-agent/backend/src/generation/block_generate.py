"""
Single-block LLM generation for the Lesson Builder (POST /api/v1/blocks/generate).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from pydantic_ai import Agent

import core.events as core_events
from core.events import TraceClosedEvent, TraceRegisteredEvent
from core.llm.runner import run_llm
from core.llm.types import ModelSlot
from contracts.lectio import MANUAL_ONLY_COMPONENT_IDS, get_component_registry_entry
from generation.block_generate_prompts import (
    build_block_system_prompt,
    build_block_user_prompt,
    output_model_for_component,
)
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent
from v3_execution.config.models import (
    V3_BLOCK_WRITER_FAST,
    V3_BLOCK_WRITER_STANDARD,
    get_v3_model,
    get_v3_model_settings,
    get_v3_spec,
)

logger = logging.getLogger(__name__)

_CALLER = "block_generator"


class ContextBlockIn(BaseModel):
    component_id: str
    content: dict[str, Any]


class BlockGenerateRequest(BaseModel):
    lesson_id: str | None = None
    section_id: str | None = None
    component_id: str
    mode: Literal["fill", "improve", "custom"] = "fill"
    subject: str
    focus: str
    grade_band: Literal["primary", "secondary", "advanced"]
    context_blocks: list[ContextBlockIn] | None = None
    teacher_note: str | None = None
    existing_content: dict[str, Any] | None = None
    model_tier: Literal["FAST", "STANDARD"] | None = None
    generation_context: str | None = None


class BlockGenerateResponse(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)


def _slot_for_tier(model_tier: str | None) -> ModelSlot:
    if model_tier and str(model_tier).upper() == "STANDARD":
        return ModelSlot.STANDARD
    return ModelSlot.FAST


async def run_block_generation(
    body: BlockGenerateRequest,
    *,
    user_id: str,
) -> dict[str, Any]:
    if body.component_id in MANUAL_ONLY_COMPONENT_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"component '{body.component_id}' is manual-only and must not be AI-generated",
        )
    if get_component_registry_entry(body.component_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown component_id: {body.component_id}",
        )

    slot = _slot_for_tier(body.model_tier)
    node = V3_BLOCK_WRITER_STANDARD if slot == ModelSlot.STANDARD else V3_BLOCK_WRITER_FAST
    spec = get_v3_spec(node)
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=output_model_for_component(body.component_id),
    )

    trace_id = uuid.uuid4().hex
    core_events.event_bus.publish(
        trace_id,
        TraceRegisteredEvent(
            trace_id=trace_id,
            user_id=user_id,
            source="block_generate",
        ),
    )

    try:
        output_type = output_model_for_component(body.component_id)
        system_prompt = build_block_system_prompt(
            body.component_id,
            template_id=None,
        )
        user_prompt = build_block_user_prompt(
            subject=body.subject,
            focus=body.focus,
            grade_band=body.grade_band,
            context_blocks=[
                {"component_id": b.component_id, "content": b.content}
                for b in (body.context_blocks or [])
            ],
            teacher_note=body.teacher_note,
            existing_content=body.existing_content,
            generation_context=body.generation_context,
        )

        agent = Agent(
            model=model,
            output_type=provider_output,
            system_prompt=system_prompt,
            retries=NO_OUTPUT_RETRY,
        )

        result = await run_llm(
            trace_id=trace_id,
            caller=_CALLER,
            generation_id=None,
            agent=agent,
            user_prompt=user_prompt,
            model=model,
            slot=slot,
            spec=spec,
            section_id=None,
            node=node,
            model_settings=get_v3_model_settings(node),
            structured_context=structured_context,
        )

        raw = result.output
        if hasattr(raw, "model_dump"):
            content = raw.model_dump(mode="json", exclude_none=True)
        elif isinstance(raw, dict):
            content = raw
        else:
            content = json.loads(str(raw))

        return content
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Block generation failed for component_id=%s", body.component_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    finally:
        core_events.event_bus.publish(
            trace_id,
            TraceClosedEvent(trace_id=trace_id, source="block_generate"),
        )

