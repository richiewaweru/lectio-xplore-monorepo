"""Shared ImmutableLessonPacket + LessonLegalitySnapshot fixtures.

Extracted from the retired ``test_contract_hardening.py`` (P11B deleted the
ordinary form-plan ownership contract it tested) so still-live consumers
(teaching-plan semantic review) keep their fixture helpers without pulling in
the deleted ordinary form-plan pipeline.
"""

from __future__ import annotations

from typing import Any

from curriculum.teaching_plan.models import TeachingPlanDraftV2
from print.generation.whole_lesson.legality import LessonLegalitySnapshot, legality_hash
from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)


def packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-harden",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="a1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause"]),
        ],
        limits=LessonLimits(),
        resource_id="lesson",
    )


def make_snapshot(**overrides: Any) -> LessonLegalitySnapshot:
    """Build a hash-valid snapshot for teaching-plan review tests."""
    data: dict[str, Any] = {
        "resource_id": "lesson",
        "catalogue_version": "test",
        "permitted_intents": ["orient", "explain-cause"],
        "excluded_intents": [],
        "typical_by_slot": {
            "orient": ["orient"],
            "explain": ["explain-cause"],
        },
        "permitted_objects": ["prose", "list", "table", "figure"],
        "compatible_objects_by_intent": {
            "orient": ["prose", "figure"],
            "explain-cause": ["prose", "list", "table", "figure"],
        },
    }
    data.update(overrides)
    # Ensure every permitted intent has an explicit compatibility key.
    compat = dict(data.get("compatible_objects_by_intent") or {})
    for intent_id in data.get("permitted_intents") or []:
        compat.setdefault(str(intent_id), [])
    data["compatible_objects_by_intent"] = {
        key: list(value) for key, value in sorted(compat.items())
    }
    data["catalogue_hash"] = legality_hash(data)
    return LessonLegalitySnapshot.model_validate(data)


def five_item_check_packet() -> ImmutableLessonPacket:
    return packet().model_copy(
        update={
            "scope": ScopeContract(
                terminology=["light"],
                must_not_introduce=[
                    {
                        "id": "exclude-1",
                        "statement": "cellular respiration",
                    }
                ],
            ),
            "approved_items": [
                ApprovedItemRef(
                    id=f"approved-mcq-{index}",
                    card_id="card",
                    stem=(
                        f"Why does light change a plant's ability to make food "
                        f"(approved item {index})?"
                    ),
                    options=[
                        {"key": "A", "text": "A"},
                        {"key": "B", "text": "B"},
                    ],
                    correct_key="A",
                )
                for index in range(1, 6)
            ],
            "slots": [
                SlotRecord(
                    slot_id="check",
                    purpose="Check whether the learner can explain the role of light.",
                    typical_intents=["check-understanding"],
                )
            ],
        }
    )


def check_plan(
    *, source_ids: list[str], invalid_context: bool = False
) -> TeachingPlanDraftV2:
    forbidden = " through cellular respiration" if invalid_context else ""
    refs = ["approved_item_ids"] if invalid_context else ["lesson.objective"]
    return TeachingPlanDraftV2(
        learner_title="Why light matters to plant growth",
        arc="Use the two plants to check whether learners can explain why light matters.",
        starting_state=["Learners can compare two plants grown under different conditions."],
        target_state=["Learners can explain how light enables food production."],
        anchor_usage=[{"slot_id": "check", "usage": "Return to the two plants."}],
        sections=[
            {
                "display_title": "Explain the role of light",
                "specific_purpose": "Check causal understanding.",
                "entry_state": ["Learners have compared the plants."],
                "must_establish": ["Light enables the plant to make food."],
                "avoid_repeating": [],
                "bridge_from_previous": None,
                "exit_state": ["Learners can explain why light matters."],
                "blocks": [
                    {
                        "intent": "check-understanding",
                        "brief": (
                            "Return to the two plants and require learners to explain "
                            f"why light changes the plant's ability to make food{forbidden}."
                        ),
                        "evidence_refs": refs,
                        "evidence": (
                            "The objective requires a causal explanation, so this check "
                            "tests the role of light directly."
                        ),
                        "source_question_ids": source_ids,
                        "learner_action": {
                            "action": "select-one",
                            "target": "approved multiple-choice item",
                            "purpose": "Check causal understanding of light.",
                            "expected_evidence": "Correct choice naming light's role",
                            "difficulty": "guided",
                        },
                    }
                ],
            }
        ],
    )
