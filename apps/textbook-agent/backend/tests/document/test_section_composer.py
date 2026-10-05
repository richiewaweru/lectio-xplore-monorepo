from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from core.prompts import effective_prompt_text
from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import (
    TeachingPlanBlock,
    TeachingPlanSection,
    VisualSpec,
)
from document.shared_lesson.composer import (
    COMPOSITION_ISSUE_CODES,
    SOFT_COMPOSITION_ISSUE_CODES,
    CompositionChoice,
    CompositionPolicy,
    CompositionValidationError,
    SectionCompositionDraft,
    SectionCompositionPlan,
    compose_section,
    validate_and_build_composition,
    validate_composition_plan,
)
from infra.authoring.model_policy import SECTION_COMPOSER, get_v3_slot


def _visual() -> VisualSpec:
    return VisualSpec(
        purpose="Show the particle arrangement",
        must_show=["particles"],
        labels_required=["Particle"],
    )


def _block(
    block_id: str, intent: str, brief: str | None = None, *, visual: bool = False
) -> TeachingPlanBlock:
    return TeachingPlanBlock(
        id=block_id,
        position=int(block_id.removeprefix("b")),
        intent=intent,
        brief=brief or intent,
        evidence=f"Learner can demonstrate {intent}.",
        visual=_visual() if visual else None,
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
        _block("b0", "explain the particle model", visual=True),
        _block("b1", "compare two models using evidence"),
        _block("b2", "warn about a misconception in this subsection"),
    )
    response = {
        "items": [
            _choice("b0", "paragraph", "explanation"),
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
    assert all(
        item.id.startswith("shared-figure-node-" if item.kind == "figure" else "shared-node-")
        for item in first.items
    )
    figure = first.items[1]
    assert (figure.kind, figure.teaching_block_id, figure.semantic_role) == (
        "figure",
        "b0",
        "visual_model",
    )


def test_code_inserts_adjacent_task_anchors_after_owning_block_nodes() -> None:
    section = _section(_block("b0", "orient", "explain"), _block("b1", "compare evidence"))
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
    plan = validate_and_build_composition(section=section, choices=choices, tasks=[])
    assert ("paragraph_run_exceeded", "choices[2]") in plan.warnings
    with pytest.raises(CompositionValidationError, match="unsuitable"):
        validate_and_build_composition(
            section=section,
            choices=[CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="summary")],
            tasks=[],
        )
    plan = validate_and_build_composition(
        section=_section(_block("b0", "explain the topic")),
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="table", semantic_role="comparison")
        ],
        tasks=[],
    )
    assert ("kind_missing_semantic_cue", "choices[0].kind") in plan.warnings


def test_task_anchor_breaks_paragraph_run_across_block_boundary() -> None:
    section = _section(
        _block("b0", "explain the model"),
        _block("b1", "summarize the idea"),
    )
    tasks = [_task("task-a", "b0")]
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="summary"),
        CompositionChoice(teaching_block_id="b1", kind="paragraph", semantic_role="explanation"),
    ]

    plan = validate_and_build_composition(section=section, choices=choices, tasks=tasks)

    assert [item.kind for item in plan.items if item.kind != "task_anchor"] == [
        "paragraph",
        "paragraph",
        "paragraph",
    ]


def test_three_consecutive_paragraphs_with_no_anchor_are_advisory() -> None:
    section = _section(
        _block("b0", "explain the model"),
        _block("b1", "compare the results"),
        _block("b2", "summarize the idea"),
    )
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b1", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b2", kind="paragraph", semantic_role="summary"),
    ]

    plan = validate_and_build_composition(section=section, choices=choices, tasks=[])
    assert ("paragraph_run_exceeded", "choices[2]") in plan.warnings


