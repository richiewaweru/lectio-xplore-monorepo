from __future__ import annotations

import json

from core.prompts import effective_prompt_text
from curriculum.backbone.models import LessonBackbone
from curriculum.planning.models import ConceptCard


def get_item_system_prompt() -> str:
    return effective_prompt_text("quiz-items")


def __getattr__(name: str):
    # `from module import ITEM_SYSTEM_PROMPT` resolves via __getattr__.
    if name == "ITEM_SYSTEM_PROMPT":
        return get_item_system_prompt()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


BACKBONE_ITEM_RULES = """
LESSON BACKBONE (the only scenarios, shapes and data you may use)
Every question is about the anchor or one of its variants (state which in
backbone_ref.target, using the anchor or variant id). If the learner must look
at a figure to answer, set backbone_ref.figure_id to that figure's id and make
the stem refer to it. Do not invent other scenarios, shapes or data. Never copy
the anchor's worked answer into a stem.
Add to each item: "backbone_ref": {"target": "<anchor or variant id>", "figure_id": "<figure id or null>"}
"""


def backbone_prompt_block(backbone: LessonBackbone) -> str:
    data = backbone.model_dump(mode="json")
    return BACKBONE_ITEM_RULES + json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n"


def build_item_messages(
    card: ConceptCard,
    *,
    backbone: LessonBackbone | None = None,
    repair_errors: list[str] | None = None,
    allowed_misconception_ids: list[str] | None = None,
    previous_output: object | None = None,
) -> list[str]:
    subject, level, notation = card.item_context()
    payload = {
        "card_id": card.id,
        "title": card.title,
        "objective": card.objective,
        "misconceptions": [
            {"id": row.id, "description": row.description}
            for row in card.misconceptions
        ],
        "subject": subject,
        "level": level,
        "notation": notation,
    }
    base_prompt = """Write the five diagnostic items for this approved concept card.
Use only named misconception ids or null in diagnoses. Follow the notation
constraint when it is present.

Required shape (coverage and unmapped-option counts are computed downstream):
{
  "items": [{
    "prompt_text": "student-facing stem",
    "options": [
      {"key": "a", "text": "option", "correct": true, "diagnoses": null},
      {"key": "b", "text": "option", "correct": false, "diagnoses": "M1"}
    ],
    "expected_answer": "correct answer with a concise explanation"
  }]
}

Rules:
- Every option must include `diagnoses` (strict schema).
- If `correct` is true, `diagnoses` must be exactly JSON null.
- If `correct` is false, `diagnoses` must be either one named, approved misconception id
  or JSON null (meaning unmapped-option for downstream counting).
- Never guess or invent a misconception id.

Do not output any stable identity fields. The backend owns item identity
and assigns stable ids from the approved card and item order.

APPROVED CARD
"""
    if backbone is not None:
        base_prompt = base_prompt + json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        base_prompt += backbone_prompt_block(backbone)
        payload = None
    tail = "" if payload is None else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if repair_errors is None:
        return [base_prompt + tail]

    allowed_ids = allowed_misconception_ids or []
    errors_json = json.dumps(list(repair_errors), ensure_ascii=False)
    previous_json = (
        json.dumps(previous_output, ensure_ascii=False, sort_keys=True)
        if previous_output is not None
        else "null"
    )

    repair_prompt = (
        base_prompt
        + "\n"
        + "REPAIR CONTEXT (attempt 2+ only)\n"
        + "- Validation errors you must fix:\n"
        + errors_json
        + "\n"
        + "- Allowed misconception ids:\n"
        + json.dumps(allowed_ids, ensure_ascii=False)
        + "\n"
        + "- Previous provider output:\n"
        + previous_json
        + "\n\n"
        + "Repair rules:\n"
        + "- Return the complete corrected five-item set.\n"
        + "- Fix only the listed validation errors.\n"
        + "- Do not invent or rename misconception ids.\n"
        + "- correct=true => diagnoses must be JSON null.\n"
        + "- correct=false => diagnoses must be either an allowed misconception id or JSON null.\n"
        + "- Keep all approved card and item identities owned by the backend.\n"
    )

    return [repair_prompt + tail]


__all__ = ["BACKBONE_ITEM_RULES", "backbone_prompt_block", "build_item_messages", "get_item_system_prompt"]
