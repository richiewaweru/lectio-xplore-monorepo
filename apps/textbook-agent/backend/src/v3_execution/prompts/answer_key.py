from __future__ import annotations

from v3_execution.prompts.formatting import format_source_of_truth
from v3_execution.models import AnswerKeyExecutorWorkOrder


def build_answer_key_prompt(order: AnswerKeyExecutorWorkOrder) -> str:
    questions = "\n".join(
        f"- {q.id}: difficulty={q.difficulty}; answer={q.expected_answer}"
        for q in order.questions
        if q.id in set(order.answer_key_plan.include_question_ids)
    )
    return f"""You format answer keys — you do NOT invent new mathematics or facts.

STYLE: {order.answer_key_plan.style}

QUESTIONS:
{questions}

NOTES:
{chr(10).join(f'- {note}' for note in order.answer_key_plan.notes) or '- none'}

ANCHOR CONTEXT:
{format_source_of_truth(order.source_of_truth)}

Return JSON ONLY:
{{
  "entries": [
    {{"question_id": "...", "student_answer": "...", "working": "...optional...", "notes": "...optional..."}}
  ]
}}
Use the PROVIDED expected answers verbatim in the appropriate field — do NOT change them.
"""


__all__ = ["build_answer_key_prompt"]