def test_soft_paragraph_run_is_auto_fixed_and_accepted_with_a_warning() -> None:
    section = _section(
        _block("b0", "explain why this happens"),
        _block("b1", "explain why that happens"),
        _block("b2", "explain why it happens"),
    )
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b1", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b2", kind="paragraph", semantic_role="summary"),
    ]

    plan = validate_and_build_composition(
        section=section, choices=choices, tasks=[], accept_soft_issues=True
    )

    assert [item.kind for item in plan.items] == ["paragraph", "paragraph", "paragraph"]
    assert ("paragraph_run_exceeded", "choices[2]") in plan.warnings
    assert all(code in SOFT_COMPOSITION_ISSUE_CODES for code, _path in plan.warnings)


def test_five_or_more_consecutive_paragraphs_remain_advisory() -> None:
    section = _section(
        *[_block(f"b{index}", "explain why it happens") for index in range(5)]
    )
    choices = [
        CompositionChoice(teaching_block_id=f"b{index}", kind="paragraph", semantic_role="explanation")
        for index in range(5)
    ]

    plan = validate_and_build_composition(
        section=section, choices=choices, tasks=[], accept_soft_issues=True
    )
    assert len([warning for warning in plan.warnings if warning[0] == "paragraph_run_exceeded"]) == 3


def test_node_ceiling_is_advisory_for_any_overage() -> None:
    section = _section(_block("b0", "compare the evidence"))
    one_over = [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="summary"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="bridge"),
    ]
    plan = validate_and_build_composition(
        section=section,
        choices=one_over,
        tasks=[],
        policy=CompositionPolicy(max_nodes_per_block=2),
        accept_soft_issues=True,
    )
    assert len(plan.items) == 3
    assert ("block_exceeds_node_limit", "blocks/b0") in plan.warnings

    two_over = one_over + [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="worked_example")
    ]
    plan = validate_and_build_composition(
        section=section,
        choices=two_over,
        tasks=[],
        policy=CompositionPolicy(max_nodes_per_block=2),
        accept_soft_issues=True,
    )
    assert ("block_exceeds_node_limit", "blocks/b0") in plan.warnings


def test_soft_cue_issues_convert_to_paragraph_with_a_warning() -> None:
    # "list" and "evidence" both share ground with paragraph (the role
    # "evidence" is valid for paragraphs too), so this is fixable -- unlike
    # a role such as "visual_model" that only "figure" accepts.
    section = _section(_block("b0", "explain why this happens"))
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="evidence")
    ]

    plan = validate_and_build_composition(
        section=section, choices=choices, tasks=[], accept_soft_issues=True
    )

    assert plan.items[0].kind == "list"
    assert plan.items[0].semantic_role == "evidence"
    assert ("kind_missing_semantic_cue", "choices[0].kind") in plan.warnings


def test_soft_cue_issue_is_advisory_even_when_form_is_specialized() -> None:
    section = _section(_block("b0", "explain why this happens"))
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="table", semantic_role="comparison")
    ]

    plan = validate_and_build_composition(
        section=section, choices=choices, tasks=[], accept_soft_issues=True
    )
    assert ("kind_missing_semantic_cue", "choices[0].kind") in plan.warnings


def test_extra_callouts_beyond_ceiling_convert_to_paragraph_with_a_warning() -> None:
    section = _section(
        _block("b0", "warning: avoid the common misconception"),
        _block("b1", "safety warning about this misconception"),
    )
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="callout", semantic_role="misconception"),
        CompositionChoice(teaching_block_id="b1", kind="callout", semantic_role="safety_guidance"),
    ]

    plan = validate_and_build_composition(
        section=section, choices=choices, tasks=[], accept_soft_issues=True
    )

    assert [item.kind for item in plan.items] == ["callout", "callout"]
    assert ("section_exceeds_callout_limit", "choices[1].kind") in plan.warnings


