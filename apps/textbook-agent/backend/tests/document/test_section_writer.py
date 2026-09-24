from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson.composer import (
    CompositionChoice,
    validate_and_build_composition,
)
from document.shared_lesson.writer import (
    SectionSource,
    SectionTaskSummary,
    SectionWriterRequest,
    SectionWriteValidationError,
    validate_and_build_section,
    write_section,
)
from infra.authoring.model_policy import SHARED_SECTION_WRITER, get_v3_slot


def _block(
    block_id: str, position: int, intent: str, brief: str | None = None
) -> TeachingPlanBlock:
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief or intent,
        evidence=f"Learners can demonstrate {intent}.",
    )


def _task() -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-check-compare",
        teaching_block_id="block-compare",
        mode="formative",
        action="select-one",
        purpose="Check whether the learner can compare the models",
        prompt="Which model best represents the change?",
        difficulty="guided",
        expected_evidence="Select the model with the correct particle spacing",
        response={"type": "single_choice", "options": []},
        evaluation={"type": "exact_match"},
    )


def _request() -> SectionWriterRequest:
    section = TeachingPlanSection(
        slot_id="section-models",
        display_title="Comparing particle models",
        entry_state=["Learner can name solid and liquid states"],
        must_establish=["Learner explains how heating changes particle motion"],
        avoid_repeating=["Do not reteach the names of the states"],
        bridge_from_previous=None,
        exit_state=["Learner predicts particle motion after heating"],
        specific_purpose="Explain and compare particle models",
        blocks=[
            _block("block-intro", 0, "introduce the water model with a diagram"),
            _block("block-compare", 1, "compare experimental evidence from two models"),
        ],
    )
    task = _task()
    composition = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="block-intro", kind="paragraph", semantic_role="explanation"
            ),
            CompositionChoice(
                teaching_block_id="block-intro", kind="figure", semantic_role="visual_model"
            ),
            CompositionChoice(
                teaching_block_id="block-compare", kind="table", semantic_role="comparison"
            ),
            CompositionChoice(
                teaching_block_id="block-compare", kind="list", semantic_role="evidence"
            ),
        ],
        tasks=[task],
    )
    return SectionWriterRequest(
        section=section,
        composition_plan=composition,
        sources=(
            SectionSource(
                id="source-water-change",
                kind="approved_fact",
                text="Heating water increases the average motion of its particles.",
            ),
        ),
        task_summaries=(
            SectionTaskSummary(
                task_spec_id=task.id,
                teaching_block_id=task.teaching_block_id,
                action=task.action,
                purpose=task.purpose,
                prompt=task.prompt,
                expected_evidence=task.expected_evidence,
            ),
        ),
    )


def _payload_for_item(item) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": item.id,
        "kind": item.kind,
        "teaching_block_id": item.teaching_block_id,
        "accessibility": {"description": "A clear explanation for all learners."},
    }
    if item.kind == "paragraph":
        payload["display"] = {"text": "Heating gives water particles more motion."}
    elif item.kind == "figure":
        payload["display"] = {"caption": "Particle motion after heating"}
        payload["accessibility"] = {"alt_text": "Particles move faster after heating."}
    elif item.kind == "table":
        payload["display"] = {
            "headers": ["Model", "Particle motion"],
            "rows": [["Unheated", "Slower"], ["Heated", "Faster"]],
            "caption": "Compare particle motion",
        }
    elif item.kind == "list":
        payload["display"] = {"ordered": True, "items": ["Add heat", "Particles move faster"]}
    elif item.kind == "heading":
        payload["display"] = {"text": "Compare the models", "level": 3}
    elif item.kind == "callout":
        payload["display"] = {
            "tone": "note",
            "title": "Remember",
            "body": "Motion changes with heat.",
        }
    return payload


def _draft(request: SectionWriterRequest) -> dict[str, Any]:
    return {
        "nodes": [
            _payload_for_item(item)
            for item in request.composition_plan.items
            if item.kind != "task_anchor"
        ]
    }


def test_writes_diverse_section_and_inserts_unchanged_anchor() -> None:
    request = _request()
    result = validate_and_build_section(request=request, draft=_draft(request))

    assert result.title == request.section.display_title
    assert [node.kind for node in result.nodes] == [
        "paragraph",
        "figure",
        "table",
        "list",
        "task_anchor",
    ]
    anchor = result.nodes[-1]
    assert anchor.id == request.composition_plan.items[-1].id
    assert anchor.task_spec_id == request.task_summaries[0].task_spec_id
    assert anchor.teaching_block_id == "block-compare"
    assert anchor.role is None
    section = result.as_shared_section(section_id="shared-section-1", position=0)
    assert section.title == request.section.display_title
    assert section.nodes == result.nodes


