from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection, VisualSpec
from document.shared_lesson.composer import (
    CompositionChoice,
    validate_and_build_composition,
)
from document.shared_lesson.writer import (
    SECTION_WRITE_ISSUE_CODES,
    SectionSource,
    SectionTaskSummary,
    SectionWriterRequest,
    SectionWriteValidationError,
    validate_and_build_section,
    validate_draft_nodes,
    write_section,
)
from infra.authoring.model_policy import SHARED_SECTION_WRITER, get_v3_slot


def _block(
    block_id: str,
    position: int,
    intent: str,
    brief: str | None = None,
    visual: VisualSpec | None = None,
) -> TeachingPlanBlock:
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief or intent,
        evidence=f"Learners can demonstrate {intent}.",
        visual=visual,
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
            _block(
                "block-intro",
                0,
                "introduce the water model with a diagram",
                visual=VisualSpec(
                    purpose="Show particle motion in water",
                    must_show=["Water particles"],
                    labels_required=["Particle"],
                ),
            ),
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


def _numeric_task() -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-solve-x",
        teaching_block_id="block-solve",
        mode="formative",
        action="enter-number",
        purpose="Check whether the learner can solve for x",
        prompt="Solve 4x = 36 for x.",
        difficulty="guided",
        expected_evidence="The learner solves 4x = 36 to get x = 9",
        response={"type": "number", "answer_lines": 1},
        evaluation={"type": "exact_match", "correct_value": 9},
    )