def test_hard_codes_still_fail_closed_even_with_soft_acceptance() -> None:
    section = _section(_block("b0", "explain"), _block("b1", "explain again"))
    choices = [
        CompositionChoice(teaching_block_id="b1", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
    ]

    with pytest.raises(CompositionValidationError) as excinfo:
        validate_and_build_composition(
            section=section, choices=choices, tasks=[], accept_soft_issues=True
        )
    assert _issue_codes(excinfo.value) == {"block_order_violation"}


@pytest.mark.asyncio
async def test_compose_section_accepts_shape_issue_without_repair() -> None:
    section = _section(_block("b0", "explain why this happens"))
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        # A shape issue is accepted on the first response and recorded as an
        # advisory warning; it must never trigger a correction call.
        calls.append(payload)
        return {"items": [_choice("b0", "list", "evidence")]}

    plan = await compose_section(section=section, tasks=[], provider=provider)

    assert len(calls) == 1
    assert not calls[0]["repair_errors"]
    assert plan.items[0].kind == "list"
    assert ("kind_missing_semantic_cue", "choices[0].kind") in plan.warnings


def test_list_accepts_explicit_sorting_but_rejects_uncued_unrelated_block() -> None:
    sorting_section = _section(
        _block("b0", "classify", "Sort two cases using the stated criterion.")
    )
    sorting_plan = validate_and_build_composition(
        section=sorting_section,
        choices=[CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="sequence")],
        tasks=[],
    )
    assert sorting_plan.items[0].kind == "list"

    unrelated_section = _section(_block("b0", "explain", "Describe why the principle matters."))
    plan = validate_and_build_composition(
        section=unrelated_section,
        choices=[CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="evidence")],
        tasks=[],
    )
    assert ("kind_missing_semantic_cue", "choices[0].kind") in plan.warnings


def test_rejects_block_node_ceiling_callout_ceiling_and_false_subsection() -> None:
    section = _section(_block("b0", "compare the evidence"))
    plan = validate_and_build_composition(
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
    assert ("block_exceeds_node_limit", "blocks/b0") in plan.warnings
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="heading", semantic_role="subsection"
            )
        ],
        tasks=[],
    )
    assert ("heading_missing_subsection_cue", "blocks/b0") in plan.warnings

    warning_section = _section(
        _block("b0", "warning: avoid the common misconception"),
        _block("b1", "safety warning about this misconception"),
    )
    plan = validate_and_build_composition(
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
    assert ("section_exceeds_callout_limit", "choices[1].kind") in plan.warnings


def test_misconception_role_does_not_authorize_callout_without_block_cue() -> None:
    prompt = " ".join(effective_prompt_text("section-composer").split())
    assert "A `misconception` semantic role does not by itself authorize a `callout`" in prompt
    assert "a paragraph may still use the `misconception` role" in prompt

    section = _section(
        _block(
            "b0",
            "explain why one result follows",
            "Show the reasoning behind the result.",
        )
    )
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="callout", semantic_role="misconception"
            )
        ],
        tasks=[],
    )
    assert ("callout_missing_cautionary_cue", "blocks/b0") in plan.warnings

    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="paragraph", semantic_role="misconception"
            )
        ],
        tasks=[],
    )
    assert [(item.kind, item.semantic_role) for item in plan.items] == [
        ("paragraph", "misconception")
    ]


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
    plan = validate_and_build_composition(section=section, choices=choices, tasks=[])
    assert ("section_exceeds_node_limit", f"section/{section.slot_id}") in plan.warnings


def test_rejects_anchor_removal_invention_and_reordering() -> None:
    section = _section(_block("b0", "orient", "explain"), _block("b1", "compare"))
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
    section = _section(_block("b0", "orient", "explain"))
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


def _issue_codes(exc: CompositionValidationError) -> set[str]:
    codes = {code for code, _path in exc.issues}
    assert codes <= COMPOSITION_ISSUE_CODES
    return codes


def test_duplicate_block_ids_reports_stable_issue_code() -> None:
    section = _section(_block("b0", "explain"), _block("b0", "explain again"))
    with pytest.raises(CompositionValidationError) as excinfo:
        validate_and_build_composition(section=section, choices=[], tasks=[])

    assert _issue_codes(excinfo.value) == {"duplicate_block_ids", "block_missing_ordinary_node"}
    assert ("duplicate_block_ids", "blocks") in excinfo.value.issues


