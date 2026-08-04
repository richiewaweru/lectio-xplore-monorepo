from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.lectio import get_section_field_for_component
from v3_blueprint.models import ProductionBlueprint
from v3_execution.compile_orders import compile_execution_bundle
from v3_execution.executors.section_writer import execute_section


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _payload_for_field(field: str, content: str) -> dict[str, object]:
    if field == "explanation":
        return {"body": content, "emphasis": []}
    if field == "worked_example":
        return {
            "title": content,
            "solution": [{"step": "", "latex": "", "explain": "", "diagramRef": []}],
            "answer": "",
        }
    if field == "summary":
        return {"paragraphs": [content], "key_points": [], "cta": {}}
    if field == "hook":
        return {
            "headline": content,
            "body": content,
            "anchor": "anchor",
        }
    if field == "practice":
        return {"introduction": "", "items": [], "footnote": "", "diagram": None}
    return {"detail": content}


@pytest.mark.asyncio
async def test_section_writer_emits_component_ready_once_per_component_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bp = _load_example("amara_compound_area.json")
    bundle = compile_execution_bundle(
        bp,
        generation_id="gen-1",
        blueprint_id="bp-1",
        template_id="guided-concept-path",
    )
    order = bundle.section_orders[0]

    async def stub_json_agent(**_kwargs):
        fields: dict[str, object] = {}
        for component in order.section.components:
            field = get_section_field_for_component(component.component_id) or "explanation"
            fields[field] = _payload_for_field(field, component.content_intent)
        return fields

    monkeypatch.setattr(
        "v3_execution.executors.section_writer.run_json_agent",
        stub_json_agent,
    )

    captured: list[tuple[str, dict[str, object]]] = []

    async def emit(event_type: str, payload: dict[str, object]) -> None:
        captured.append((event_type, payload))

    blocks = await execute_section(
        order,
        emit,
        trace_id="trace-1",
        generation_id="gen-1",
        model_overrides=None,
    )

    ready_events = [payload for event, payload in captured if event == "component_ready"]
    assert len(ready_events) == len(order.section.components) == len(blocks)
    assert [payload["component_id"] for payload in ready_events] == [
        component.component_id for component in order.section.components
    ]
    for payload, block in zip(ready_events, blocks, strict=True):
        assert payload["section_id"] == order.section.id
        assert payload["component_id"] == block.component_id
        assert payload["section_field"] == block.section_field
        assert payload["data"] == block.data


@pytest.mark.asyncio
async def test_section_writer_emits_failed_event_before_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bp = _load_example("amara_compound_area.json")
    bundle = compile_execution_bundle(
        bp,
        generation_id="gen-1",
        blueprint_id="bp-1",
        template_id="guided-concept-path",
    )
    order = bundle.section_orders[0]

    async def stub_json_agent(**_kwargs):
        # Missing fields force execute_section to fail validation/coverage.
        return {}

    monkeypatch.setattr(
        "v3_execution.executors.section_writer.run_json_agent",
        stub_json_agent,
    )

    captured: list[tuple[str, dict[str, object]]] = []

    async def emit(event_type: str, payload: dict[str, object]) -> None:
        captured.append((event_type, payload))

    with pytest.raises(RuntimeError):
        await execute_section(
            order,
            emit,
            trace_id="trace-1",
            generation_id="gen-1",
            model_overrides=None,
        )

    event_types = [event for event, _payload in captured]
    assert "section_writing_started" in event_types
    assert "section_writer_failed" in event_types
    failed_payload = next(payload for event, payload in captured if event == "section_writer_failed")
    assert failed_payload["generation_id"] == "gen-1"
    assert failed_payload["section_id"] == order.section.id
    assert isinstance(failed_payload["errors"], list)
    assert isinstance(failed_payload["warnings"], list)