def _numeric_request(sources: tuple[SectionSource, ...] = ()) -> SectionWriterRequest:
    section = TeachingPlanSection(
        slot_id="section-solve",
        display_title="Solving linear equations",
        entry_state=["Learner can isolate a variable"],
        must_establish=["Learner solves a one-step linear equation"],
        avoid_repeating=["Do not reteach variable notation"],
        bridge_from_previous=None,
        exit_state=["Learner solves 4x = 36 independently"],
        specific_purpose="Guide the learner through solving 4x = 36",
        blocks=[
            _block("block-intro", 0, "explain how to isolate x in an equation"),
            _block("block-solve", 1, "guide the learner to solve 4x = 36 for x"),
        ],
    )
    task = _numeric_task()
    composition = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="block-intro", kind="paragraph", semantic_role="worked_example"
            ),
            CompositionChoice(
                teaching_block_id="block-solve", kind="paragraph", semantic_role="explanation"
            ),
        ],
        tasks=[task],
    )
    return SectionWriterRequest(
        section=section,
        composition_plan=composition,
        sources=sources,
        task_summaries=(
            SectionTaskSummary(
                task_spec_id=task.id,
                teaching_block_id=task.teaching_block_id,
                action=task.action,
                purpose=task.purpose,
                prompt=task.prompt,
                expected_evidence=task.expected_evidence,
                evaluation=task.evaluation,
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
        del payload["accessibility"]  # the writer never authors alt text
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
    elif item.kind == "equation":
        payload["display"] = {
            "label": "Energy balance",
            "inputs": ["light energy", "water", "carbon dioxide", "chlorophyll", "temperature"],
            "condition": "in a leaf",
            "outputs": ["glucose", "oxygen", "stored chemical energy", "biomass"],
        }
    elif item.kind == "quote":
        payload["display"] = {
            "text": "Plants transform light energy into stored chemical energy.",
            "attribution": "Approved science source",
        }
    elif item.kind == "compare":
        payload["display"] = {
            "items": [
                {"title": "Light reactions", "body": "Capture light energy."},
                {"title": "Carbon fixation", "body": "Builds sugar molecules."},
                {"title": "Cellular respiration", "body": "Releases stored energy."},
                {"title": "Photorespiration", "body": "Competes with carbon fixation."},
            ]
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


def test_shape_advisories_preserve_all_equation_terms_and_comparison_cards() -> None:
    section = TeachingPlanSection(
        slot_id="section-energy",
        display_title="Energy pathways",
        entry_state=["Learner names plant needs"],
        must_establish=["Learner compares energy pathways"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["Learner explains the comparison"],
        specific_purpose="Compare energy pathways and show their terms",
        blocks=[
            _block("block-equation", 0, "explain the formula inputs and outputs"),
            _block("block-compare", 1, "compare the alternative pathways"),
        ],
    )
    composition = validate_and_build_composition(
        section=section,
        choices=[
            CompositionChoice(
                teaching_block_id="block-equation", kind="equation", semantic_role="explanation"
            ),
            CompositionChoice(
                teaching_block_id="block-compare", kind="compare", semantic_role="comparison"
            ),
        ],
        tasks=[],
    )
    request = SectionWriterRequest(
        section=section,
        composition_plan=composition,
        sources=(
            SectionSource(
                id="source-photosynthesis",
                kind="approved_fact",
                text="Plants use light energy to make glucose and oxygen from water and carbon dioxide.",
            ),
        ),
        task_summaries=(),
    )
    result = validate_and_build_section(request=request, draft=_draft(request))
    equation = result.nodes[0]
    compare = result.nodes[1]
    assert equation.display.inputs[-1] == "temperature"
    assert equation.display.outputs[-1] == "biomass"
    assert compare.display.items[-1].title == "Photorespiration"
    assert ("length_over_target", "nodes[0].inputs/5/4") in result.warnings
    assert ("length_over_target", "nodes[0].outputs/4/3") in result.warnings
    assert ("length_over_target", "nodes[1].items/4/3") in result.warnings


def test_writer_uses_standard_slot_with_deepseek_thinking_enabled() -> None:
    from infra.authoring.model_policy import V3_NODE_REASONING

    assert get_v3_slot(SHARED_SECTION_WRITER).value == "standard"
    assert V3_NODE_REASONING[SHARED_SECTION_WRITER] == "medium"


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
    "attack,expected_code",
    [
        ("missing", "node_count_mismatch"),
        ("extra", "node_count_mismatch"),
        ("reordered", "node_id_mismatch"),
        ("retyped", "node_kind_mismatch"),
        ("wrong_owner", "node_block_mismatch"),
        ("anchor", "writer_draft_schema_invalid"),
    ],
)
def test_rejects_composition_shape_attacks(attack: str, expected_code: str) -> None:
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

    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    codes = {code for code, _path in excinfo.value.issues}
    assert codes == {expected_code}


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


def test_writer_supplied_figure_asset_id_is_dropped() -> None:
    request = _request()
    draft = _draft(request)
    figure_draft = next(node for node in draft["nodes"] if node["kind"] == "figure")
    figure_draft["display"]["asset_id"] = "fig-2"
    result = validate_and_build_section(request=request, draft=draft)
    figure = next(node for node in result.nodes if node.kind == "figure")
    assert figure.display.asset_id is None
    assert figure.accessibility.alt_text == ""


def test_figure_node_is_code_placed_with_pending_alt_and_writer_cannot_author_alt() -> None:
    request = _request()
    figure_items = [item for item in request.composition_plan.items if item.kind == "figure"]
    assert [(item.teaching_block_id, item.semantic_role) for item in figure_items] == [
        ("block-intro", "visual_model")
    ]
    result = validate_and_build_section(request=request, draft=_draft(request))
    figure = next(node for node in result.nodes if node.kind == "figure")
    assert figure.display.caption == "Particle motion after heating"
    assert figure.accessibility.alt_text == ""  # pending until media binds

    with_alt = _draft(request)
    with_alt["nodes"][1]["accessibility"] = {"alt_text": "Writer-authored alt"}
    with pytest.raises(SectionWriteValidationError):
        validate_and_build_section(request=request, draft=with_alt)

    blank_caption = _draft(request)
    blank_caption["nodes"][1]["display"]["caption"] = "  "
    with pytest.raises(SectionWriteValidationError, match="blank"):
        validate_and_build_section(request=request, draft=blank_caption)


def test_writer_payload_carries_each_blocks_visual_spec() -> None:
    from document.shared_lesson.writer import _request_payload

    request = _request()
    payload = _request_payload(request, repair_scope="", errors=())
    blocks = {block["id"]: block for block in payload["section_contract"]["blocks"]}
    assert blocks["block-intro"]["visual"] == {
        "mode": "diagram",
        "purpose": "Show particle motion in water",
        "must_show": ["Water particles"],
        "labels_required": ["Particle"],
        "must_not_show": [],
        "required": True,
    }
    assert blocks["block-compare"]["visual"] is None


def test_rejects_malformed_table_content() -> None:
    request = _request()

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


def test_rejects_stated_task_answer_result() -> None:
    request = _numeric_request()
    draft = _draft(request)
    draft["nodes"][1]["display"]["text"] = "Divide both sides by 4 to see that x = 9."
    with pytest.raises(SectionWriteValidationError, match="states the result of an anchored task"):
        validate_and_build_section(request=request, draft=draft)


def test_allows_benign_mention_of_task_operand_without_stating_result() -> None:
    request = _numeric_request()
    draft = _draft(request)
    draft["nodes"][1]["display"]["text"] = "This step revisits the equation 4x = 36 from earlier."
    result = validate_and_build_section(request=request, draft=draft)
    assert result.nodes[1].kind == "paragraph"


def test_allows_worked_example_using_different_values_than_the_anchored_task() -> None:
    sources = (
        SectionSource(
            id="source-related-equation",
            kind="approved_fact",
            text="A related equation, 5m = 20, has solution m = 4.",
        ),
    )
    request = _numeric_request(sources=sources)
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "For example, 5m = 20, so m = 4."
    result = validate_and_build_section(request=request, draft=draft)
    assert result.nodes[0].kind == "paragraph"


@pytest.mark.asyncio
async def test_stated_task_answer_triggers_bounded_repair() -> None:
    request = _numeric_request()
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        draft = _draft(request)
        if len(calls) == 1:
            draft["nodes"][1]["display"]["text"] = "Divide both sides by 4 to see that x = 9."
        else:
            draft["nodes"][1]["display"]["text"] = (
                "Divide both sides of the equation by the same coefficient to isolate x."
            )
        return draft

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 2
    assert calls[0]["repair"] is None
    assert calls[1]["repair"] is not None
    assert "states the result of an anchored task" in calls[1]["repair"]["issues"][0]
    assert result.nodes[-1].kind == "task_anchor"


def test_prompt_states_answer_leakage_and_misconception_rules() -> None:
    from core.prompts import effective_prompt_text

    prompt = effective_prompt_text("shared-section-writer")
    lowered = prompt.lower()
    assert "resolve every misconception" in lowered
    assert "never solve an anchored task" in lowered
    assert "hidden_answer_context_do_not_reveal" in prompt
    assert "stay factually accurate" in lowered


def test_payload_hides_expected_evidence_and_evaluation_from_ordinary_context() -> None:
    from document.shared_lesson.writer import _request_payload

    request = _numeric_request()
    payload = _request_payload(request, repair_scope="initial", errors=())

    for summary in payload["task_summaries"]:
        assert "expected_evidence" not in summary
        assert "evaluation" not in summary


# --- Diagnostic issue code/path coverage -----------------------------------
#
# `SectionWriteValidationError.issues` feeds `_record_execution_failure`'s
# persisted diagnostic (see runtime.py / test_shared_lesson_runtime.py). Each
# raise site must attach a closed-vocabulary code and a structural-only path
# (node index/kind/field -- never provider output or learner text), the same
# discipline the composer already applies to `CompositionValidationError`.


def _issue_codes(error: SectionWriteValidationError) -> set[str]:
    return {code for code, _path in error.issues}


def test_schema_invalid_draft_yields_writer_draft_schema_invalid_code() -> None:
    request = _request()
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft={"nodes": "not-a-list"})
    assert _issue_codes(excinfo.value) == {"writer_draft_schema_invalid"}
    assert excinfo.value.issues == (("writer_draft_schema_invalid", ""),)


def test_table_shape_errors_yield_table_issue_codes() -> None:
    request = _request()

    empty_table = _draft(request)
    empty_table["nodes"][2]["display"]["headers"] = []
    empty_table["nodes"][2]["display"]["rows"] = []
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=empty_table)
    assert _issue_codes(excinfo.value) == {"table_missing_headers_or_rows"}
    (code, path) = excinfo.value.issues[0]
    assert path == "nodes[2].table"

    mismatched_rows = _draft(request)
    mismatched_rows["nodes"][2]["display"]["rows"] = [["Only one cell"]]
    with pytest.raises(SectionWriteValidationError, match="header width") as excinfo:
        validate_and_build_section(request=request, draft=mismatched_rows)
    assert _issue_codes(excinfo.value) == {"table_row_width_mismatch"}
    assert excinfo.value.issues[0][1] == "nodes[2].table.rows"


def test_blank_learner_text_yields_blank_text_code() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "   "
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"blank_text"}
    assert excinfo.value.issues[0][1] == "nodes[0].text"


def test_planning_text_leak_yields_metadata_leaked_code() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "The must_establish field says particles move faster."
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"metadata_leaked"}
    assert excinfo.value.issues[0][1] == "nodes[0].text"