def test_duplicate_and_unknown_task_ids_report_stable_issue_codes() -> None:
    section = _section(_block("b0", "explain"))
    duplicate_tasks = [_task("task-a", "b0"), _task("task-a", "b0")]
    with pytest.raises(CompositionValidationError) as duplicate_excinfo:
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
                )
            ],
            tasks=duplicate_tasks,
        )
    assert ("duplicate_task_ids", "tasks") in duplicate_excinfo.value.issues

    unknown_tasks = [_task("task-b", "missing-block")]
    with pytest.raises(CompositionValidationError) as unknown_excinfo:
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
                )
            ],
            tasks=unknown_tasks,
        )
    assert ("task_unknown_block", "tasks[0]") in unknown_excinfo.value.issues


def test_block_order_violation_reports_stable_issue_code() -> None:
    section = _section(_block("b0", "explain"), _block("b1", "compare evidence"))
    choices = [
        CompositionChoice(teaching_block_id="b1", kind="table", semantic_role="comparison"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
    ]
    with pytest.raises(CompositionValidationError) as excinfo:
        validate_and_build_composition(section=section, choices=choices, tasks=[])

    assert ("block_order_violation", "choices[1]") in excinfo.value.issues


def test_each_rejects_test_case_reports_expected_issue_code() -> None:
    section = _section(_block("b0", "compare the evidence"))

    with pytest.raises(CompositionValidationError) as no_node_excinfo:
        validate_and_build_composition(section=section, choices=[], tasks=[])
    assert "block_missing_ordinary_node" in _issue_codes(no_node_excinfo.value)
    assert ("block_missing_ordinary_node", "blocks/b0") in no_node_excinfo.value.issues

    with pytest.raises(CompositionValidationError) as unknown_block_excinfo:
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(
                    teaching_block_id="missing", kind="paragraph", semantic_role="explanation"
                )
            ],
            tasks=[],
        )
    assert _issue_codes(unknown_block_excinfo.value) >= {"item_unknown_block"}
    assert ("item_unknown_block", "choices[0]") in unknown_block_excinfo.value.issues

    paragraph_section = _section(_block("b0", "explain comparison evidence"))
    paragraph_plan = validate_and_build_composition(
        section=paragraph_section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
            ),
            CompositionChoice(
                teaching_block_id="b0", kind="paragraph", semantic_role="summary"
            ),
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="bridge"),
        ],
        tasks=[],
    )
    assert "paragraph_run_exceeded" in {code for code, _path in paragraph_plan.warnings}

    with pytest.raises(CompositionValidationError) as role_mismatch_excinfo:
        validate_and_build_composition(
            section=paragraph_section,
            choices=[
                CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="summary")
            ],
            tasks=[],
        )
    assert ("kind_role_mismatch", "choices[0].kind") in role_mismatch_excinfo.value.issues

    cueless_section = _section(_block("b0", "explain the topic"))
    cue_plan = validate_and_build_composition(
        section=cueless_section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="table", semantic_role="comparison")
        ],
        tasks=[],
    )
    assert ("kind_missing_semantic_cue", "choices[0].kind") in cue_plan.warnings

    heading_section = _section(_block("b0", "compare the evidence"))
    heading_plan = validate_and_build_composition(
        section=heading_section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="heading", semantic_role="subsection"
            )
        ],
        tasks=[],
    )
    assert ("heading_missing_subsection_cue", "blocks/b0") in heading_plan.warnings

    callout_section = _section(
        _block("b0", "explain why one result follows", "Show the reasoning behind the result.")
    )
    callout_plan = validate_and_build_composition(
        section=callout_section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="callout", semantic_role="misconception"
            )
        ],
        tasks=[],
    )
    assert ("callout_missing_cautionary_cue", "blocks/b0") in callout_plan.warnings

    ceiling_section = _section(_block("b0", "compare the evidence"))
    node_ceiling_plan = validate_and_build_composition(
        section=ceiling_section,
        choices=[
            CompositionChoice(
                teaching_block_id="b0", kind="paragraph", semantic_role="explanation"
            ),
            CompositionChoice(teaching_block_id="b0", kind="table", semantic_role="comparison"),
            CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="evidence"),
        ],
        tasks=[],
    )
    assert ("block_exceeds_node_limit", "blocks/b0") in node_ceiling_plan.warnings

    section_ceiling_section = _section(
        *[_block(f"b{index}", "compare evidence") for index in range(6)]
    )
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
    section_ceiling_plan = validate_and_build_composition(
        section=section_ceiling_section, choices=choices, tasks=[]
    )
    assert (
        "section_exceeds_node_limit",
        f"section/{section_ceiling_section.slot_id}",
    ) in section_ceiling_plan.warnings

    callout_ceiling_section = _section(
        _block("b0", "warning: avoid the common misconception"),
        _block("b1", "safety warning about this misconception"),
    )
    callout_ceiling_plan = validate_and_build_composition(
        section=callout_ceiling_section,
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
    assert (
        "section_exceeds_callout_limit",
        f"section/{callout_ceiling_section.slot_id}",
    ) not in callout_ceiling_plan.warnings
    assert ("section_exceeds_callout_limit", "choices[1].kind") in callout_ceiling_plan.warnings


def test_anchor_mismatch_and_plan_divergence_report_stable_issue_codes() -> None:
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

    dropped = SectionCompositionPlan(section_slot_id=valid.section_slot_id, items=valid.items[:-1])
    with pytest.raises(CompositionValidationError) as anchor_excinfo:
        validate_composition_plan(plan=dropped, section=section, tasks=tasks)
    assert anchor_excinfo.value.issues == (("task_anchor_mismatch", f"section/{section.slot_id}"),)

    # Tamper only the stable node id of an ordinary item -- the block/kind/role
    # choices extracted from the plan stay identical (so anchors and recomputed
    # ordinary items still line up), but the recomputed deterministic ID no
    # longer matches, which is the "plan differs" branch rather than the
    # TaskAnchor-specific branch above.
    tampered_first = valid.items[0].model_copy(update={"id": "tampered-node-id"})
    tampered = SectionCompositionPlan(
        section_slot_id=valid.section_slot_id,
        items=(tampered_first, *valid.items[1:]),
    )
    with pytest.raises(CompositionValidationError) as divergence_excinfo:
        validate_composition_plan(plan=tampered, section=section, tasks=tasks)
    assert divergence_excinfo.value.issues == (
        ("plan_diverges_from_deterministic", f"section/{section.slot_id}"),
    )


@pytest.mark.asyncio
async def test_provider_schema_invalid_draft_reports_stable_issue_code() -> None:
    section = _section(_block("b0", "explain"))

    async def malformed_provider(_payload: dict[str, Any]) -> Any:
        return {"items": []}

    with pytest.raises(CompositionValidationError) as excinfo:
        await compose_section(section=section, tasks=[], provider=malformed_provider)

    # Empty items violates the closed draft schema (min_length=1), which is
    # reported through the fixed schema-invalid code, never as free text.
    assert excinfo.value.issues == (("provider_draft_schema_invalid", "items"),)


def test_empty_warnings_are_omitted_so_pre_warning_outputs_hash_identically():
    from document.shared_lesson.composer import SectionCompositionPlan

    legacy = {
        "section_slot_id": "s1",
        "items": [
            {
                "id": "n1",
                "kind": "paragraph",
                "teaching_block_id": "b1",
                "semantic_role": "explanation",
            }
        ],
    }
    plan = SectionCompositionPlan.model_validate(legacy)
    assert plan.model_dump(mode="json") == {
        "section_slot_id": "s1",
        "items": [{**legacy["items"][0], "task_spec_id": None}],
    }
    warned = plan.model_copy(update={"warnings": (("paragraph_run_exceeded", "choices[2]"),)})
    assert warned.model_dump(mode="json")["warnings"] == [["paragraph_run_exceeded", "choices[2]"]]


@pytest.mark.asyncio
async def test_composer_output_containing_a_figure_is_rejected_and_repaired() -> None:
    section = _section(_block("b0", "explain the particle model", visual=True))
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            return {
                "items": [
                    _choice("b0", "paragraph", "explanation"),
                    _choice("b0", "figure", "visual_model"),
                ]
            }
        return {"items": [_choice("b0", "paragraph", "explanation")]}

    plan = await compose_section(section=section, tasks=[], provider=provider)

    assert len(calls) == 2
    assert any("figure" in error for error in calls[1]["repair_errors"])
    # The figure still exists -- placed by code from the plan, not the composer.
    assert [item.kind for item in plan.items] == ["paragraph", "figure"]


@pytest.mark.asyncio
async def test_persistent_composer_figure_fails_closed() -> None:
    section = _section(_block("b0", "explain the particle model", visual=True))
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        return {"items": [_choice("b0", "figure", "visual_model")]}

    with pytest.raises(CompositionValidationError) as excinfo:
        await compose_section(section=section, tasks=[], provider=provider)
    assert calls == 2
    assert _issue_codes(excinfo.value) == {"provider_draft_schema_invalid"}

    with pytest.raises(ValidationError):
        CompositionChoice.model_validate(_choice("b0", "figure", "visual_model"))


def test_code_places_exactly_one_figure_per_visual_block_before_task_anchors() -> None:
    section = _section(
        _block("b0", "explain the particle model", visual=True),
        _block("b1", "compare two models using evidence"),
        _block("b2", "summarize the idea", visual=True),
    )
    tasks = [_task("task-a", "b0"), _task("task-c", "b2")]
    choices = [
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
        CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="summary"),
        CompositionChoice(teaching_block_id="b1", kind="table", semantic_role="comparison"),
        CompositionChoice(teaching_block_id="b2", kind="paragraph", semantic_role="summary"),
    ]

    plan = validate_and_build_composition(
        section=section, choices=choices, tasks=tasks, policy=CompositionPolicy(max_nodes_per_block=2)
    )

    assert [(item.kind, item.teaching_block_id) for item in plan.items] == [
        ("paragraph", "b0"),
        ("paragraph", "b0"),
        ("figure", "b0"),  # does not count toward max_nodes_per_block=2
        ("task_anchor", "b0"),
        ("table", "b1"),
        ("paragraph", "b2"),
        ("figure", "b2"),
        ("task_anchor", "b2"),
    ]
    assert sum(item.kind == "figure" for item in plan.items) == 2
    validate_composition_plan(plan=plan, section=section, tasks=tasks)

    again = validate_and_build_composition(
        section=section, choices=choices, tasks=tasks, policy=CompositionPolicy()
    )
    assert again.items == plan.items  # figure ids are stable

    without_figure = SectionCompositionPlan(
        section_slot_id=plan.section_slot_id,
        items=tuple(item for item in plan.items if item.id != plan.items[2].id),
    )
    with pytest.raises(CompositionValidationError):
        validate_composition_plan(plan=without_figure, section=section, tasks=tasks)


