from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from v3_execution.llm_helpers import run_json_agent
from v3_execution.models import ExecutorOutcome, GeneratedQuestionBlock, QuestionWriterWorkOrder
from v3_execution.prompts.question_writer import build_question_writer_prompt
from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.runtime.retry_runner import run_with_retries
from v3_execution.runtime.validation import validate_question_batch


EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _items_map(payload: dict[str, Any]) -> dict[str, Any]:
    if "items" in payload and isinstance(payload["items"], dict):
        return payload["items"]
    return payload


async def execute_questions(
    order: QuestionWriterWorkOrder,
    emit_event: EmitFn,
    *,
    trace_id: str | None,
    generation_id: str | None,
    model_overrides: dict | None = None,
) -> list[GeneratedQuestionBlock]:
    await emit_event(
        "questions_started",
        {"section_id": order.section_id, "generation_id": generation_id},
    )

    async def _attempt(_: bool) -> ExecutorOutcome:
        prompt = build_question_writer_prompt(order)
        response = await run_json_agent(
            node_name="v3_question_writer",
            trace_id=trace_id,
            generation_id=generation_id,
            system_prompt="You output JSON only.",
            user_prompt=prompt,
            model_overrides=model_overrides,
        )
        bucket = _items_map(response)
        blocks: list[GeneratedQuestionBlock] = []
        errors: list[str] = []

        for planned in order.questions:
            entry = bucket.get(planned.id)
            if entry is None:
                errors.append(f"Missing stem for question {planned.id}")
                continue
            stem = entry.get("stem") if isinstance(entry, dict) else str(entry)

            difficulty = planned.difficulty
            data = {
                "question": stem,
                "difficulty": difficulty,
                "hints": [],
            }
            blocks.append(
                GeneratedQuestionBlock(
                    question_id=planned.id,
                    section_id=order.section_id,
                    difficulty=difficulty,
                    data=data,
                    expected_answer=planned.expected_answer,
                    expected_working=planned.expected_working,
                    diagram_required=planned.diagram_required,
                    source_work_order_id=order.work_order_id,
                )
            )

        errors.extend(validate_question_batch(blocks, order))
        ok = len(errors) == 0
        return ExecutorOutcome(ok=ok, blocks=blocks, errors=errors)

    outcome = await run_with_retries(
        f"questions:{order.section_id}",
        _attempt,
        max_retries=V3_MAX_RETRIES["question_writer"],
    )
    if not outcome.ok:
        raise RuntimeError("; ".join(outcome.errors))

    emitted: list[GeneratedQuestionBlock] = []
    for block in outcome.blocks:
        if not isinstance(block, GeneratedQuestionBlock):
            continue
        emitted.append(block)
        await emit_event(
            "question_ready",
            {
                "generation_id": generation_id,
                "question_id": block.question_id,
                "section_id": block.section_id,
                "difficulty": block.difficulty,
                "data": block.data,
            },
        )
    return emitted


__all__ = ["execute_questions"]