def test_placeholder_text_leak_yields_metadata_leaked_code() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "TODO: explain the model."
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"metadata_leaked"}


def test_unsupported_number_yields_unsupported_number_code() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "The temperature reaches 900 degrees."
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"unsupported_number"}
    assert excinfo.value.issues[0][1] == "nodes[0].text"
    # The leaked numeric value itself must never appear in the sanitized path.
    assert "900" not in excinfo.value.issues[0][1]


def test_internal_identifier_leak_yields_internal_id_leaked_code() -> None:
    request = _request()
    identifier = request.composition_plan.items[0].id
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = f"Use {identifier} to answer."
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"internal_id_leaked"}
    # The leaked identifier itself must never appear in the sanitized path.
    assert identifier not in excinfo.value.issues[0][1]


def test_task_answer_leak_yields_task_answer_leaked_code() -> None:
    request = _numeric_request()
    draft = _draft(request)
    draft["nodes"][1]["display"]["text"] = "Divide both sides by 4 to see that x = 9."
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"task_answer_leaked"}
    (code, path) = excinfo.value.issues[0]
    assert path == "nodes[1].text"
    # The leaked answer value itself must never appear in the sanitized path.
    assert "9" not in path


# --- SOFT/HARD writer issue acceptance (mirrors composer's SOFT pattern) --