def test_no_visual_blocks_means_no_figure_items() -> None:
    section = _section(
        _block("b0", "show the diagram of the particle model figure"),
        _block("b1", "explain the visual flow"),
    )
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
            CompositionChoice(teaching_block_id="b1", kind="paragraph", semantic_role="summary"),
        ],
        tasks=[],
    )
    assert all(item.kind != "figure" for item in plan.items)


# --- code-reserved key-idea slot (doc 36 G3) ---------------------------------


def _explain_section(*extra: TeachingPlanBlock) -> TeachingPlanSection:
    return _section(_block("b0", "explain-cause", "How the process works"), *extra)


def test_explaining_section_detected_from_block_intent() -> None:
    from document.shared_lesson.composer import is_explaining_section

    assert is_explaining_section(_explain_section())
    assert is_explaining_section(_section(_block("b0", "orient"), _block("b1", "trace-flow")))
    assert not is_explaining_section(_section(_block("b0", "orient", "explain")))
    assert not is_explaining_section(_section(_block("b0", "check-understanding")))


def test_explaining_section_gets_key_idea_slot_first_without_callout_warning() -> None:
    from document.shared_lesson.composer import KEY_IDEA_SLOT_PREFIX

    section = _explain_section(_block("b1", "compare evidence", visual=True))
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
            CompositionChoice(teaching_block_id="b1", kind="table", semantic_role="comparison"),
        ],
        tasks=[],
    )

    first = plan.items[0]
    assert (first.kind, first.semantic_role, first.teaching_block_id) == (
        "callout",
        "explanation",
        "b0",
    )
    assert first.id.startswith(KEY_IDEA_SLOT_PREFIX)
    assert [item.kind for item in plan.items] == ["callout", "paragraph", "table", "figure"]
    assert sum(1 for item in plan.items if item.kind == "callout") == 1
    assert not any(code == "section_exceeds_callout_limit" for code, _ in plan.warnings)
    # The slot is code-owned and survives verification.
    validate_composition_plan(plan=plan, section=section, tasks=[])


