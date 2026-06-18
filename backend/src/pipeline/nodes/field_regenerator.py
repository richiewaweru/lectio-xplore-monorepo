"""
field_regenerator node.

Regenerates a single failing field in an already-assembled section.
All other fields are preserved exactly as the model originally produced them.

STATE CONTRACT
    Reads:  current_section_id, generated_sections, assembled_sections,
            rerender_requests, contract
    Writes: generated_sections[sid] (field patched),
            assembled_sections[sid] (field patched),
            completed_nodes, errors
    Slot:   FAST - short targeted output, no need for STANDARD
    Skips:  if no rerender request for current_section_id
            if block_type is not in RETRYABLE_FIELDS
"""

from __future__ import annotations

import json

import core.events as core_events
from langchain_core.runnables.config import RunnableConfig
from pydantic_ai import Agent

from core.config import settings as app_settings
from pipeline.events import FieldRegenOutcomeEvent
from pipeline.llm_runner import run_llm
from pipeline.prompts.field_regen import (
    RETRYABLE_FIELDS,
    build_field_regen_system_prompt,
    build_field_regen_user_prompt,
)
from pipeline.providers.registry import get_node_text_model
from pipeline.runtime_context import retry_policy_for_node
from pipeline.runtime_policy import resolve_runtime_policy_bundle
from pipeline.state import PipelineError, TextbookPipelineState


def _publish_field_regen_outcome(
    generation_id: str,
    section_id: str | None,
    *,
    field_name: str,
    outcome: str,
    error_message: str | None = None,
) -> None:
    if not generation_id or not section_id:
        return
    core_events.event_bus.publish(
        generation_id,
        FieldRegenOutcomeEvent(
            generation_id=generation_id,
            section_id=section_id,
            field_name=field_name,
            outcome=outcome,
            error_message=error_message,
        ),
    )


async def field_regenerator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
    config: RunnableConfig | None = None,
) -> dict:
    state = TextbookPipelineState.parse(state)
    sid = state.current_section_id
    request = state.pending_rerender_for(sid)
    generation_id = state.request.generation_id or ""

    if request is None:
        return {"completed_nodes": ["field_regenerator"]}

    if request.block_type not in RETRYABLE_FIELDS:
        return {"completed_nodes": ["field_regenerator"]}

    section = state.generated_sections.get(sid)
    if section is None:
        return {
            "errors": [
                PipelineError(
                    node="field_regenerator",
                    section_id=sid,
                    message=f"No generated content found for {sid}",
                    recoverable=False,
                )
            ],
            "completed_nodes": ["field_regenerator"],
        }

    model = get_node_text_model(
        "field_regenerator",
        model_overrides=model_overrides,
        generation_mode=state.request.mode,
    )

    agent = Agent(
        model=model,
        output_type=str,
        system_prompt=build_field_regen_system_prompt(state.contract.id),
    )

    try:
        retry_policy = retry_policy_for_node(config, "field_regenerator")
        if retry_policy is None:
            retry_policy = resolve_runtime_policy_bundle(
                app_settings,
                state.request.mode,
            ).retries.for_node("field_regenerator")
        result = await run_llm(
            generation_id=state.request.generation_id or "",
            node="field_regenerator",
            agent=agent,
            model=model,
            user_prompt=build_field_regen_user_prompt(
                section=section,
                failing_field=request.block_type,
                reason=request.reason,
            ),
            section_id=sid,
            generation_mode=state.request.mode,
            retry_policy=retry_policy,
        )

        raw_field = json.loads(result.output)
        patched_payload = section.model_dump(exclude_none=True)
        patched_payload[request.block_type] = raw_field
        patched_section = type(section).model_validate(patched_payload)
        _publish_field_regen_outcome(
            generation_id,
            sid,
            field_name=request.block_type,
            outcome="success",
        )

        return {
            "generated_sections": {**state.generated_sections, sid: patched_section},
            "assembled_sections": {**state.assembled_sections, sid: patched_section},
            "completed_nodes": ["field_regenerator"],
        }

    except json.JSONDecodeError as exc:
        _publish_field_regen_outcome(
            generation_id,
            sid,
            field_name=request.block_type,
            outcome="failed",
            error_message=f"Failed to parse regenerated field JSON: {exc}",
        )
        return {
            "errors": [
                PipelineError(
                    node="field_regenerator",
                    section_id=sid,
                    message=f"Failed to parse regenerated field JSON: {exc}",
                    recoverable=True,
                )
            ],
            "completed_nodes": ["field_regenerator"],
        }
    except Exception as exc:
        _publish_field_regen_outcome(
            generation_id,
            sid,
            field_name=request.block_type,
            outcome="failed",
            error_message=f"Field regeneration failed: {exc}",
        )
        return {
            "errors": [
                PipelineError(
                    node="field_regenerator",
                    section_id=sid,
                    message=f"Field regeneration failed: {exc}",
                    recoverable=True,
                )
            ],
            "completed_nodes": ["field_regenerator"],
        }
