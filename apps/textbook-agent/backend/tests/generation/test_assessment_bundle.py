"""Assessment bundle: open response vs MCQ without illegal enrichment."""

from __future__ import annotations

import pytest

from generation.page_objects import (
    WriterContext,
    assemble_choices,
    assemble_questions,
    build_assessment_bundle,
)
from v3_blueprint.planning.models import PlannedBlock


def test_open_response_bundle_separates_answers() -> None:
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "s4-questions",
                "position": 0,
                "intent": "check-understanding",
                "object": "questions",
                "evidence": "card",
                "brief": "MUST NOT BECOME PROMPT",
                "source_question_ids": ["q-open-1"],
            }
        ),
        item_records=(
            {
                "id": "q-open-1",
                "prompt": "Explain why covering the leaf helps.",
                "marks": 2,
                "answer_lines": 3,
                "answer": "Light is the changed condition.",
                "rubric": "2 marks for light comparison.",
            },
        ),
    )
    bundle = build_assessment_bundle(ctx)
    student = bundle.student_blocks[0]
    assert ctx.planned.object == "questions"
    assert student.block_id == "s4-questions"
    item = student.content["items"][0]
    assert item["id"] == "q-open-1"
    assert item["prompt"] == "Explain why covering the leaf helps."
    assert "options" not in item
    assert "correct_key" not in item
    assert "answer_key_ref" not in item
    assert len(bundle.answer_entries) == 1
    assert bundle.answer_entries[0].question_id == "q-open-1"
    assert "Light" in bundle.answer_entries[0].answer


def test_mcq_bundle_uses_block_id_for_answer() -> None:
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "q-mcq-1",
                "position": 1,
                "intent": "diagnose-misconception",
                "object": "choices",
                "evidence": "card",
                "brief": "MCQ brief",
                "source_question_ids": ["q-mcq-1"],
            }
        ),
        item_records=(
            {
                "id": "q-mcq-1",
                "stem": "Role of soil?",
                "options": [
                    {"letter": "A", "text": "Soil is food"},
                    {"letter": "B", "text": "Soil supplies minerals"},
                    {"letter": "C", "text": "Soil supplies sunlight"},
                ],
                "correct_key": "B",
                "marks": 1,
            },
        ),
    )
    bundle = build_assessment_bundle(ctx)
    student = bundle.student_blocks[0]
    assert ctx.planned.object == "choices"
    assert student.content["stem"] == "Role of soil?"
    assert len(student.content["options"]) == 3
    assert bundle.answer_entries[0].question_id == "q-mcq-1"
    assert bundle.answer_entries[0].answer == "B"


def test_assemble_questions_rejects_multiple_choice_source() -> None:
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "q1",
                "position": 0,
                "intent": "check-understanding",
                "object": "questions",
                "evidence": "card",
                "brief": "brief",
                "source_question_ids": ["item-1"],
            }
        ),
        item_records=(
            {
                "id": "item-1",
                "prompt": "Why?",
                "options": [{"key": "A", "text": "x"}],
                "correct_key": "A",
                "answer": "Because light.",
            },
        ),
    )
    with pytest.raises(Exception, match="must be assembled as choices"):
        assemble_questions(ctx)


def test_assemble_choices_normalizes_key_to_letter() -> None:
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "c1",
                "position": 0,
                "intent": "diagnose-misconception",
                "object": "choices",
                "evidence": "card",
                "brief": "brief",
                "source_question_ids": ["c1"],
            }
        ),
        item_records=(
            {
                "id": "c1",
                "prompt": "Which?",
                "options": [
                    {"key": "A", "text": "One"},
                    {"key": "B", "text": "Two"},
                ],
                "correct_key": "A",
            },
        ),
    )
    result = assemble_choices(ctx)
    assert result.content["options"][0]["letter"] == "A"
    assert result.answer_entries[0]["question_id"] == "c1"


def test_assemble_choices_uses_exact_source_question_among_many_records() -> None:
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "check-b1",
                "position": 0,
                "intent": "check-understanding",
                "object": "choices",
                "evidence": "card",
                "brief": "brief",
                "source_question_ids": ["q2"],
            }
        ),
        item_records=(
            {
                "id": "q1",
                "prompt": "First?",
                "options": [
                    {"key": "A", "text": "One"},
                    {"key": "B", "text": "Two"},
                ],
                "correct_key": "A",
            },
            {
                "id": "q2",
                "prompt": "Second?",
                "options": [
                    {"key": "A", "text": "Three"},
                    {"key": "B", "text": "Four"},
                ],
                "correct_key": "B",
            },
        ),
    )

    result = assemble_choices(ctx)

    assert result.content["stem"] == "Second?"
    assert result.answer_entries[0]["question_id"] == "check-b1"
    assert result.answer_entries[0]["answer"] == "B"
