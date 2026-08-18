from __future__ import annotations

import json

from core.prompts import effective_prompt_text
from v3_blueprint.planning.models import ConceptCard


def get_item_system_prompt() -> str:
    return effective_prompt_text("quiz-items")


def __getattr__(name: str):
    # `from module import ITEM_SYSTEM_PROMPT` resolves via __getattr__.
    if name == "ITEM_SYSTEM_PROMPT":
        return get_item_system_prompt()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def build_item_messages(card: ConceptCard) -> list[str]:
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
    return [
        """Write the five diagnostic items for this approved concept card.
Use only named misconception ids or null in diagnoses. Follow the notation
constraint when it is present.

Required shape (coverage and unmapped-option counts are computed downstream):
{
  "items": [{
    "prompt_text": "student-facing stem",
    "options": [
      {"key": "a", "text": "option", "correct": false, "diagnoses": "M1 or null"}
    ],
    "expected_answer": "correct answer with a concise explanation"
  }]
}

Do not output any stable identity fields. The backend owns item identity
and assigns stable ids from the approved card and item order.

APPROVED CARD
"""
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    ]


__all__ = ["build_item_messages", "get_item_system_prompt"]
