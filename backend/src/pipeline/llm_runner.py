from __future__ import annotations

from typing import Any

import core.events as core_events
from core.llm import RetryPolicy, run_llm as core_run_llm
from core.llm import ModelSlot, ModelSpec
from pipeline.providers.registry import get_node_text_slot, get_node_text_spec
from pipeline.types.requests import GenerationMode

event_bus = core_events.event_bus


async def run_llm(
    *,
    generation_id: str,
    node: str,
    agent: Any,
    user_prompt: str,
    model: Any | None = None,
    slot: ModelSlot | None = None,
    section_id: str | None = None,
    retry_policy: RetryPolicy | None = None,
    spec: ModelSpec | None = None,
    model_settings: dict | None = None,
    generation_mode: GenerationMode = GenerationMode.BALANCED,
) -> Any:
    resolved_slot = slot or get_node_text_slot(node)
    resolved_spec = spec or get_node_text_spec(node, generation_mode)
    return await core_run_llm(
        caller=node,
        trace_id=generation_id,
        generation_id=generation_id,
        agent=agent,
        user_prompt=user_prompt,
        model=model,
        slot=resolved_slot,
        section_id=section_id,
        retry_policy=retry_policy,
        spec=resolved_spec,
        model_settings=model_settings,
    )
