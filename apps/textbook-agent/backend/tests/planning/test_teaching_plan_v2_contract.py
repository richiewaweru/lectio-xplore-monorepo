from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanDraftV2,
    materialize_teaching_plan,
)

LEGACY_PLAN = {
    "teaching_plan_id": "plan-identity-1",
    "revision": 1,
    "preparation_hash": "upstream-input-hash",
    "approval_status": None,
    "arc": "Explain water movement",
    "misconception_focus_ids": ["water-cycle-order"],
    "anchor_usage": [{"slot_id": "orient", "usage": "Observe a covered leaf."}],
    "sections": [
        {
            "slot_id": "orient",
            "specific_purpose": "Connect the observation to the question.",
            "transition": "Now trace the water.",
            "blocks": [
                {
                    "id": "orient-b1",
                    "position": 0,
                    "intent": "orient",
                    "brief": "Describe what the learner sees.",
                    "evidence": "A relevant observation.",
                }
            ],
        }
    ],
}

LEGACY_HASH = "79121d3b333a001c5023de3f5d7959066002dd5615b62c9b9e9e11ac13013698"


def _v2_plan_payload() -> dict:
    return {
        "contract_version": 2,
        "learner_title": "Follow water from leaf to cloud",
        "arc": "Observe, explain, and transfer the water cycle.",
        "starting_state": ["Learner can name visible water sources."],
        "target_state": ["Learner explains how water changes and moves."],
        "anchor_usage": [{"slot_id": "orient", "usage": "Return to the covered leaf."}],
        "misconception_focus_ids": ["water-cycle-order"],
        "sections": [
            {
                "slot_id": "orient",
                "specific_purpose": "Build from an observation.",
                "display_title": "Notice where water appears",
                "entry_state": ["Learner can name visible water sources."],
                "must_establish": ["Water can appear on a covered leaf."],
                "avoid_repeating": [],
                "bridge_from_previous": None,
                "exit_state": ["Learner has an observation to explain."],
                "blocks": [],
            },
            {
                "slot_id": "explain",
                "specific_purpose": "Explain the observation with a model.",
                "display_title": "Trace water through the cycle",
                "entry_state": ["Learner has an observation to explain."],
                "must_establish": ["Water can evaporate, condense, and return."],
                "avoid_repeating": ["Naming visible water sources."],
                "bridge_from_previous": "Use the leaf observation to ask where its droplets began.",
                "exit_state": ["Learner explains how water changes and moves."],
                "blocks": [],
            },
        ],
    }


def _v2_draft_payload() -> dict:
    payload = _v2_plan_payload()
    payload.pop("contract_version")
    payload.pop("anchor_usage")
    payload.pop("misconception_focus_ids")
    for section in payload["sections"]:
        section.pop("slot_id")
        section.pop("blocks")
    return payload


def test_legacy_approved_plan_hash_and_serialized_bytes_are_preserved() -> None:
    plan = TeachingPlan.model_validate(LEGACY_PLAN)
    assert plan.contract_version == 1
    serialized = plan.model_dump(mode="json")
    assert "contract_version" not in serialized
    assert "learner_title" not in serialized
    assert "starting_state" not in serialized
    assert "target_state" not in serialized
    assert all("display_title" not in section for section in serialized["sections"])
    assert teaching_plan_content_hash(plan) == LEGACY_HASH


def test_v2_draft_requires_approved_refs_for_sourcebook_needs() -> None:
    payload = _v2_draft_payload()
    payload["sections"][1]["blocks"] = [
        {
            "intent": "model",
            "brief": "Show one worked example.",
            "evidence": "Learner follows the example.",
            "sourcebook_needs": ["a worked example"],
            "sourcebook_refs": [],
        }
    ]

    with pytest.raises(ValidationError, match="sourcebook_needs require approved sourcebook_refs"):
        TeachingPlanDraftV2.model_validate(payload)


@pytest.mark.parametrize(
    ("field_path", "replacement"),
    [
        (("learner_title",), "Trace a different question"),
        (("starting_state",), ["A changed starting understanding."]),
        (("target_state",), ["A changed target understanding."]),
        (("sections", 0, "display_title"), "A different section title"),
        (("sections", 0, "entry_state"), ["A different assumed understanding."]),
        (("sections", 0, "must_establish"), ["A different required understanding."]),
        (("sections", 0, "avoid_repeating"), ["A previously established idea."]),
        (("sections", 1, "bridge_from_previous"), "Connect through a different idea."),
        (("sections", 0, "exit_state"), ["A different downstream guarantee."]),
    ],
)
def test_each_new_pedagogical_field_changes_v2_hash(field_path, replacement) -> None:
    original_payload = _v2_plan_payload()
    original = TeachingPlan.model_validate(original_payload)
    changed_payload = deepcopy(original_payload)
    cursor = changed_payload
    for part in field_path[:-1]:
        cursor = cursor[part]
    cursor[field_path[-1]] = replacement
    changed = TeachingPlan.model_validate(changed_payload)
    assert teaching_plan_content_hash(changed) != teaching_plan_content_hash(original)