def test_accept_soft_issues_records_task_answer_leaked_as_warning() -> None:
    request = _numeric_request()
    draft = _draft(request)
    draft["nodes"][1]["display"]["text"] = "Divide both sides by 4 to see that x = 9."

    result = validate_and_build_section(request=request, draft=draft, accept_soft_issues=True)

    assert result.warnings == (
        ("task_answer_leaked", "nodes[1].text"),
        ("unsupported_number", "nodes[1].text"),
        ("shape_missing", "section/key_idea"),
    )
    assert result.nodes[1].display.text == "Divide both sides by 4 to see that x = 9."


def test_accept_soft_issues_records_unsupported_number_as_warning() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "The temperature reaches 900 degrees."

    result = validate_and_build_section(request=request, draft=draft, accept_soft_issues=True)

    assert ("unsupported_number", "nodes[0].text") in result.warnings
    assert "900" not in next(path for code, path in result.warnings if code == "unsupported_number")


def test_inline_formula_notation_does_not_create_unsupported_numeric_fact() -> None:
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "Plants use CO~2~ and m^2^ notation in this explanation."

    result = validate_and_build_section(request=request, draft=draft)

    assert ("unsupported_number", "nodes[0].text") not in result.warnings


def test_accept_soft_issues_still_raises_hard_issues() -> None:
    """A HARD code (metadata_leaked) fails closed even with accept_soft_issues=True."""
    request = _request()
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "The must_establish field says particles move faster."

    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft, accept_soft_issues=True)
    assert _issue_codes(excinfo.value) == {"metadata_leaked"}


def test_no_warnings_recorded_when_no_soft_issues_present() -> None:
    request = _request()
    draft = _draft(request)

    result = validate_and_build_section(request=request, draft=draft, accept_soft_issues=True)

    assert result.warnings == (("shape_missing", "section/key_idea"),)


@pytest.mark.asyncio
async def test_write_section_accepts_soft_only_issue_on_final_attempt_with_event() -> None:
    request = _numeric_request()
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        draft = _draft(request)
        # Every attempt still leaks the task answer; the writer never resolves it.
        draft["nodes"][1]["display"]["text"] = "Divide both sides by 4 to see that x = 9."
        return draft

    result = await write_section(request=request, provider=provider)
    assert len(calls) == 3
    assert ("task_answer_leaked", "nodes[1].text") in result.warnings
    assert ("unsupported_number", "nodes[1].text") in result.warnings


@pytest.mark.asyncio
async def test_write_section_still_fails_when_hard_issue_survives_final_attempt() -> None:
    """A HARD issue (metadata_leaked) surviving all bounded repairs still fails
    the WorkItem, even on the final attempt."""
    request = _request()
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        draft = _draft(request)
        draft["nodes"][0]["display"]["text"] = "The must_establish field says particles move faster."
        return draft

    with pytest.raises(SectionWriteValidationError) as excinfo:
        await write_section(request=request, provider=provider)
    assert calls == 3
    assert _issue_codes(excinfo.value) == {"metadata_leaked"}


def test_soft_section_write_issue_codes_are_a_subset_of_the_closed_vocabulary() -> None:
    from document.shared_lesson.writer import SOFT_SECTION_WRITE_ISSUE_CODES

    assert SOFT_SECTION_WRITE_ISSUE_CODES == frozenset({"task_answer_leaked", "unsupported_number"})
    assert SOFT_SECTION_WRITE_ISSUE_CODES <= SECTION_WRITE_ISSUE_CODES


def test_section_write_result_rejects_non_soft_warning_code() -> None:
    from document.shared_lesson.writer import SectionWriteResult

    request = _request()
    draft = _draft(request)
    result = validate_and_build_section(request=request, draft=draft)
    with pytest.raises(ValidationError, match="not a soft issue code"):
        SectionWriteResult(
            section_slot_id=result.section_slot_id,
            title=result.title,
            nodes=result.nodes,
            warnings=(("metadata_leaked", "nodes[0].text"),),
        )


def test_node_shape_mismatch_yields_node_shape_mismatch_code(monkeypatch) -> None:
    from pydantic import TypeAdapter

    import document.shared_lesson.writer as writer_module

    request = _request()
    draft = _draft(request)

    def _always_invalid(_payload):
        # Reuse a real ValidationError shape by validating an impossible type.
        return TypeAdapter(int).validate_python("not-an-int")

    monkeypatch.setattr(
        writer_module.shared_lesson_node_adapter, "validate_python", _always_invalid
    )
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert _issue_codes(excinfo.value) == {"node_shape_mismatch"}
    assert excinfo.value.issues[0][1] == "nodes[0]"


