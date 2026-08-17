from __future__ import annotations

import pytest

from v3_execution.models import (
    SectionWriterWorkOrder,
    SourceOfTruthEntry,
    WriterSection,
    WriterSectionComponent,
)
from v3_execution.runtime.writer_schema import build_section_writer_output_schema


def _section_order(*, components: list[WriterSectionComponent]) -> SectionWriterWorkOrder:
    return SectionWriterWorkOrder(
        work_order_id="wo-1",
        section=WriterSection(
            id="intro",
            title="Intro",
            learning_intent="Understand the anchor",
            components=components,
        ),
        source_of_truth=[SourceOfTruthEntry(key="anchor", text="Pizza slices")],
        template_id="guided-concept-path",
    )


def test_build_section_writer_output_schema_includes_work_order_fields() -> None:
    order = _section_order(
        components=[
            WriterSectionComponent(
                component_id="explanation-block",
                content_intent="Explain the concept.",
            )
        ]
    )
    schema = build_section_writer_output_schema(order)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert isinstance(schema["properties"], dict)
    assert len(schema["required"]) == len(schema["properties"])


def test_build_section_writer_output_schema_changes_when_contract_changes() -> None:
    order_one = _section_order(
        components=[
            WriterSectionComponent(
                component_id="explanation-block",
                content_intent="Explain the concept.",
            )
        ]
    )
    order_two = _section_order(
        components=[
            WriterSectionComponent(
                component_id="explanation-block",
                content_intent="Explain the concept.",
            ),
            WriterSectionComponent(
                component_id="hook-hero",
                content_intent="Introduce the topic.",
            ),
        ]
    )
    first = build_section_writer_output_schema(order_one)
    second = build_section_writer_output_schema(order_two)
    assert set(second["properties"]) != set(first["properties"])
