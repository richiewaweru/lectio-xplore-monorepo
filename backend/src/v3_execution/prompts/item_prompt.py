from __future__ import annotations

import json

from v3_blueprint.planning.models import ConceptCard


ITEM_SYSTEM_PROMPT = """You write assessment items that diagnose specific wrong beliefs.

You are given a concept, its objective, and a numbered list of misconceptions.
Write exactly 5 multiple-choice items.

Each incorrect option must be the answer a learner holding one named
misconception would confidently choose. Tag it with that id. You may only use
ids from the supplied list. Tag a plausible wrong option null when it does not
map cleanly; never stretch an id.

Across the five items, make every supplied misconception diagnosable at least
once. Prefer one clean diagnostic option over cramming every misconception into
each item.

Test the objective through transfer to fresh contexts. Do not test recall of
phrasing or an example. If memorising an example would answer an item without
understanding, rewrite it.

Quality rules:
- exactly one defensible correct option per item
- options have similar lengths and grammatical forms
- never use all-of-the-above or none-of-the-above
- avoid negation unless the concept itself is about negation
- no option is wrong only on a technicality
- the correct option is not identifiable by form

Return only the requested JSON."""


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

Required shape:
{
  "card_id": "the supplied card id",
  "items": [{
    "question_id": "stable card id plus .i1 through .i5",
    "prompt_text": "student-facing stem",
    "options": [
      {"key": "a", "text": "option", "correct": false, "diagnoses": "M1 or null"}
    ],
    "expected_answer": "correct answer with a concise explanation"
  }],
  "coverage": {"M1": 1},
  "unmapped_options": 0
}

APPROVED CARD
"""
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    ]


__all__ = ["ITEM_SYSTEM_PROMPT", "build_item_messages"]