@pytest.mark.parametrize(
    ("field_path", "bad_value"),
    [
        (("learner_title",), "  "),
        (("starting_state",), []),
        (("target_state",), ["", "A useful goal"]),
        (("sections", 0, "display_title"), " "),
        (("sections", 0, "entry_state"), []),
        (("sections", 0, "must_establish"), ["Same", " Same "]),
        (("sections", 0, "avoid_repeating"), [" "]),
        (("sections", 1, "bridge_from_previous"), "  "),
        (("sections", 0, "exit_state"), [" "]),
    ],
)
def test_v2_rejects_blank_empty_or_duplicate_continuity(field_path, bad_value) -> None:
    payload = deepcopy(_v2_plan_payload())
    cursor = payload
    for part in field_path[:-1]:
        cursor = cursor[part]
    cursor[field_path[-1]] = bad_value
    with pytest.raises(ValidationError):
        TeachingPlan.model_validate(payload)


@pytest.mark.parametrize(
    ("field_path",),
    [
        (("learner_title",),),
        (("starting_state",),),
        (("target_state",),),
        (("sections", 0, "display_title"),),
        (("sections", 0, "entry_state"),),
        (("sections", 0, "must_establish"),),
        (("sections", 0, "avoid_repeating"),),
        (("sections", 0, "bridge_from_previous"),),
        (("sections", 0, "exit_state"),),
    ],
)
def test_v2_rejects_missing_continuity_fields(field_path) -> None:
    payload = deepcopy(_v2_plan_payload())
    cursor = payload
    for part in field_path[:-1]:
        cursor = cursor[part]
    cursor.pop(field_path[-1])
    with pytest.raises(ValidationError):
        TeachingPlan.model_validate(payload)


@pytest.mark.parametrize(
    ("field_path",),
    [
        (("learner_title",),),
        (("starting_state",),),
        (("target_state",),),
        (("sections", 0, "display_title"),),
        (("sections", 0, "entry_state"),),
        (("sections", 0, "must_establish"),),
        (("sections", 0, "avoid_repeating"),),
        (("sections", 0, "bridge_from_previous"),),
        (("sections", 0, "exit_state"),),
    ],
)
def test_v2_generated_draft_requires_enriched_fields(field_path) -> None:
    payload = _v2_draft_payload()
    cursor = payload
    for part in field_path[:-1]:
        cursor = cursor[part]
    cursor.pop(field_path[-1])
    with pytest.raises(ValidationError):
        TeachingPlanDraftV2.model_validate(payload)


def test_v2_generated_draft_rejects_unknown_fields() -> None:
    payload = _v2_draft_payload()
    payload["native_component"] = "card"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TeachingPlanDraftV2.model_validate(payload)


@pytest.mark.parametrize(
    ("section_index", "bridge_value"),
    [(0, "Unexpected opening bridge."), (1, None)],
)
def test_v2_bridge_shape_requires_null_first_and_meaningful_subsequent(
    section_index: int,
    bridge_value: str | None,
) -> None:
    payload = deepcopy(_v2_plan_payload())
    payload["sections"][section_index]["bridge_from_previous"] = bridge_value
    with pytest.raises(ValidationError, match="bridge_from_previous"):
        TeachingPlan.model_validate(payload)


def test_v2_section_slots_are_unique_and_anchor_ownership_is_exact() -> None:
    payload = deepcopy(_v2_plan_payload())
    payload["sections"][1]["slot_id"] = "orient"
    with pytest.raises(ValidationError, match="slot_ids must be unique"):
        TeachingPlan.model_validate(payload)

    payload = deepcopy(_v2_plan_payload())
    payload["anchor_usage"][0]["slot_id"] = "foreign-slot"
    with pytest.raises(ValidationError, match="belong to a Teaching Plan section"):
        TeachingPlan.model_validate(payload)


def test_materialization_emits_v2_fields_and_hashes_them() -> None:
    draft = TeachingPlanDraftV2.model_validate(_v2_draft_payload())
    plan = materialize_teaching_plan(
        draft,
        slot_ids=["orient", "explain"],
        teaching_plan_id="v2-plan",
        revision=2,
        preparation_hash="prep-v2",
    )
    assert plan.contract_version == 2
    assert plan.learner_title == "Follow water from leaf to cloud"
    assert plan.sections[0].slot_id == "orient"
    assert plan.sections[1].slot_id == "explain"
    assert plan.sections[0].bridge_from_previous is None
    assert plan.sections[1].bridge_from_previous
    serialized = plan.model_dump(mode="json")
    assert serialized["contract_version"] == 2
    assert serialized["sections"][0]["must_establish"] == ["Water can appear on a covered leaf."]
    assert teaching_plan_content_hash(plan) == teaching_plan_content_hash(serialized)


def test_v2_materialization_rejects_duplicate_or_foreign_slot_ownership() -> None:
    draft_payload = _v2_draft_payload()
    draft_payload["anchor_usage"] = [{"slot_id": "foreign", "usage": "Anchor."}]
    draft = TeachingPlanDraftV2.model_validate(draft_payload)
    with pytest.raises(ValueError, match="anchor_usage slot_id"):
        materialize_teaching_plan(draft, slot_ids=["orient", "explain"])

    draft = TeachingPlanDraftV2.model_validate(_v2_draft_payload())
    with pytest.raises(ValueError, match="slot_ids must be unique"):
        materialize_teaching_plan(draft, slot_ids=["orient", "orient"])

    with pytest.raises(ValueError, match="surrounding whitespace"):
        materialize_teaching_plan(draft, slot_ids=["orient ", "explain"])
