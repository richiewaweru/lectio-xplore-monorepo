from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from core.database.models import GenerationModel, SkeletonShadowRecordModel, UserModel
from generation.v3_studio.dtos import V3InputForm
from v3_blueprint.knowledge_classifier import KnowledgeTypeClassification
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    SectionPlan,
    StructuralPlan,
)
from v3_blueprint.shadow import (
    record_skeleton_shadow,
    shadow_review_csv,
    structural_match_score,
)


def _plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="Explain why light is required for photosynthesis.",
            structure_rationale="Contrast a lit plant with a plant kept in darkness.",
        ),
        anchor=AnchorSpec(
            example="two bean plants",
            reuse_scope="orient, explain, and check",
        ),
        prior_knowledge=["plants need water"],
        sections=[
            SectionPlan(
                id="orient",
                title="Two plants",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="show the two plants")],
            ),
            SectionPlan(
                id="explain",
                title="What light changes",
                role="explain",
                visual_required=False,
                transition_note="Use the two plants to isolate the role of light.",
                components=[
                    ComponentSlot(
                        slug="explanation-block",
                        purpose="explain the evidence from the two plants",
                    )
                ],
            ),
            SectionPlan(
                id="check",
                title="Check",
                role="check",
                visual_required=False,
                transition_note="Test the same idea on a new plant case.",
                components=[ComponentSlot(slug="quiz-check", purpose="diagnose the idea")],
            ),
        ],
        question_plan=[],
        answer_key_style="brief_explanations",
    )


def _form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 4",
        subject="Biology",
        duration_minutes=45,
        resource_type="lesson",
        topic="Photosynthesis",
        subtopics=["light"],
        prior_knowledge="Plants need water.",
        outcome="Explain why light is required for photosynthesis.",
        struggle="Learners think soil is plant food.",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
        free_text="",
    )


@pytest.mark.asyncio
async def test_shadow_record_persists_classifier_separately_from_skeleton_fit(
    db_session_factory,
) -> None:
    classification = KnowledgeTypeClassification(
        primary_knowledge_type="conceptual",
        secondary_demand=None,
        confidence="medium",
        success_test="The learner judges a new no-light case.",
        note="Review the classification independently.",
    )
    async with db_session_factory() as session:
        session.add(UserModel(id="teacher-shadow", email="shadow@example.com"))
        session.add(
            GenerationModel(
                id="generation-shadow-1",
                user_id="teacher-shadow",
                subject="Biology",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
            )
        )
        await session.commit()

    with patch(
        "v3_blueprint.shadow.classify_knowledge_type",
        new=AsyncMock(return_value=classification),
    ):
        await record_skeleton_shadow(
            generation_id="generation-shadow-1",
            plan=_plan(),
            form=_form(),
            session_factory=db_session_factory,
        )

    async with db_session_factory() as session:
        record = await session.scalar(select(SkeletonShadowRecordModel))
    assert record is not None
    assert record.classifier_type == "conceptual"
    assert record.classifier_confidence == "medium"
    assert record.classifier_note == "Review the classification independently."
    assert record.skeleton_id == "conceptual.first_exposure"
    assert record.current_roles == ["orient", "explain", "check"]
    assert record.expanded_slots == ["orient", "explain", "contrast", "check"]
    assert record.reviewer_preference is None

    csv_body = await shadow_review_csv(
        user_id="teacher-shadow",
        session_factory=db_session_factory,
    )
    assert "classifier_confidence" in csv_body
    assert "wrong_classification" in csv_body
    assert "conceptual.first_exposure" in csv_body
    assert "Review the classification independently." in csv_body


def test_structural_match_score_uses_ordered_role_overlap() -> None:
    assert structural_match_score(
        ["orient", "explain", "check"],
        ["orient", "explain", "contrast", "check"],
    ) == 0.75
    assert structural_match_score(["check"], ["orient", "check"]) == 0.5