def test_slot_does_not_warn_when_provider_also_chose_a_misconception_callout() -> None:
    section = _explain_section(_block("b1", "diagnose-misconception", "a common mistake"))
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
            CompositionChoice(teaching_block_id="b1", kind="callout", semantic_role="misconception"),
        ],
        tasks=[],
    )

    assert [item.kind for item in plan.items] == ["callout", "paragraph", "callout"]
    assert [item.semantic_role for item in plan.items] == ["explanation", "explanation", "misconception"]
    assert plan.warnings == ()
    validate_composition_plan(plan=plan, section=section, tasks=[])


def test_non_explaining_section_is_unchanged() -> None:
    section = _section(_block("b0", "orient", "explain"), _block("b1", "check-understanding"))
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
            CompositionChoice(teaching_block_id="b1", kind="paragraph", semantic_role="evidence"),
        ],
        tasks=[],
    )

    assert [item.kind for item in plan.items] == ["paragraph", "paragraph"]
    validate_composition_plan(plan=plan, section=section, tasks=[])


def test_existing_explanation_callout_moves_to_front_without_duplicating() -> None:
    section = _explain_section(_block("b1", "explain key idea"))
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation"),
            CompositionChoice(teaching_block_id="b1", kind="callout", semantic_role="explanation"),
        ],
        tasks=[],
    )

    kinds = [(item.kind, item.teaching_block_id) for item in plan.items]
    assert kinds[0] == ("callout", "b0")
    assert sum(1 for kind, _ in kinds if kind == "callout") == 1
    # b1 would have been left empty, so it keeps an ordinary explanation node.
    assert ("paragraph", "b1") in kinds
    validate_composition_plan(plan=plan, section=section, tasks=[])


def test_stored_plan_without_slot_still_verifies() -> None:
    section = _explain_section()
    legacy = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation")
        ],
        tasks=[],
        reserve_key_idea=False,
    )

    assert [item.kind for item in legacy.items] == ["paragraph"]
    validate_composition_plan(plan=legacy, section=section, tasks=[])


def test_removing_the_slot_from_a_new_plan_is_rejected() -> None:
    section = _explain_section()
    plan = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(teaching_block_id="b0", kind="paragraph", semantic_role="explanation")
        ],
        tasks=[],
    )
    forged = plan.model_copy(update={"items": plan.items[1:]})

    # A plan without a slot is a legacy plan and is accepted unchanged; a plan
    # whose slot id was tampered with diverges from the deterministic build.
    validate_composition_plan(plan=forged, section=section, tasks=[])
    tampered_slot = plan.items[0].model_copy(update={"id": plan.items[0].id[:-1] + "x"})
    with pytest.raises(CompositionValidationError):
        validate_composition_plan(
            plan=plan.model_copy(update={"items": (tampered_slot, *plan.items[1:])}),
            section=section,
            tasks=[],
        )
