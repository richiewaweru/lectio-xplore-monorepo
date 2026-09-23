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

__all__ = [
    "NO_OUTPUT_RETRY",
    "StructuredCallContext",
    "get_structured_mode",
    "prepare_structured_agent",
    "run_json_agent",
    "run_structured_agent",
    "structured_output_for_model",
]