def test_task_anchor_ownership_mismatch_yields_its_code() -> None:
    request = _request()
    draft = _draft(request)
    result = validate_and_build_section(request=request, draft=draft)
    assert result.nodes[-1].kind == "task_anchor"

    # The writer request's own validators already guarantee task summaries
    # match their TaskAnchor's teaching_block_id in the ordinary case, so this
    # defensive check can only be exercised by bypassing that invariant
    # directly (the request model is frozen).
    mutated_task = request.task_summaries[0].model_copy(
        update={"teaching_block_id": "block-intro"}
    )
    object.__setattr__(request, "task_summaries", (mutated_task,))
    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=_draft(request))
    assert _issue_codes(excinfo.value) == {"task_anchor_ownership_mismatch"}


def test_diagnostic_issue_codes_are_closed_vocabulary() -> None:
    # Every code this module can raise must be declared, mirroring the
    # composer's COMPOSITION_ISSUE_CODES closed-vocabulary discipline.
    expected = {
        "writer_draft_schema_invalid",
        "node_count_mismatch",
        "node_id_mismatch",
        "node_kind_mismatch",
        "node_block_mismatch",
        "node_shape_mismatch",
        "table_missing_headers_or_rows",
        "table_row_width_mismatch",
        "blank_text",
        "metadata_leaked",
        "task_answer_leaked",
        "internal_id_leaked",
        "unsupported_number",
        "task_anchor_ownership_mismatch",
        "length_over_target",
        "shape_missing",
        "list_item_not_parallel",
    }
    assert SECTION_WRITE_ISSUE_CODES == frozenset(expected)


def test_unknown_issue_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown section write issue code"):
        SectionWriteValidationError(["boom"], issues=(("not_a_real_code", ""),))


def test_payload_names_the_key_idea_slot_only_for_reserved_sections() -> None:
    from document.shared_lesson.writer import _request_payload

    request = _request()
    payload = _request_payload(request, repair_scope="initial", errors=())
    assert payload["key_idea_slot_node_id"] is None

    section = request.section.model_copy(
        update={
            "blocks": [
                request.section.blocks[0].model_copy(update={"intent": "explain"}),
                request.section.blocks[1],
            ]
        }
    )
    choices = [
        CompositionChoice(
            teaching_block_id="block-intro", kind="paragraph", semantic_role="explanation"
        ),
        CompositionChoice(
            teaching_block_id="block-compare", kind="table", semantic_role="comparison"
        ),
        CompositionChoice(
            teaching_block_id="block-compare", kind="list", semantic_role="evidence"
        ),
    ]
    composition = validate_and_build_composition(
        section=section, choices=choices, tasks=[_task()]
    )
    reserved = request.model_copy(update={"section": section, "composition_plan": composition})
    payload = _request_payload(reserved, repair_scope="initial", errors=())

    assert payload["key_idea_slot_node_id"] == composition.items[0].id
    assert payload["shaping_targets"]["key_idea_words_max"] == 25


def test_writer_prompt_tells_it_to_fill_the_key_idea_slot() -> None:
    from core.prompts import effective_prompt_text

    prompt = " ".join(effective_prompt_text("shared-section-writer").split())
    assert "key_idea_slot_node_id" in prompt
    assert "25 words or fewer" in prompt


def test_writer_prompt_carries_compare_versus_table_guidance() -> None:
    from core.prompts import effective_prompt_text

    prompt = " ".join(effective_prompt_text("shared-section-writer").split())
    assert (
        "Use compare only for two or three rival accounts that differ in content. "
        "Anything compared on the same attributes, or with more than three items, is a "
        "table with one column per thing compared. Keep table cells to about 12 words."
        in prompt
    )
    assert "comparison nodes keep every card" in prompt


def _provider_schema_failure(loc: tuple, error_type: str = "missing") -> Exception:
    from pydantic_ai.exceptions import ToolRetryError, UnexpectedModelBehavior
    from pydantic_ai.messages import RetryPromptPart

    try:
        try:
            raise ToolRetryError(
                RetryPromptPart(
                    content=[
                        {
                            "type": error_type,
                            "loc": loc,
                            "msg": "PROVIDER_MSG_SENTINEL",
                            "input": "PROVIDER_INPUT_SENTINEL",
                        }
                    ]
                )
            )
        except ToolRetryError as retry:
            raise UnexpectedModelBehavior("Exceeded maximum output retries (0)") from retry
    except UnexpectedModelBehavior as exc:
        return exc