def test_writer_uses_standard_slot_without_provider_reasoning() -> None:
    from infra.authoring.model_policy import V3_NODE_REASONING

    assert get_v3_slot(SHARED_SECTION_WRITER).value == "standard"
    assert V3_NODE_REASONING[SHARED_SECTION_WRITER] is False


def test_request_requires_enriched_section_and_exact_task_anchor_registry() -> None:
    request = _request()
    legacy_section = TeachingPlanSection(
        slot_id=request.section.slot_id,
        blocks=request.section.blocks,
    )
    with pytest.raises(ValidationError, match="continuity fields"):
        SectionWriterRequest(
            section=legacy_section,
            composition_plan=request.composition_plan,
            sources=request.sources,
            task_summaries=request.task_summaries,
        )
    with pytest.raises(ValidationError, match="TaskAnchors"):
        SectionWriterRequest(
            section=request.section,
            composition_plan=request.composition_plan,
            sources=request.sources,
            task_summaries=(),
        )


@pytest.mark.parametrize(
    "attack", ["missing", "extra", "reordered", "retyped", "wrong_owner", "anchor"]
)
def test_rejects_composition_shape_attacks(attack: str) -> None:
    request = _request()
    draft = _draft(request)
    nodes = draft["nodes"]
    if attack == "missing":
        nodes.pop()
    elif attack == "extra":
        nodes.append(deepcopy(nodes[-1]))
    elif attack == "reordered":
        nodes[0], nodes[1] = nodes[1], nodes[0]
    elif attack == "retyped":
        nodes[0]["kind"] = "heading"
        nodes[0]["display"] = {"text": "Heating the model", "level": 2}
    elif attack == "wrong_owner":
        nodes[0]["teaching_block_id"] = "block-compare"
    elif attack == "anchor":
        nodes.append(
            {
                "id": "invented-task-anchor",
                "kind": "task_anchor",
                "teaching_block_id": "block-compare",
                "task_spec_id": "invented-task",
            }
        )

    with pytest.raises(SectionWriteValidationError):
        validate_and_build_section(request=request, draft=draft)


def test_rejects_unknown_fields_planning_leaks_placeholders_and_unapproved_numbers() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["print_page"] = 1
    with pytest.raises(SectionWriteValidationError):
        validate_and_build_section(request=request, draft=draft)

    for text in (
        "The must_establish field says particles move faster.",
        "Use task-check-compare to answer.",
        "TODO: explain the model.",
        "The temperature reaches 900 degrees.",
    ):
        invalid = _draft(request)
        invalid["nodes"][0]["display"]["text"] = text
        with pytest.raises(SectionWriteValidationError):
            validate_and_build_section(request=request, draft=invalid)


def test_rejects_missing_figure_alt_text_and_malformed_table_content() -> None:
    request = _request()
    invalid_figure = _draft(request)
    del invalid_figure["nodes"][1]["accessibility"]["alt_text"]
    with pytest.raises(SectionWriteValidationError):
        validate_and_build_section(request=request, draft=invalid_figure)

    invalid_table = _draft(request)
    invalid_table["nodes"][2]["display"]["rows"] = [["Only one cell"]]
    with pytest.raises(SectionWriteValidationError, match="header width"):
        validate_and_build_section(request=request, draft=invalid_table)


@pytest.mark.asyncio
async def test_uses_section_aware_then_targeted_repair_with_three_call_limit() -> None:
    request = _request()
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        result = _draft(request)
        if len(calls) == 1:
            result["nodes"].pop()
        elif len(calls) == 2:
            result["nodes"][0]["display"]["text"] = "The must_establish field is satisfied."
        return result

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 3
    assert calls[0]["repair"] is None
    assert calls[1]["repair"]["scope"] == "section"
    assert calls[2]["repair"]["scope"] == "targeted"
    assert calls[2]["repair"]["affected_node_ids"] == [request.composition_plan.items[0].id]
    assert result.nodes[-1].kind == "task_anchor"


@pytest.mark.asyncio
async def test_stops_after_initial_plus_two_failed_repairs() -> None:
    request = _request()
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        return {"nodes": []}

    with pytest.raises(SectionWriteValidationError):
        await write_section(request=request, provider=provider)
    assert calls == 3


@pytest.mark.asyncio
async def test_provider_failure_fails_closed_without_repair() -> None:
    request = _request()
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider authentication failed")

    with pytest.raises(RuntimeError, match="authentication"):
        await write_section(request=request, provider=provider)
    assert calls == 1
