from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from v3_blueprint.planning.models import (
    ConceptCard,
    ItemOption,
    Misconception,
    QuestionBrief,
)
from v3_execution.executors.item_executor import (
    ItemGenerationDraft,
    ItemGenerationResult,
    ItemQuestionDraft,
    execute_items,
    materialize_item_result,
    validate_item_result,
)
from v3_execution.prompts.item_prompt import build_item_messages
from core.llm.deepseek_schema import to_deepseek_strict_schema


def _card() -> ConceptCard:
    return ConceptCard(
        id="biology.photosynthesis.inputs",
        title="Inputs to photosynthesis",
        objective="Identify the inputs plants use to make glucose.",
        misconceptions=[
            Misconception(
                id="M1",
                description="Plants obtain food directly from soil.",
            ),
            Misconception(
                id="M2",
                description="Sunlight is a material consumed by the plant.",
            ),
        ],
    ).with_item_context(
        subject="Biology",
        level="Form 2",
        notation="Use word equations.",
    )


def _item(index: int, diagnosis: str | None) -> QuestionBrief:
    return QuestionBrief(
        question_id=f"biology.photosynthesis.inputs.i{index}",
        prompt_text=f"Fresh transfer scenario {index}",
        options=[
            ItemOption(key="a", text="Correct response", correct=True),
            ItemOption(
                key="b",
                text="Diagnostic response",
                correct=False,
                diagnoses=diagnosis,
            ),
            ItemOption(key="c", text="Other response", correct=False),
            ItemOption(key="d", text="Another response", correct=False),
        ],
        expected_answer="Correct response, because the objective applies.",
    )


def _draft_item(index: int, diagnosis: str | None) -> ItemQuestionDraft:
    return ItemQuestionDraft(
        prompt_text=f"Fresh transfer scenario {index}",
        options=[
            ItemOption(key="a", text="Correct response", correct=True),
            ItemOption(
                key="b",
                text="Diagnostic response",
                correct=False,
                diagnoses=diagnosis,
            ),
            ItemOption(key="c", text="Other response", correct=False),
            ItemOption(key="d", text="Another response", correct=False),
        ],
        expected_answer="Correct response, because the objective applies.",
    )


def test_item_executor_public_signature_accepts_only_card() -> None:
    assert list(inspect.signature(execute_items).parameters) == ["card"]


def test_item_executor_rejects_generated_content_channel() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        execute_items(  # type: ignore[call-arg]
            _card(),
            generated_content={"sections": ["contaminating prose"]},
        )


def test_item_prompt_contains_only_approved_card_fields() -> None:
    message = build_item_messages(_card())[0]

    assert "Inputs to photosynthesis" in message
    assert "Plants obtain food directly from soil" in message
    assert '"subject": "Biology"' in message
    assert '"level": "Form 2"' in message
    assert '"notation": "Use word equations."' in message
    for forbidden in (
        "component_id",
        "transition_note",
        "anchor",
        "generated_text",
        "section_brief",
    ):
        assert forbidden not in message


def test_item_provider_schema_has_only_items_and_no_question_id() -> None:
    schema = ItemGenerationDraft.model_json_schema()
    assert set(schema["properties"]) == {"items"}
    item_props = schema["$defs"]["ItemQuestionDraft"]["properties"]
    assert "question_id" not in item_props
    projected = to_deepseek_strict_schema(schema)
    assert set(projected["properties"]) == {"items"}
    assert "question_id" not in projected["$defs"]["ItemQuestionDraft"]["properties"]


def test_item_draft_rejects_upstream_identity_fields() -> None:
    with pytest.raises(ValidationError):
        ItemGenerationDraft.model_validate(
            {
                "card_id": "biology.photosynthesis.inputs",
                "items": [_draft_item(1, "M1").model_dump()],
            }
        )
    with pytest.raises(ValidationError):
        ItemQuestionDraft.model_validate(
            {
                "question_id": "biology.photosynthesis.inputs.i1",
                **_draft_item(1, "M1").model_dump(),
            }
        )


def test_materialize_item_result_stamps_card_and_question_ids() -> None:
    draft = ItemGenerationDraft(
        items=[_draft_item(index, None) for index in range(1, 6)]
    )

    result = materialize_item_result(draft, _card())

    assert result.card_id == _card().id
    assert [item.question_id for item in result.items] == [
        f"{_card().id}.i{index}" for index in range(1, 6)
    ]


def test_item_validator_recomputes_coverage_and_unmapped_count() -> None:
    result = ItemGenerationResult(
        card_id=_card().id,
        items=[
            _item(1, "M1"),
            _item(2, "M2"),
            _item(3, None),
            _item(4, "M1"),
            _item(5, None),
        ],
        coverage={"invented": 99},
        unmapped_options=99,
    )

    validated = validate_item_result(result, _card())

    assert validated.coverage == {"M1": 2, "M2": 1}
    assert validated.unmapped_options == 12
    assert validated.needs_review is False


def test_item_validator_rejects_unknown_misconception_id() -> None:
    result = ItemGenerationResult(
        card_id=_card().id,
        items=[_item(index, "M9") for index in range(1, 6)],
    )

    with pytest.raises(ValueError, match="unknown misconception"):
        validate_item_result(result, _card())


def test_item_validator_flags_missing_coverage_for_review() -> None:
    result = ItemGenerationResult(
        card_id=_card().id,
        items=[_item(index, "M1") for index in range(1, 6)],
    )

    validated = validate_item_result(result, _card())

    assert validated.needs_review is True
    assert validated.missing_misconceptions == ("M2",)


def test_item_requires_exactly_one_correct_option() -> None:
    with pytest.raises(ValueError, match="exactly one correct"):
        QuestionBrief(
            question_id="q1",
            prompt_text="Question",
            options=[
                ItemOption(key="a", text="One", correct=True),
                ItemOption(key="b", text="Two", correct=True),
            ],
            expected_answer="One",
        )
