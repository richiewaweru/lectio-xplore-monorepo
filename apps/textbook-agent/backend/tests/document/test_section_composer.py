from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson.composer import (
    CompositionChoice,
    CompositionValidationError,
    SectionCompositionDraft,
    SectionCompositionPlan,
    compose_section,
    validate_and_build_composition,
    validate_composition_plan,
)
from infra.authoring.model_policy import SECTION_COMPOSER, get_v3_slot


def _block(block_id: str, intent: str, brief: str | None = None) -> TeachingPlanBlock:
    return TeachingPlanBlock(
        id=block_id,
        position=int(block_id.removeprefix("b")),
        intent=intent,
        brief=brief or intent,
        evidence=f"Learner can demonstrate {intent}.",
    )


def _section(*blocks: TeachingPlanBlock) -> TeachingPlanSection:
    return TeachingPlanSection(slot_id="section-explain", blocks=list(blocks))


def _task(task_id: str, block_id: str) -> SharedTaskSpec:
    return SharedTaskSpec(
        id=task_id,
        teaching_block_id=block_id,
        mode="formative",
        action="select-one",
        purpose="Check the learner's understanding",
        prompt="Which model is accurate?",
        difficulty="guided",
        expected_evidence="Select the accurate model",
        response={"type": "single_choice", "options": []},
        evaluation={"type": "exact_match"},
    )


def _choice(block_id: str, kind: str, role: str) -> dict[str, str]:
    return {"teaching_block_id": block_id, "kind": kind, "semantic_role": role}


@pytest.mark.asyncio
async def test_composes_diverse_section_with_fixed_order_and_stable_ids() -> None:
    section = _section(
        _block("b0", "explain the particle model"),
        _block("b1", "compare two models using evidence"),
        _block("b2", "warn about a misconception in this subsection"),
    )
    response = {
        "items": [
            _choice("b0", "paragraph", "explanation"),
            _choice("b0", "figure", "visual_model"),
            _choice("b1", "table", "comparison"),
            _choice("b1", "list", "evidence"),
            _choice("b2", "heading", "subsection"),
            _choice("b2", "callout", "misconception"),
        ]
    }
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        return response

    first = await compose_section(section=section, tasks=[], provider=provider)
    second = await compose_section(section=section, tasks=[], provider=provider)

    assert len(calls) == 2
    assert first == second
    assert [item.kind for item in first.items] == [
        "paragraph",
        "figure",
        "table",
        "list",
        "heading",
        "callout",
    ]
    assert len({item.id for item in first.items}) == len(first.items)
    assert all(item.id.startswith("shared-node-") for item in first.items)


def test_code_inserts_adjacent_task_anchors_after_owning_block_nodes() -> None:
    section = _section(_block("b0", "explain"), _block("b1", "compare evidence"))
    tasks = [_task("task-a", "b0"), _task("task-b", "b0"), _task("task-c", "b1")]
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
            ),
            CompositionChoice(teaching_block_id="b1", kind="table", semantic_role="comparison"),
        ],
        tasks=tasks,
    )

    assert [(item.kind, item.teaching_block_id, item.task_spec_id) for item in plan.items] == [
        ("paragraph", "b0", None),
        ("task_anchor", "b0", "task-a"),
        ("task_anchor", "b0", "task-b"),
        ("table", "b1", None),
        ("task_anchor", "b1", "task-c"),
    ]
    validate_composition_plan(plan=plan, section=section, tasks=tasks)


def test_composer_uses_standard_slot_without_provider_reasoning() -> None:
    from infra.authoring.model_policy import V3_NODE_REASONING

    assert get_v3_slot(SECTION_COMPOSER).value == "standard"
    assert V3_NODE_REASONING[SECTION_COMPOSER] is False


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ([], "no ordinary node"),
        ([_choice("b0", "unknown", "explanation")], "closed"),
        ([_choice("missing", "paragraph", "explanation")], "unknown Teaching Plan block"),
    ],
)
def test_rejects_missing_block_unknown_kind_and_unknown_block(items, message: str) -> None:
    section = _section(_block("b0", "explain"))
    if items and items[0]["kind"] == "unknown":
        with pytest.raises(ValidationError, match="Input should be"):
            SectionCompositionDraft.model_validate({"items": items})
        return
    with pytest.raises(CompositionValidationError, match=message):
        validate_and_build_composition(
            section=section,
            choices=[CompositionChoice.model_validate(item) for item in items],
            tasks=[],
        )