@pytest.mark.asyncio
async def test_provider_schema_mismatch_enters_repair_loop_with_safe_path() -> None:
    request = _request()
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            raise _provider_schema_failure(("nodes", 2, "display", "rows"))
        return _draft(request)

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 2
    assert result.nodes[-1].kind == "task_anchor"
    assert calls[1]["repair"]["scope"] == "section"
    assert calls[1]["repair"]["issues"] == ["nodes[2].display.rows: missing"]
    table_id = [i for i in request.composition_plan.items if i.kind != "task_anchor"][2].id
    assert calls[1]["repair"]["affected_node_ids"] == [table_id]
    assert "SENTINEL" not in repr(calls[1]["repair"])


@pytest.mark.asyncio
async def test_provider_schema_mismatch_every_call_raises_after_three_calls() -> None:
    request = _request()
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        raise _provider_schema_failure(("nodes", 1, "display", "caption"), "string_too_short")

    with pytest.raises(SectionWriteValidationError) as caught:
        await write_section(request=request, provider=provider)

    assert calls == 3
    assert caught.value.issues == (("writer_draft_schema_invalid", "nodes[1].display.caption"),)
    assert caught.value.errors == ("nodes[1].display.caption: string_too_short",)
    assert "SENTINEL" not in repr(caught.value.errors)


