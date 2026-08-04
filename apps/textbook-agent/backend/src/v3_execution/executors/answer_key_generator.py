from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from v3_execution.models import (
    AnswerKeyExecutorWorkOrder,
    GeneratedAnswerKeyBlock,
)


EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _build_deterministic_entries(order: AnswerKeyExecutorWorkOrder) -> tuple[list[dict[str, Any]], list[str]]:
    include_ids = order.answer_key_plan.include_question_ids
    include_set = set(include_ids)
    present_ids: set[str] = set()
    entries: list[dict[str, Any]] = []

    for question in order.questions:
        if question.id not in include_set:
            continue
        present_ids.add(question.id)
        entries.append(
            {
                "question_id": question.id,
                "student_answer": question.expected_answer,
                # Keep explanations blank for now; answers remain deterministic.
                "explanation": "",
            }
        )

    errors = [
        f"Answer key missing question {question_id}"
        for question_id in include_ids
        if question_id not in present_ids
    ]
    return entries, errors


async def execute_answer_key(
    order: AnswerKeyExecutorWorkOrder | None,
    emit_event: EmitFn,
    *,
    trace_id: str | None,
    generation_id: str | None,
    model_overrides: dict | None = None,
) -> GeneratedAnswerKeyBlock | None:
    if order is None:
        return None

    _ = trace_id, model_overrides
    await emit_event("answer_key_started", {"generation_id": generation_id})

    entries, errors = _build_deterministic_entries(order)
    if errors:
        raise RuntimeError("; ".join(errors))

    block = GeneratedAnswerKeyBlock(
        answer_key_id=str(uuid.uuid4()),
        style=order.answer_key_plan.style,
        entries=entries,
        source_work_order_id=order.work_order_id,
    )

    await emit_event(
        "answer_key_ready",
        {
            "generation_id": generation_id,
            "style": block.style,
            "answer_key_id": block.answer_key_id,
        },
    )
    return block


__all__ = ["execute_answer_key"]
