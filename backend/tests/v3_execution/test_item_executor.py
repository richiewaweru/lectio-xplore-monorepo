from __future__ import annotations

import inspect

import pytest

from v3_blueprint.planning.models import ConceptCard, Misconception
from v3_execution.executors.item_executor import (
    DiagnosticItem,
    DiagnosticOption,
    ItemGenerationResult,
    execute_items,
    validate_item_result,
)
from v3_execution.prompts.item_prompt import build_item_messages


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


def _item(index: int, diagnosis: str | None) -> DiagnosticItem:
    return DiagnosticItem(
        question_id=f"biology.photosynthesis.inputs.i{index}",
        prompt_text=f"Fresh transfer scenario {index}",
        options=[
            DiagnosticOption(key="a", text="Correct response", correct=True),
            DiagnosticOption(
                key="b",
                text="Diagnostic response",
                correct=False,
                diagnoses=diagnosis,
            ),
            DiagnosticOption(key="c", text="Other response", correct=False),
            DiagnosticOption(key="d", text="Another response", correct=False),
        ],
        expected_answer="Correct response, because the objective applies.",
    )


def test_item_executor_public_signature_accepts_only_card() -> None:
    assert list(inspect.signature(execute_items).parameters) == ["card"]


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
        DiagnosticItem(
            question_id="q1",
            prompt_text="Question",
            options=[
                DiagnosticOption(key="a", text="One", correct=True),
                DiagnosticOption(key="b", text="Two", correct=True),
            ],
            expected_answer="One",
        )