@pytest.mark.asyncio
async def test_provider_empty_reply_is_repairable_and_timeout_still_propagates() -> None:
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    request = _request()
    calls: list[dict[str, Any]] = []

    async def empty_then_valid(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            raise UnexpectedModelBehavior("Exceeded maximum output retries (0)")
        return _draft(request)

    await write_section(request=request, provider=empty_then_valid)
    assert len(calls) == 2
    assert len(calls[1]["repair"]["issues"]) == 1

    timeouts = 0

    async def timing_out(_payload: dict[str, Any]) -> Any:
        nonlocal timeouts
        timeouts += 1
        raise TimeoutError("section writer timed out")

    with pytest.raises(TimeoutError):
        await write_section(request=request, provider=timing_out)
    assert timeouts == 1


# ---------------------------------------------------------------------------
# Node-level collection and patch/full repair modes
# ---------------------------------------------------------------------------


def _ordinary_ids(request: SectionWriterRequest) -> list[str]:
    return [item.id for item in request.composition_plan.items if item.kind != "task_anchor"]


def test_validation_collects_every_broken_node_and_keeps_good_ones() -> None:
    request = _request()
    ids = _ordinary_ids(request)
    draft = _draft(request)
    draft["nodes"][0]["display"]["text"] = "The must_establish field says particles move."
    draft["nodes"][2]["display"]["rows"] = [["Only one cell"]]

    validation = validate_draft_nodes(request=request, draft=draft)

    assert validation.broken_node_ids == (ids[0], ids[2])
    assert validation.kept_node_ids == (ids[1], ids[3])
    assert validation.repair_mode == "patch"
    assert [node.node is not None for node in validation.nodes] == [False, True, False, True]
    assert {(code, path) for node in validation.nodes for code, path, _m in node.issues} == {
        ("metadata_leaked", "nodes[0].text"),
        ("table_row_width_mismatch", "nodes[2].table.rows"),
    }

    with pytest.raises(SectionWriteValidationError) as excinfo:
        validate_and_build_section(request=request, draft=draft)
    assert excinfo.value.issues == (
        ("metadata_leaked", "nodes[0].text"),
        ("table_row_width_mismatch", "nodes[2].table.rows"),
    )
    assert excinfo.value.affected_node_ids == (ids[0], ids[2])


def test_node_schema_failures_report_safe_paths_per_node() -> None:
    request = _request()
    draft = _draft(request)
    del draft["nodes"][3]["display"]["items"]
    draft["nodes"][0]["display"]["text"] = ""
    draft["nodes"][2]["display"]["rows"] = "SECRET_SENTINEL text"

    validation = validate_draft_nodes(request=request, draft=draft)

    assert validation.repair_mode == "patch"
    paths = {path for node in validation.nodes for _c, path, _m in node.issues}
    assert any(path.startswith("nodes[3]") and path.endswith("items") for path in paths)
    assert any(path.startswith("nodes[2]") and path.endswith("rows") for path in paths)
    assert "SENTINEL" not in repr([node.issues for node in validation.nodes])


def test_section_level_problems_choose_full_mode() -> None:
    request = _request()
    for draft in (None, "nope", {"nodes": "x"}, {"nodes": []}, {"nodes": [], "extra": 1}):
        assert validate_draft_nodes(request=request, draft=draft).repair_mode == "full"
    short = _draft(request)
    short["nodes"].pop()
    count = validate_draft_nodes(request=request, draft=short)
    assert count.repair_mode == "full"
    assert count.to_error().affected_node_ids == tuple(_ordinary_ids(request))


@pytest.mark.asyncio
async def test_patch_repair_returns_only_broken_node_and_keeps_the_rest() -> None:
    request = _request()
    ids = _ordinary_ids(request)
    calls: list[dict[str, Any]] = []
    first = _draft(request)
    first["nodes"][2]["display"]["rows"] = [["Only one cell"]]
    first["nodes"][0]["display"]["text"] = "Original opening paragraph about particles."

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            return deepcopy(first)
        fixed = _payload_for_item(request.composition_plan.items[2])
        fixed["display"]["caption"] = "Repaired table"
        return {"nodes": [fixed]}

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 2
    repair = calls[1]["repair"]
    assert repair["mode"] == "patch"
    assert repair["scope"] == "section"
    assert repair["repair_node_ids"] == [ids[2]]
    assert repair["affected_node_ids"] == [ids[2]]
    assert repair["keep_node_ids"] == [ids[0], ids[1], ids[3]]
    assert repair["previous_draft"] == {"nodes": first["nodes"]}
    assert repair["issues"] == [
        f"nodes[2].table.rows ({ids[2]}): table rows must match the header width"
    ]
    assert result.repair_modes == ("patch",)
    assert result.nodes[0].display.text == "Original opening paragraph about particles."
    assert result.nodes[2].display.caption == "Repaired table"
    assert result.nodes[2].display.rows == (("Unheated", "Slower"), ("Heated", "Faster"))
    assert [node.id for node in result.nodes[:4]] == ids
    assert result.nodes[-1].kind == "task_anchor"
    assert result.model_dump(mode="json")["repair_modes"] == ["patch"]


@pytest.mark.asyncio
async def test_empty_reply_after_a_usable_draft_keeps_patching_that_draft() -> None:
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    request = _request()
    ids = _ordinary_ids(request)
    calls: list[dict[str, Any]] = []
    first = _draft(request)
    first["nodes"][2]["display"]["rows"] = [["Only one cell"]]

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            return deepcopy(first)
        if len(calls) == 2:
            raise UnexpectedModelBehavior("Exceeded maximum output retries (0)")
        return {"nodes": [_payload_for_item(request.composition_plan.items[2])]}

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 3
    repair = calls[2]["repair"]
    assert repair["mode"] == "patch"
    assert repair["repair_node_ids"] == [ids[2]]
    assert repair["previous_draft"] == {"nodes": first["nodes"]}
    assert any("table rows must match the header width" in issue for issue in repair["issues"])
    assert result.repair_modes == ("patch", "patch")


@pytest.mark.asyncio
async def test_patch_ignores_extra_and_renamed_ids_and_missing_id_stays_broken() -> None:
    request = _request()
    ids = _ordinary_ids(request)
    calls: list[dict[str, Any]] = []
    first = _draft(request)
    first["nodes"][2]["display"]["rows"] = [["Only one cell"]]

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            return deepcopy(first)
        if len(calls) == 2:
            renamed = _payload_for_item(request.composition_plan.items[2])
            renamed["id"] = "invented-id"
            rewrite_other = _payload_for_item(request.composition_plan.items[0])
            rewrite_other["display"]["text"] = "A paragraph the patch must not change."
            return {"nodes": [rewrite_other, renamed]}
        return {"nodes": [_payload_for_item(request.composition_plan.items[2])]}

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 3
    assert calls[1]["repair"]["mode"] == "patch"
    # Nothing usable came back, so the second repair patches the same node
    # against an unchanged previous draft.
    assert calls[2]["repair"]["mode"] == "patch"
    assert calls[2]["repair"]["repair_node_ids"] == [ids[2]]
    assert calls[2]["repair"]["previous_draft"] == {"nodes": first["nodes"]}
    assert calls[2]["repair"]["scope"] == "targeted"
    assert result.repair_modes == ("patch", "patch")
    assert result.nodes[0].display.text == "Heating gives water particles more motion."


@pytest.mark.asyncio
async def test_patch_that_breaks_a_section_rule_is_caught_by_the_full_recheck() -> None:
    request = _numeric_request()
    ids = _ordinary_ids(request)
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        draft = _draft(request)
        if len(calls) == 1:
            draft["nodes"][0]["display"]["text"] = "TODO write this paragraph."
            return draft
        patched = draft["nodes"][0]
        patched["display"]["text"] = (
            "Divide both sides by 4 to see that x = 9."
            if len(calls) == 2
            else "Divide both sides by the coefficient to isolate x."
        )
        return {"nodes": [patched]}

    result = await write_section(request=request, provider=provider)

    assert len(calls) == 3
    assert calls[1]["repair"]["repair_node_ids"] == [ids[0]]
    assert calls[2]["repair"]["mode"] == "patch"
    assert calls[2]["repair"]["repair_node_ids"] == [ids[0]]
    # The rejected patch is what the next repair is shown as the previous draft.
    assert "x = 9" in calls[2]["repair"]["previous_draft"]["nodes"][0]["display"]["text"]
    assert "states the result of an anchored task" in calls[2]["repair"]["issues"][0]
    assert result.repair_modes == ("patch", "patch")


@pytest.mark.asyncio
async def test_unparseable_reply_repairs_in_full_mode_without_previous_draft() -> None:
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    request = _request()
    calls: list[dict[str, Any]] = []

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        if len(calls) == 1:
            raise UnexpectedModelBehavior("Exceeded maximum output retries (0)")
        return _draft(request)

    result = await write_section(request=request, provider=provider)

    assert calls[1]["repair"]["mode"] == "full"
    assert calls[1]["repair"]["previous_draft"] is None
    assert "keep_node_ids" not in calls[1]["repair"]
    assert result.repair_modes == ("full",)

    calls.clear()

    async def non_object(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        return "not json at all" if len(calls) == 1 else _draft(request)

    await write_section(request=request, provider=non_object)
    assert calls[1]["repair"]["mode"] == "full"
    assert calls[1]["repair"]["previous_draft"] is None


@pytest.mark.asyncio
async def test_wrong_node_count_repairs_in_full_mode_with_previous_draft() -> None:
    request = _request()
    calls: list[dict[str, Any]] = []
    short = _draft(request)
    short["nodes"].pop()

    async def provider(payload: dict[str, Any]) -> Any:
        calls.append(payload)
        return deepcopy(short) if len(calls) == 1 else _draft(request)

    result = await write_section(request=request, provider=provider)

    assert calls[1]["repair"]["mode"] == "full"
    assert calls[1]["repair"]["previous_draft"] == short
    assert calls[1]["repair"]["affected_node_ids"] == _ordinary_ids(request)
    assert result.repair_modes == ("full",)


@pytest.mark.asyncio
async def test_three_failed_calls_raise_with_all_issues_and_repair_modes() -> None:
    request = _request()
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        draft = _draft(request)
        draft["nodes"][0]["display"]["text"] = "The must_establish field says particles move."
        draft["nodes"][2]["display"]["rows"] = [["Only one cell"]]
        return draft

    with pytest.raises(SectionWriteValidationError) as excinfo:
        await write_section(request=request, provider=provider)

    assert calls == 3
    assert excinfo.value.issues == (
        ("metadata_leaked", "nodes[0].text"),
        ("table_row_width_mismatch", "nodes[2].table.rows"),
    )
    assert excinfo.value.repair_modes == ("patch", "patch")


@pytest.mark.asyncio
async def test_timeout_during_a_patch_repair_propagates() -> None:
    request = _request()
    calls = 0

    async def provider(_payload: dict[str, Any]) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TimeoutError("section writer timed out")
        draft = _draft(request)
        draft["nodes"][2]["display"]["rows"] = [["Only one cell"]]
        return draft

    with pytest.raises(TimeoutError):
        await write_section(request=request, provider=provider)
    assert calls == 2


@pytest.mark.asyncio
async def test_default_provider_returns_raw_json_and_keeps_closed_schema_hint(monkeypatch) -> None:
    from document.shared_lesson import writer as writer_module
    from infra.authoring import structured_provider

    captured: dict[str, Any] = {}

    async def run_structured_agent(**kwargs):
        captured.update(kwargs)
        return kwargs["output_type"].model_validate({"nodes": [{"id": "n", "kind": "bogus"}]})

    monkeypatch.setattr(structured_provider, "run_structured_agent", run_structured_agent)
    reply = await writer_module._default_provider({"x": 1})

    # Not validated against the closed node schema; our code does that per node.
    assert reply == {"nodes": [{"id": "n", "kind": "bogus"}]}
    schema = captured["output_type"].model_json_schema()
    assert "$defs" not in schema and "$ref" not in str(schema)
    assert schema["properties"]["nodes"]["minItems"] == 1


@pytest.mark.asyncio
async def test_repair_modes_are_recorded_content_free_even_without_warnings(monkeypatch) -> None:
    from document.shared_lesson import runtime as runtime_module

    events: list[dict[str, Any]] = []

    async def append_event(_session, **kwargs):
        events.append(kwargs)

    monkeypatch.setattr(runtime_module, "append_event", append_event)
    await runtime_module._record_writer_style_warnings(
        None, run_id="r", work_item_id="w", warnings=(), repair_modes=()
    )
    assert events == []
    await runtime_module._record_writer_style_warnings(
        None, run_id="r", work_item_id="w", warnings=(), repair_modes=("patch", "full")
    )
    assert events[0]["event_type"] == "section_write_warning"
    assert events[0]["safe_payload"] == {
        "warning_codes": [],
        "warning_paths": [],
        "repair_modes": ["patch", "full"],
    }
