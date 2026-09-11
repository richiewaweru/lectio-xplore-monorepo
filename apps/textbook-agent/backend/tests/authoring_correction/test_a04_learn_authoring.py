"""A04: Learn authoring — closed salvage removed; v2 production is canonical.

Shared request helpers remain for policy/remaining_fixes regressions that still
exercise interaction writers against approved items.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from learn.generation import native_production


CORE_CONFIG: dict[str, dict[str, Any]] = {
    "choice": {
        "options": [
            {"id": "a", "text": "liquid to solid"},
            {"id": "b", "text": "liquid to vapour"},
        ],
        "correct_option_id": "b",
    },
    "multi-select": {
        "options": [
            {"id": "stone", "text": "stone"},
            {"id": "evaporation", "text": "evaporation"},
            {"id": "metal", "text": "metal"},
            {"id": "condensation", "text": "condensation"},
        ],
        "correct_option_ids": ["evaporation", "condensation"],
    },
    "fill-blank": {
        "answers": ["chlorophyll"],
        "blank_ids": ["pigment"],
        "case_sensitive": False,
    },
    "numeric": {"value": 50, "tolerance": 0, "unit": "m"},
    "short-response": {
        "evaluation": "teacher-review",
        "review_guidance": "Explain the condensation.",
    },
    "match-pairs": {
        "pairs": [
            {"left": "evaporation", "right": "liquid to vapour"},
            {"left": "condensation", "right": "vapour to liquid"},
        ]
    },
    "classify": {
        "categories": [
            {"id": "liquid", "label": "liquid"},
            {"id": "gas", "label": "gas"},
        ],
        "pairs": [
            {"left": "rain", "right": "liquid"},
            {"left": "water vapour", "right": "gas"},
            {"left": "dew", "right": "liquid"},
        ],
    },
    "sequence": {
        "items": [
            {"id": "egg", "label": "egg"},
            {"id": "larva", "label": "larva"},
            {"id": "pupa", "label": "pupa"},
            {"id": "adult", "label": "adult"},
        ],
        "order": ["egg", "larva", "pupa", "adult"],
    },
}


def _request(
    capability_id: str,
    *,
    action: str,
    approved_items: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "work_order_id": f"a04::{capability_id}",
        "block_id": f"b-{capability_id}",
        "capability_id": capability_id,
        "lane": "interaction",
        "brief": f"Author {capability_id}",
        "intent": "check-understanding",
        "action": action,
        "evidence": "Known-answer regression",
        "teaching_plan_hash": "a04",
        "lesson_context": {"objective": "Known-answer regression objective"},
        "allowed_facts": ["Scoped fact for regression."],
        "terminology": [],
        "approved_items": approved_items or [],
    }


def test_a04_closed_salvage_and_ordered_assemble_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src
    assert not (Path(native_production.__file__).parent / "ordered_assemble.py").exists()
