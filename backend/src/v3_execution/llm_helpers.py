from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent, PromptedOutput

from core.llm import ModelFamily, ModelSpec
from core.llm.runner import run_llm
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec

_CALLER = "v3_execution"


def structured_output_type_for_model(
    output_type: Any,
    *,
    spec: ModelSpec,
) -> Any:
    if spec.family == ModelFamily.OPENAI_COMPATIBLE and spec.model_name.startswith("deepseek-"):
        return PromptedOutput(
            output_type,
            template=(
                "Return only valid JSON matching this schema.\n"
                "Do not call tools.\n"
                "{schema}"
            ),
        )
    return output_type


async def run_json_agent(
    *,
    node_name: str,
    trace_id: str | None,
    generation_id: str | None,
    system_prompt: str,
    user_prompt: str,
    model_overrides: dict | None = None,
    model_settings: dict | None = None,
) -> dict[str, Any]:
    model = get_v3_model(node_name, model_overrides=model_overrides)
    spec = get_v3_spec(node_name)
    slot = get_v3_slot(node_name)
    effective_model_settings = get_v3_model_settings(
        node_name,
        base_settings=model_settings,
    )

    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(dict[str, Any], spec=spec),
        system_prompt=system_prompt,
    )
    result = await run_llm(
        trace_id=trace_id or generation_id or "v3-execution",
        caller=_CALLER,
        generation_id=generation_id,
        agent=agent,
        user_prompt=user_prompt,
        model=model,
        slot=slot,
        spec=spec,
        section_id=None,
        node=node_name,
        model_settings=effective_model_settings,
    )
    raw = result.output
    if hasattr(raw, "model_dump"):
        return raw.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(raw, dict):
        return raw
    return json.loads(str(raw))


__all__ = ["run_json_agent", "structured_output_type_for_model"]
