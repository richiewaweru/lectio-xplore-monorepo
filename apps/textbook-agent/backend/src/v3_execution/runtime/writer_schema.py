from __future__ import annotations

from typing import Any

from contracts.lectio import get_component_card, get_section_content_schema
from v3_execution.models import SectionWriterWorkOrder


def build_section_writer_output_schema(order: SectionWriterWorkOrder) -> dict[str, Any]:
    """Build a dynamic JSON Schema for one section-writer work order."""
    section_schema = get_section_content_schema()
    definitions = section_schema.get("definitions", {})
    properties: dict[str, Any] = {}
    required: list[str] = []

    for component in order.section.components:
        card = order.component_cards.get(component.component_id) or get_component_card(
            component.component_id
        )
        if not card:
            continue
        field_name = card.get("section_field")
        if not isinstance(field_name, str) or not field_name:
            continue
        ref = card.get("schema_summary", {}).get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
            continue
        def_name = ref.split("/")[-1]
        field_schema = definitions.get(def_name)
        if not isinstance(field_schema, dict):
            continue
        properties[field_name] = field_schema
        required.append(field_name)

    return {
        "type": "object",
        "title": f"section_{order.section.id}_output",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


__all__ = ["build_section_writer_output_schema"]
