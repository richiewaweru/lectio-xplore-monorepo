from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson.composer import (
    COMPOSITION_ISSUE_CODES,
    CompositionChoice,
    CompositionValidationError,
    SectionCompositionDraft,
    SectionCompositionPlan,
    compose_section,
    validate_and_build_composition,
    validate_composition_plan,
)
from infra.authoring.model_policy import SECTION_COMPOSER, get_v3_slot
from core.prompts import effective_prompt_text


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
    with pytest.raises(CompositionValidationError, match="suitable semantic cues"):
        validate_and_build_composition(
            section=unrelated_section,
            choices=[CompositionChoice(teaching_block_id="b0", kind="list", semantic_role="evidence")],
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
    with pytest.raises(CompositionValidationError, match="lacks cautionary semantics"):
        validate_and_build_composition(
            section=section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="callout", semantic_role="misconception"
                )
            ],
            tasks=[],
        )

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
    with pytest.raises(CompositionValidationError) as paragraph_excinfo:
        validate_and_build_composition(
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
    assert "paragraph_run_exceeded" in _issue_codes(paragraph_excinfo.value)

    with pytest.raises(CompositionValidationError) as role_mismatch_excinfo:
        validate_and_build_composition(
            section=paragraph_section,
            choices=[
                CompositionChoice(teaching_block_id="b0", kind="figure", semantic_role="summary")
            ],
            tasks=[],
        )
    assert ("kind_role_mismatch", "choices[0].kind") in role_mismatch_excinfo.value.issues

    cueless_section = _section(_block("b0", "explain the evidence"))
    with pytest.raises(CompositionValidationError) as cue_excinfo:
        validate_and_build_composition(
            section=cueless_section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="figure", semantic_role="visual_model"
                )
            ],
            tasks=[],
        )
    assert ("kind_missing_semantic_cue", "choices[0].kind") in cue_excinfo.value.issues

    heading_section = _section(_block("b0", "compare the evidence"))
    with pytest.raises(CompositionValidationError) as heading_excinfo:
        validate_and_build_composition(
            section=heading_section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="heading", semantic_role="subsection"
                )
            ],
            tasks=[],
        )
    assert ("heading_missing_subsection_cue", "blocks/b0") in heading_excinfo.value.issues

    callout_section = _section(
        _block("b0", "explain why one result follows", "Show the reasoning behind the result.")
    )
    with pytest.raises(CompositionValidationError) as callout_excinfo:
        validate_and_build_composition(
            section=callout_section,
            choices=[
                CompositionChoice(
                    teaching_block_id="b0", kind="callout", semantic_role="misconception"
                )
            ],
            tasks=[],
        )
    assert ("callout_missing_cautionary_cue", "blocks/b0") in callout_excinfo.value.issues

    ceiling_section = _section(_block("b0", "compare the evidence"))
    with pytest.raises(CompositionValidationError) as node_ceiling_excinfo:
        validate_and_build_composition(
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
    assert ("block_exceeds_node_limit", "blocks/b0") in node_ceiling_excinfo.value.issues

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
    with pytest.raises(CompositionValidationError) as section_ceiling_excinfo:
        validate_and_build_composition(section=section_ceiling_section, choices=choices, tasks=[])
    assert (
        "section_exceeds_node_limit",
        f"section/{section_ceiling_section.slot_id}",
    ) in section_ceiling_excinfo.value.issues

    callout_ceiling_section = _section(
        _block("b0", "warning: avoid the common misconception"),
        _block("b1", "safety warning about this misconception"),
    )
    with pytest.raises(CompositionValidationError) as callout_ceiling_excinfo:
        validate_and_build_composition(
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
    ) in callout_ceiling_excinfo.value.issues


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
