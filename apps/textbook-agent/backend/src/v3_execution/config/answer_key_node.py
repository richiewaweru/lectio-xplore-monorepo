from __future__ import annotations

from v3_execution.config.models import V3_ANSWER_KEY_GENERATOR, V3_ANSWER_KEY_GENERATOR_HEAVY
from v3_execution.models import AnswerKeyExecutorWorkOrder


def effective_answer_key_node_name(order: AnswerKeyExecutorWorkOrder) -> str:
    """FAST when every included question has expected_answer; STANDARD for full_working without working."""
    include_ids = set(order.answer_key_plan.include_question_ids)
    qs = [q for q in order.questions if q.id in include_ids]
    if not qs:
        return V3_ANSWER_KEY_GENERATOR
    missing_expected = any(not (q.expected_answer or "").strip() for q in qs)
    if missing_expected:
        return V3_ANSWER_KEY_GENERATOR_HEAVY
    if order.answer_key_plan.style == "full_working":
        missing_working = any(not (q.expected_working or "").strip() for q in qs)
        if missing_working:
            return V3_ANSWER_KEY_GENERATOR_HEAVY
    return V3_ANSWER_KEY_GENERATOR


__all__ = ["effective_answer_key_node_name"]
