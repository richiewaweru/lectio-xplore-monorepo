"""Compatibility re-export. Current callers should import infra.authoring.structured_provider."""

from infra.authoring.structured_provider import *  # noqa: F403
from infra.authoring.structured_provider import (
    NO_OUTPUT_RETRY,
    StructuredCallContext,
    get_structured_mode,
    prepare_structured_agent,
    run_json_agent,
    run_structured_agent,
    structured_output_for_model,
)

from core.llm.runner import run_llm
from infra.authoring.model_policy import (
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)
from pydantic_ai import Agent

__all__ = [
    "Agent",
    "NO_OUTPUT_RETRY",
    "StructuredCallContext",
    "get_structured_mode",
    "get_v3_model_settings",
    "get_v3_slot",
    "get_v3_spec",
    "prepare_structured_agent",
    "run_json_agent",
    "run_llm",
    "run_structured_agent",
    "structured_output_for_model",
]
