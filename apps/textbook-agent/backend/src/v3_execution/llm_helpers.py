from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, PromptedOutput, StructuredDict, ToolOutput

from core.config import settings
from core.llm import ModelSpec, build_structured_model, is_deepseek_spec
from core.llm.runner import RetryPolicy, run_llm
from core.llm.schema import SchemaSource, schema_source, validate_canonical_output
from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec

StructuredMode = Literal["strict_tool", "prompted_json"]

_CALLER = "v3_execution"

_NODE_TIMEOUT_KEYS = {
    "v3_section_writer": "section_writer",
    "v3_question_writer": "question_writer",
    "v3_answer_key_generator": "answer_key_generator",
}

# Disables pydantic-ai's in-library structured-output retry.
#
# On a validation failure pydantic-ai appends a corrective request to the *same*
# message history, so the model's own invalid reply is replayed back to the
# provider. DeepSeek rejects that with HTTP 400 "Invalid assistant message:
# content or tool_calls must be set" whenever the invalid reply was
# reasoning-only (empty ``content``).
#
# Apply this only at call sites that own an explicit outer repair attempt, so
# repair has exactly one owner. Sites without an outer loop must keep the
# library default.
NO_OUTPUT_RETRY = {"output": 0}

_DEEPSEEK_PROMPTED_TEMPLATE = (
    "Return only valid JSON matching this schema.\n"
    "Do not call tools.\n"
    "{schema}"
)


@dataclass(frozen=True)
class StructuredCallContext:
    structured_mode: StructuredMode | None = None
    schema_source_kind: str | None = None
    schema_fingerprint: str | None = None
    strict_fallback: bool = False


def get_structured_mode(*, node_name: str | None = None) -> StructuredMode:
    _ = node_name
    mode = settings.deepseek_structured_mode
    if mode not in {"strict_tool", "prompted_json"}:
        return "prompted_json"
    return mode  # type: ignore[return-value]


def _tool_output_name(output_type: Any, source: SchemaSource) -> str:
    if isinstance(output_type, type) and issubclass(output_type, BaseModel):
        return re.sub(r"[^A-Za-z0-9_]+", "_", output_type.__name__).strip("_") or "output"
    if source.kind == "json_schema":
        title = source.canonical_schema.get("title")
        if isinstance(title, str) and title.strip():
            return re.sub(r"[^A-Za-z0-9_]+", "_", title).strip("_")
    return "structured_output"


def structured_output_for_model(
    *,
    output_type: Any | None = None,
    output_schema: dict[str, Any] | None = None,
    spec: ModelSpec,
    structured_mode: StructuredMode | None = None,
) -> tuple[Any, SchemaSource, StructuredCallContext]:
    """Select provider output strategy and return output type + schema metadata."""
    source = schema_source(output_type=output_type, output_schema=output_schema)
    mode = structured_mode or get_structured_mode()
    canonical_type = source.output_type if source.output_type is not None else output_type

    if is_deepseek_spec(spec) and mode == "strict_tool":
        if canonical_type is not None:
            tool_name = _tool_output_name(canonical_type, source)
            provider_output = ToolOutput(canonical_type, name=tool_name, strict=True)
        else:
            provider_shape = StructuredDict(
                source.canonical_schema,
                name=_tool_output_name(None, source),
            )
            provider_output = ToolOutput(provider_shape, strict=True)
        context = StructuredCallContext(
            structured_mode="strict_tool",
            schema_source_kind=source.kind,
            schema_fingerprint=source.fingerprint,
            strict_fallback=False,
        )
        return provider_output, source, context

    if is_deepseek_spec(spec):
        fallback_type = canonical_type if canonical_type is not None else dict[str, Any]
        provider_output = PromptedOutput(
            fallback_type,
            template=_DEEPSEEK_PROMPTED_TEMPLATE,
        )
        context = StructuredCallContext(
            structured_mode="prompted_json",
            schema_source_kind=source.kind,
            schema_fingerprint=source.fingerprint,
            strict_fallback=True,
        )
        return provider_output, source, context

    if canonical_type is not None:
        context = StructuredCallContext(
            structured_mode=None,
            schema_source_kind=source.kind,
            schema_fingerprint=source.fingerprint,
        )
        return canonical_type, source, context

    provider_shape = StructuredDict(
        source.canonical_schema,
        name=_tool_output_name(None, source),
    )
    context = StructuredCallContext(
        structured_mode=None,
        schema_source_kind=source.kind,
        schema_fingerprint=source.fingerprint,
    )
    return provider_shape, source, context


