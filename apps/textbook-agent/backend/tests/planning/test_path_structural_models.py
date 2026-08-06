"""Contract tests for the structural planner's prompt-facing output models.

These models are what the provider sees as its output schema. Two properties
matter and pull in opposite directions:

* the schema must be *typed* (the previous ``list[dict]`` told the model nothing,
  which is how ``slot_id`` and a three-card plan both got through);
* it must stay *tolerant* of field drift the bridge already normalises, because
  on the prompted path the schema is advisory text, so strictness would only
  convert silently-repaired output into hard failures.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planning.models import PathStructuralCard, PathStructuralPlan, PathStructuralSection


def _section(**overrides: object) -> dict:
    payload = {
        "id": "orient",
        "role": "orient",
        "title": "Opening",
        "card_id": None,
        "visual_required": False,
        "transition_note": None,
    }
    payload.update(overrides)
    return payload


def _plan(**overrides: object) -> dict:
    payload = {
        "anchor": {"description": "two basil plants", "source": "new"},
        "cards": [{"id": "c1", "title": "Light", "objective": "Explain why."}],
        "sections": [_section()],
        "deviation_request": None,
        "objective_concern": None,
    }
    payload.update(overrides)
    return payload


# ── card cardinality ──────────────────────────────────────────────────────


def test_accepts_exactly_one_card() -> None:
    plan = PathStructuralPlan.model_validate(_plan())
    assert len(plan.cards) == 1
    assert isinstance(plan.cards[0], PathStructuralCard)


def test_rejects_two_cards() -> None:
    payload = _plan(
        cards=[
            {"id": "c1", "title": "A", "objective": "x"},
            {"id": "c2", "title": "B", "objective": "y"},
        ]
    )
    with pytest.raises(ValidationError) as excinfo:
        PathStructuralPlan.model_validate(payload)
    assert "cards" in str(excinfo.value)


def test_accepts_zero_cards_when_objective_concern_is_raised() -> None:
    """The escape hatch must survive the schema.

    A planner that judges the objective unfit answers with no cards and a
    concern. A schema-level minimum would turn that into a validation error and
    destroy the concern message before the bridge could surface it.
    """
    plan = PathStructuralPlan.model_validate(
        _plan(cards=[], objective_concern="Objective spans two concepts.")
    )
    assert plan.cards == []
    assert plan.objective_concern == "Objective spans two concepts."


def test_accepts_omitted_escape_hatch_keys() -> None:
    payload = _plan()
    del payload["deviation_request"]
    del payload["objective_concern"]
    plan = PathStructuralPlan.model_validate(payload)
    assert plan.deviation_request is None
    assert plan.objective_concern is None


# ── tolerance of known planner drift ──────────────────────────────────────


def test_section_tolerates_and_drops_slot_id_and_blocks() -> None:
    """The observed 422 was a section keyed ``slot_id``.

    It must not crash the parse, and it must not survive into the dump — the
    canonical key is ``id``, and blocks are owned by the form planner.
    """
    section = PathStructuralSection.model_validate(
        _section(slot_id="orient", blocks=[{"id": "b1"}], purpose="hook them")
    )
    dumped = section.model_dump(mode="json", exclude_none=True)
    assert section.id == "orient"
    assert "slot_id" not in dumped
    assert "blocks" not in dumped
    assert "purpose" not in dumped


def test_card_tolerates_planner_only_extras() -> None:
    card = PathStructuralCard.model_validate(
        {
            "id": "c1",
            "title": "Light",
            "objective": "Explain why.",
            "concept_id": "wrong-id",
            "definition": "planner-only",
            "body": "planner-only",
            "examples": ["planner-only"],
        }
    )
    dumped = card.model_dump(mode="json", exclude_none=True)
    assert dumped["id"] == "c1"
    for stray in ("concept_id", "definition", "body", "examples"):
        assert stray not in dumped


def test_bare_string_misconception_coerces_to_description() -> None:
    card = PathStructuralCard.model_validate(
        {"id": "c1", "misconceptions": ["Sunlight is the plant's food"]}
    )
    assert card.misconceptions[0].description == "Sunlight is the plant's food"


def test_statement_survives_the_dump_so_the_bridge_can_rename_it() -> None:
    """Regression guard for a silent-data-loss path.

    ``planning.bridge._normalize_page_concept_card_payload`` renames ``statement``
    to ``description`` only when ``description`` is absent from the dict. If the
    dump emitted ``description: None`` the rename would never fire and the
    misconception would be dropped with no error at all. That makes
    ``exclude_none=True`` part of the contract, not a formatting choice.
    """
    card = PathStructuralCard.model_validate(
        {"id": "c1", "misconceptions": [{"statement": "Light is food", "rationale": "drop me"}]}
    )
    dumped = card.model_dump(mode="json", exclude_none=True)
    row = dumped["misconceptions"][0]
    assert row["statement"] == "Light is food"
    assert "description" not in row
    assert "rationale" not in row


# ── the schema the provider actually receives ─────────────────────────────


def test_schema_exposes_typed_definitions_not_free_form_objects() -> None:
    schema = PathStructuralPlan.model_json_schema()
    defs = schema.get("$defs", {})
    assert "PathStructuralSection" in defs
    assert "PathStructuralCard" in defs

    sections = schema["properties"]["sections"]
    assert "$ref" in sections["items"], "sections must reference a typed model"
    assert sections["items"] != {"type": "object"}

    cards = schema["properties"]["cards"]
    assert cards["maxItems"] == 1
    assert "minItems" not in cards, "the lower bound belongs to the context validator"

    section_props = defs["PathStructuralSection"]["properties"]
    assert set(section_props) == {
        "id",
        "role",
        "title",
        "card_id",
        "visual_required",
        "transition_note",
        "components",
    }


def test_schema_descriptions_steer_away_from_slot_id() -> None:
    """On the prompted path, descriptions are the only steering mechanism.

    The model is handed slots carrying both ``slot_id`` and a different ``role``,
    and must map both of its own fields onto ``slot_id``. If these hints are lost
    the original failure is free to recur.
    """
    defs = PathStructuralPlan.model_json_schema()["$defs"]
    section_props = defs["PathStructuralSection"]["properties"]
    assert "slot_id" in section_props["id"]["description"]
    assert "slot_id" in section_props["role"]["description"]
