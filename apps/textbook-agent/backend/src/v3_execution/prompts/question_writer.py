from __future__ import annotations

from generation.v3_studio.prompts import build_v3_shared_prefix
from core.prompts import effective_prompt_text
from v3_execution.prompts.formatting import format_source_of_truth
from v3_execution.models import QuestionWriterWorkOrder


def _load_static_body() -> str:
    return effective_prompt_text("question-writer")


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
{_load_static_body()}
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
