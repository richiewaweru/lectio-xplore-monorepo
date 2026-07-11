from __future__ import annotations

from generation.v3_studio.prompts import build_v3_shared_prefix
from v3_execution.prompts.formatting import format_source_of_truth
from v3_execution.models import QuestionWriterWorkOrder


def build_question_writer_prompt(order: QuestionWriterWorkOrder) -> str:
    shared_prefix = build_v3_shared_prefix()
    questions_spec = "\n\n".join(
        f"""Question {q.id}:
  Difficulty: {q.difficulty}
  Skill target: {q.skill_target}
  Scaffolding: {q.scaffolding}
  Purpose: {q.purpose}
  Diagram required: {"yes" if q.diagram_required else "no"}
  Uses anchor: {q.uses_anchor_id or "no"}
  Expected answer: {q.expected_answer}
  Expected working: {q.expected_working or "not required"}
  Constraints: {", ".join(q.student_facing_constraints) or "none"}"""
        for q in order.questions
    )
    return f"""{shared_prefix}
You are a question writer, not a lesson planner.

Write exactly the questions specified below.
Do not add questions. Do not remove questions.
Do not change difficulty. Do not change expected answers.
When Diagram required is no, never reference a visual: no "this shape",
"the figure", "shown below", or "look at". State all dimensions and facts in words.

QUESTIONS TO WRITE:
{questions_spec}

ANCHOR FACTS (do not change these):
{format_source_of_truth(order.source_of_truth)}

REGISTER:
{order.register_spec.level} · {order.register_spec.tone}
Avoid: {", ".join(order.register_spec.avoid) or "none"}

Return JSON ONLY: {{"items": {{
  "<question_id>": {{"stem": "<student-facing text>"}}
}} }}
"""


__all__ = ["build_question_writer_prompt"]
