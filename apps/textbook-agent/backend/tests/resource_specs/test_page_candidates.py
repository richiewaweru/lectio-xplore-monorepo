"""Tests for native page-block planning contracts and candidate resolver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resource_specs.candidates import (
    CandidateConfigurationError,
    resolve_block_candidates,
)
from resource_specs.loader import get_spec, load_all_specs
from v3_blueprint.planning.models import (
    PlannedBlock,
    SectionBlockPlan,
    SectionPlan,
    StructuralPlan,
    adapt_legacy_structural_plan,
)
from v3_blueprint.skeletons import load_skeleton_catalog

BACKEND = Path(__file__).resolve().parents[2]
CONTRACTS = BACKEND / "contracts" / "lectio-page"
FIRST_SLICE_SLOTS = ("orient", "explain", "contrast", "confront", "check")


@pytest.fixture(scope="module")
def catalogues() -> tuple[dict, dict]:
    intents = json.loads((CONTRACTS / "intent-catalogue.v1.json").read_text(encoding="utf-8"))[
        "intents"
    ]
    objects = json.loads((CONTRACTS / "object-catalogue.v1.json").read_text(encoding="utf-8"))[
        "objects"
    ]
    return intents, objects


def test_legacy_structural_plan_parses_with_default_version() -> None:
    payload = {
        "lesson_mode": "first_exposure",
        "lesson_intent": {
            "goal": "Explain why plants need light to make food.",
            "structure_rationale": "Conceptual first exposure needs contrast and check.",
        },
        "anchor": {
            "example": "covered vs uncovered leaf",
            "reuse_scope": "Used in explain and contrast sections.",
        },
        "prior_knowledge": ["plants make food"],
        "sections": [
            {
                "id": "orient",
                "title": "Why light matters",
                "role": "orient",
                "visual_required": False,
                "transition_note": None,
                "components": [
                    {"slug": "hook-hero", "purpose": "Open with a concrete leaf contrast."}
                ],
            }
        ],
        "question_plan": [],
        "answer_key_style": "brief_explanations",
    }
    plan = StructuralPlan.model_validate(payload)
    assert plan.document_contract_version == 1
    assert plan.sections[0].blocks == []
    adapted = adapt_legacy_structural_plan(payload, source="test")
    assert adapted.document_contract_version == 1


def test_section_plan_accepts_additive_blocks() -> None:
    section = SectionPlan.model_validate(
        {
            "id": "explain",
            "title": "What light changes",
            "role": "explain",
            "visual_required": False,
            "components": [
                {"slug": "explanation-block", "purpose": "State the mechanism."}
            ],
            "blocks": [
                {
                    "id": "b1",
                    "position": 0,
                    "intent": "explain-cause",
                    "object": "prose",
                    "evidence": "slot needs causal mechanism",
                    "brief": "Explain why light is the differing condition.",
                }
            ],
        }
    )
    assert len(section.blocks) == 1
    assert section.blocks[0].object == "prose"


def test_planned_block_rejects_heading() -> None:
    with pytest.raises(ValueError, match="section.title"):
        PlannedBlock.model_validate(
            {
                "id": "h1",
                "position": 0,
                "intent": "orient",
                "object": "heading",
                "evidence": "x",
                "brief": "y",
            }
        )


def test_section_block_plan_orders_positions() -> None:
    with pytest.raises(ValueError, match="position"):
        SectionBlockPlan.model_validate(
            {
                "blocks": [
                    {
                        "id": "b1",
                        "position": 1,
                        "intent": "orient",
                        "object": "prose",
                        "evidence": "e",
                        "brief": "b",
                    }
                ]
            }
        )


def test_lesson_vocabulary_loads() -> None:
    load_all_specs.cache_clear() if hasattr(load_all_specs, "cache_clear") else None
    # reload registry
    from resource_specs import loader

    loader._REGISTRY.clear()
    loader.load_all_specs()
    spec = get_spec("lesson")
    assert spec.vocabulary is not None
    assert "explain-cause" in spec.vocabulary.intents.core
    assert "prose" in spec.vocabulary.objects.allowed
    assert "heading" in spec.vocabulary.objects.allowed


def test_first_slice_slots_have_nonempty_compatible_candidates(catalogues) -> None:
    intents, objects = catalogues
    from resource_specs import loader

    loader._REGISTRY.clear()
    loader.load_all_specs()
    spec = get_spec("lesson")
    catalog = load_skeleton_catalog()

    for slot_id in FIRST_SLICE_SLOTS:
        slot = dict(catalog.slots[slot_id])
        slot["slot_id"] = slot_id
        matrix = resolve_block_candidates(
            resource_spec=spec,
            skeleton_slot=slot,
            intent_catalogue=intents,
            object_catalogue=objects,
        )
        assert matrix, slot_id
        for intent in matrix:
            assert intent.id not in {"state-goal", "transfer", "investigate"}
            assert intent.record.get("selectable", True) is not False
            for obj in intent.objects:
                assert obj.id != "heading"
                assert obj.id != "answer-key"
                valid = intent.record.get("valid_objects", [])
                assert obj.id in valid


def test_empty_intersection_raises(catalogues) -> None:
    intents, objects = catalogues
    from resource_specs import loader

    loader._REGISTRY.clear()
    loader.load_all_specs()
    spec = get_spec("lesson")
    with pytest.raises(CandidateConfigurationError, match="No page-block candidates"):
        resolve_block_candidates(
            resource_spec=spec,
            skeleton_slot={
                "slot_id": "empty",
                "candidate_intents": {"core": ["transfer"], "optional": []},
            },
            intent_catalogue=intents,
            object_catalogue=objects,
        )


def test_heading_never_appears_in_candidates(catalogues) -> None:
    intents, objects = catalogues
    from resource_specs import loader

    loader._REGISTRY.clear()
    loader.load_all_specs()
    spec = get_spec("lesson")
    catalog = load_skeleton_catalog()
    for slot_id in FIRST_SLICE_SLOTS:
        slot = dict(catalog.slots[slot_id])
        slot["slot_id"] = slot_id
        matrix = resolve_block_candidates(
            resource_spec=spec,
            skeleton_slot=slot,
            intent_catalogue=intents,
            object_catalogue=objects,
            implemented_objects={"prose", "list", "table", "figure", "worked-example", "questions", "heading"},
        )
        for intent in matrix:
            assert all(obj.id != "heading" for obj in intent.objects)
