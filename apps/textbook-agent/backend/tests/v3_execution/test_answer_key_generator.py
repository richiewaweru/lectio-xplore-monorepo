from __future__ import annotations

import pytest

from v3_execution.executors.answer_key_generator import execute_answer_key
from v3_execution.models import (
    AnswerKeyExecutorWorkOrder,
    AnswerKeyPlanSpec,
    WriterQuestion,
)


@pytest.mark.asyncio
async def test_execute_answer_key_is_deterministic_from_expected_answers() -> None:
    order = AnswerKeyExecutorWorkOrder(
        work_order_id="wo-1",
        questions=[
            WriterQuestion(id="q1", difficulty="warm", expected_answer="42"),
            WriterQuestion(id="q2", difficulty="medium", expected_answer="9"),
        ],
        answer_key_plan=AnswerKeyPlanSpec(
            style="answers_only",
            include_question_ids=["q2", "q1"],
            notes=[],
        ),
        source_of_truth=[],
    )

    events: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    block = await execute_answer_key(
        order,
        emit,
        trace_id="trace-1",
        generation_id="gen-1",
        model_overrides={"slot": "ignored"},
    )

    assert block is not None
    assert [entry["question_id"] for entry in block.entries] == ["q1", "q2"]
    assert [entry["student_answer"] for entry in block.entries] == ["42", "9"]
    assert all(entry["explanation"] == "" for entry in block.entries)
    assert [event for event, _payload in events] == ["answer_key_started", "answer_key_ready"]


@pytest.mark.asyncio
async def test_execute_answer_key_raises_when_include_ids_are_missing() -> None:
    order = AnswerKeyExecutorWorkOrder(
        work_order_id="wo-2",
        questions=[WriterQuestion(id="q1", difficulty="warm", expected_answer="42")],
        answer_key_plan=AnswerKeyPlanSpec(
            style="answers_only",
            include_question_ids=["q1", "q2"],
            notes=[],
        ),
        source_of_truth=[],
    )

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    with pytest.raises(RuntimeError, match="Answer key missing question q2"):
        await execute_answer_key(
            order,
            emit,
            trace_id="trace-2",
            generation_id="gen-2",
            model_overrides=None,
        )
