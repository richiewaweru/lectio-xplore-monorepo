"""R02 gate G06: preserve canonical IDs and answer structures on conversion."""

from __future__ import annotations

from typing import Any, Mapping

from learn.generation.interaction_writer import write_interaction_from_request


def _request(
    capability_id: str,
    *,
    action: str,
    approved_items: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "work_order_id": f"r02::{capability_id}",
        "block_id": f"b-{capability_id}",
        "capability_id": capability_id,
        "lane": "interaction",
        "brief": f"Author {capability_id}",
        "intent": "check-understanding",
        "action": action,
        "evidence": "Known-answer regression",
        "teaching_plan_hash": "r02",
        "lesson_context": {"objective": "Known-answer regression objective"},
        "allowed_facts": ["Scoped fact for regression."],
        "terminology": [],
        "approved_items": approved_items or [],
    }


def test_r02_g06_sequence_ids_preserved_without_slugify() -> None:
    """R02-G06: sequence conversion keeps canonical step IDs."""
    approved = {
        "id": "seq-r02",
        "stem": "Order the water cycle steps.",
        "correct_order": ["Stage_A", "Stage_B", "Stage_C"],
        "items": [
            {"id": "Stage_A", "label": "Evaporation"},
            {"id": "Stage_B", "label": "Condensation"},
            {"id": "Stage_C", "label": "Precipitation"},
        ],
    }
    contract = write_interaction_from_request(
        _request("sequence", action="order-items", approved_items=[approved]),
    )
    assert contract["config"]["order"] == ["Stage_A", "Stage_B", "Stage_C"]
    assert contract["config"]["items"][0]["id"] == "Stage_A"


def test_r02_g06_numeric_value_preserved() -> None:
    """R02-G06: numeric conversion preserves exact value and unit."""
    approved = {
        "id": "num-r02",
        "stem": "What is the distance?",
        "value": 50.5,
        "tolerance": 0.1,
        "unit": "m",
    }
    contract = write_interaction_from_request(
        _request("numeric", action="enter-number", approved_items=[approved]),
    )
    assert contract["config"]["value"] == 50.5
    assert contract["config"]["tolerance"] == 0.1
    assert contract["config"]["unit"] == "m"


def test_r02_g06_short_response_accepted_answers_array_preserved() -> None:
    """R02-G06: accepted-answer alternatives remain an array, not coerced to one string."""
    approved = {
        "id": "short-r02",
        "stem": "Name the green pigment in leaves.",
        "accepted_answers": ["chlorophyll", "Chlorophyll"],
    }
    contract = write_interaction_from_request(
        _request("short-response", action="enter-text", approved_items=[approved]),
    )
    assert contract["config"]["evaluation"] == "accepted-answers"
    assert contract["config"]["accepted_answers"] == ["chlorophyll", "Chlorophyll"]