def structured_output_type_for_model(
    output_type: Any,
    *,
    spec: ModelSpec,
) -> Any:
    """Backward-compatible wrapper returning only the provider output type."""
    provider_output, _, _ = structured_output_for_model(
        output_type=output_type,
        spec=spec,
    )
    return provider_output


def _resolve_model(
    *,
    node_name: str,
    spec: ModelSpec,
    structured_context: StructuredCallContext,
    model_overrides: dict | None,
):
    if is_deepseek_spec(spec) and structured_context.structured_mode == "strict_tool":
        return build_structured_model(spec, structured_mode="strict_tool")
    return get_v3_model(node_name, model_overrides=model_overrides)


def prepare_structured_agent(
    *,
    node_name: str,
    output_type: Any | None = None,
    output_schema: dict[str, Any] | None = None,
    structured_mode: StructuredMode | None = None,
    model_overrides: dict | None = None,
) -> tuple[Any, Any, StructuredCallContext, ModelSpec, Any]:
    """Resolve model, provider output type, and telemetry context for Agent construction."""
    spec = get_v3_spec(node_name)
    provider_output, source, structured_context = structured_output_for_model(
        output_type=output_type,
        output_schema=output_schema,
        spec=spec,
        structured_mode=structured_mode,
    )
    if structured_mode is not None:
        structured_context = StructuredCallContext(
            structured_mode=structured_mode,
            schema_source_kind=structured_context.schema_source_kind,
            schema_fingerprint=structured_context.schema_fingerprint,
            strict_fallback=structured_mode == "prompted_json" and is_deepseek_spec(spec),
        )
    model = _resolve_model(
        node_name=node_name,
        spec=spec,
        structured_context=structured_context,
        model_overrides=model_overrides,
    )
    return model, provider_output, structured_context, spec, source


async def run_structured_agent(
    *,
    node_name: str,
    trace_id: str | None,
    generation_id: str | None,
    system_prompt: str,
    user_prompt: str,
    output_type: Any | None = None,
    output_schema: dict[str, Any] | None = None,
    model_overrides: dict | None = None,
    model_settings: dict | None = None,
    repair_attempts: int = 0,
    retries: dict[str, int] | None = None,
    structured_mode: StructuredMode | None = None,
) -> Any:
    spec = get_v3_spec(node_name)
    slot = get_v3_slot(node_name)
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node_name,
        output_type=output_type,
        output_schema=output_schema,
        structured_mode=structured_mode,
        model_overrides=model_overrides,
    )
    source = schema_source(output_type=output_type, output_schema=output_schema)
    effective_model_settings = get_v3_model_settings(
        node_name,
        base_settings=model_settings,
    )
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=system_prompt,
        retries=retries if retries is not None else NO_OUTPUT_RETRY,
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
        retry_policy=RetryPolicy(
            max_attempts=1 + V3_MAX_RETRIES.get(node_name.removeprefix("v3_"), 1),
            call_timeout_seconds=float(
                V3_TIMEOUTS.get(_NODE_TIMEOUT_KEYS.get(node_name, "generation_total"), 120)
            ),
        ),
        repair_attempts=repair_attempts,
        structured_context=structured_context,
    )
    return validate_canonical_output(source, result.output)


async def run_json_agent(
    *,
    node_name: str,
    trace_id: str | None,
    generation_id: str | None,
    system_prompt: str,
    user_prompt: str,
    model_overrides: dict | None = None,
    model_settings: dict | None = None,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = await run_structured_agent(
        node_name=node_name,
        trace_id=trace_id,
        generation_id=generation_id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_type=dict[str, Any] if output_schema is None else None,
        output_schema=output_schema,
        model_overrides=model_overrides,
        model_settings=model_settings,
        repair_attempts=1,
        retries={"output": 1},
    )
    if hasattr(raw, "model_dump"):
        return raw.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(raw, dict):
        return raw
    return json.loads(str(raw))


__all__ = [
    "NO_OUTPUT_RETRY",
    "StructuredCallContext",
    "StructuredMode",
    "get_structured_mode",
    "prepare_structured_agent",
    "run_json_agent",
    "run_structured_agent",
    "structured_output_for_model",
    "structured_output_type_for_model",
]
