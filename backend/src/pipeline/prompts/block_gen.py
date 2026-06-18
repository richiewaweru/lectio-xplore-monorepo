"""
Prompt builders for single-block AI generation (Lesson Builder / Phase 5).

Uses Lectio-exported component registry + JSON Schema from SectionContent
when the component maps to a known section field.
"""

from __future__ import annotations

import json
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict

from pipeline.contracts import (
    get_capacity_limits,
    get_component_registry_entry,
    get_section_field_for_component,
)


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def get_content_model_for_component(component_id: str) -> type[BaseModel] | None:
    """
    Resolve the Pydantic model for block JSON when the component maps to SectionContent.
    Returns None when the field is absent from SectionContent (use permissive fallback).
    """
    from pipeline.types.section_content import SectionContent

    field_name = get_section_field_for_component(component_id)
    if not field_name or field_name not in SectionContent.model_fields:
        return None
    ann = SectionContent.model_fields[field_name].annotation
    ann = _unwrap_optional(ann)
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann
    return None


def get_edit_schema_fields(component_id: str) -> dict[str, Any]:
    """JSON-Schema-like description for the LLM (from Pydantic when available)."""
    model = get_content_model_for_component(component_id)
    if model is not None:
        return model.model_json_schema()
    return {
        "description": "Plain JSON object; use component purpose and capacity limits below.",
        "additionalProperties": True,
    }


def build_block_system_prompt(component_id: str, template_id: str | None) -> str:
    _ = template_id  # reserved for template-specific tone hooks
    entry = get_component_registry_entry(component_id)
    if entry is None:
        raise ValueError(f"Unknown component_id: {component_id}")

    schema_fields = get_edit_schema_fields(component_id)
    capacity = get_capacity_limits(component_id) or entry.get("capacity", {})

    name = entry.get("name", component_id)
    purpose = entry.get("purpose", "")
    cognitive = entry.get("cognitive_job", "")

    return f"""You generate content for a single educational block.

Component: {name}
Purpose: {purpose}
Cognitive job: {cognitive}

Output a JSON object matching this exact schema:
{json.dumps(schema_fields, indent=2)}

Capacity limits:
{json.dumps(capacity, indent=2)}

Rules:
- Output only valid JSON. No preamble, no markdown fences.
- Every required field must be present.
- Respect all word/item count limits.
- Write at the appropriate grade level.
- Content must be pedagogically sound and accurate."""


def build_block_user_prompt(
    *,
    subject: str,
    focus: str,
    grade_band: str,
    context_blocks: list[dict[str, Any]] | None,
    teacher_note: str | None,
    existing_content: dict[str, Any] | None,
) -> str:
    parts = [
        f"Subject: {subject}",
        f"Focus for this block: {focus}",
        f"Grade band: {grade_band}",
    ]
    if teacher_note:
        parts.append(f"Teacher instruction: {teacher_note}")
    if existing_content:
        parts.append(
            "Existing content to improve (revise in place; keep structure unless asked):\n"
            f"{json.dumps(existing_content, indent=2)}"
        )
    if context_blocks:
        parts.append(
            "Surrounding blocks in this section (context only — do not copy verbatim):\n"
            f"{json.dumps(context_blocks, indent=2)}"
        )
    parts.append("Output only the JSON object for this block.")
    return "\n\n".join(parts)


class _FallbackBlockContent(BaseModel):
    """Permissive output when component_field is not on SectionContent."""

    model_config = ConfigDict(extra="allow")


def output_model_for_component(component_id: str) -> type[BaseModel]:
    """
    Pydantic model used as Agent output_type.
    Falls back to a permissive model when SectionContent has no matching field.
    """
    inner = get_content_model_for_component(component_id)
    if inner is not None:
        return inner
    return _FallbackBlockContent