def test_rejects_too_many_consecutive_paragraphs_and_unsuitable_forms() -> None:
    section = _section(_block("b0", "explain comparison evidence"))
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="summary"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="bridge"),
    ]
    with pytest.raises(CompositionValidationError, match="consecutive paragraphs"):
        validate_and_build_composition(section=section, choices=choices, tasks=[])
    with pytest.raises(CompositionValidationError, match="unsuitable"):
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(teaching_block_id="b0", kind="figure", semantic_role="summary")
            ],
            tasks=[],
        )
    with pytest.raises(CompositionValidationError, match="suitable semantic cues"):
        validate_and_build_composition(
            section=_section(_block("b0", "explain the evidence")),
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="figure", semantic_role="visual_model"
                )
            ],
            tasks=[],
        )


def test_rejects_block_node_ceiling_callout_ceiling_and_false_subsection() -> None:
    section = _section(_block("b0", "compare the evidence"))
    with pytest.raises(CompositionValidationError, match="exceeds 2 ordinary nodes"):
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
                ),
                CompositionChoice(teaching_block_id="b0", kind="table", semantic_role="comparison"),
                CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="evidence"),
            ],
            tasks=[],
        )
    with pytest.raises(CompositionValidationError, match="genuine subsection"):
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="heading", semantic_role="subsection"
                )
            ],
            tasks=[],
        )

    warning_section = _section(
        _block("b0", "warning: avoid the common misconception"),
        _block("b1", "safety warning about this misconception"),
    )
    with pytest.raises(CompositionValidationError, match="callouts"):
        validate_and_build_composition(
            section=warning_section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="callout", semantic_role="misconception"
                ),
                CompositionChoice(
                    teaching_block_id="b1", kind="callout", semantic_role="safety_guidance"
                ),
            ],
            tasks=[],
        )


def test_rejects_more_than_ten_ordinary_nodes_even_when_block_caps_hold() -> None:
    section = _section(*[_block(f"b{index}", "compare evidence") for index in range(6)])
    choices = [
        choice
        for index in range(6)
        for choice in (
            CompositionChoice(
                teaching_block_id=f"b{index}", kind="paragraph", semantic_role="explanation"
            ),
            CompositionChoice(
                teaching_block_id=f"b{index}", kind="table", semantic_role="comparison"
            ),
        )
    ]
    with pytest.raises(CompositionValidationError, match="exceeds 10 ordinary nodes"):
        validate_and_build_composition(section=section, choices=choices, tasks=[])


def test_rejects_anchor_removal_invention_and_reordering() -> None:
    section = _section(_block("b0", "explain"), _block("b1", "compare"))
    tasks = [_task("task-a", "b0"), _task("task-b", "b1")]
    valid = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
            ),
            CompositionChoice(teaching_block_id="b1", kind="table", semantic_role="comparison"),
        ],
        tasks=tasks,
    )

    for changed_items in (
        valid.items[:-1],
        valid.items + (valid.items[-1],),
        (valid.items[0], valid.items[3], valid.items[2], valid.items[1]),
    ):
        changed = SectionCompositionPlan(section_slot_id=valid.section_slot_id, items=changed_items)
        with pytest.raises(CompositionValidationError, match="TaskAnchors"):
            validate_composition_plan(plan=changed, section=section, tasks=tasks)


@pytest.mark.asyncio
async def test_one_targeted_repair_then_fail_closed() -> None:
    section = _section(_block("b0", "explain"))
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            return {"items": [_choice("b0", "figure", "summary")]}
        return {"items": [_choice("b0", "paragraph", "explanation")]}

    plan = await compose_section(section=section, tasks=[], provider=provider)

    assert len(calls) == 2
    assert calls[1]["repair_errors"]
    assert plan.items[0].kind == "paragraph"


@pytest.mark.asyncio
async def test_provider_failure_fails_closed_without_semantic_retry() -> None:
    section = _section(_block("b0", "explain"))
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider authentication failed")

    with pytest.raises(RuntimeError, match="authentication"):
        await compose_section(section=section, tasks=[], provider=provider)
    assert calls == 1
