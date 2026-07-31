from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from core.database.models import LessonProvenanceModel, PathLessonModel, UserModel
from planning.bridge import PathPreparationBlocked, prepare_path_lesson
from planning.models import (
    ComponentSelection,
    PathAnchor,
    PathPlan,
    PathStructuralPlan,
    PrepareLessonRequest,
    SelectedComponent,
    UnitCreate,
)
from planning.service import approve_path, create_unit, persist_path_plan
from v3_blueprint.planning.objective_ownership import hash_path_objective


FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "handoff"
    / "fixtures"
    / "grade4-photosynthesis-path.json"
)


async def _fake_structural_planner(context: dict) -> PathStructuralPlan:
    sections = []
    for index, slot in enumerate(context["slots"]):
        component = slot["allowed_components"][0]
        sections.append(
            {
                "id": slot["slot_id"],
                "title": slot["purpose"][:80],
                "role": slot["slot_id"],
                "card_id": None if slot["slot_id"] in {"orient", "close"} else context["concept_id"],
                "visual_required": slot["visual_required"],
                "transition_note": None if index == 0 else "Build on the preceding fixed slot.",
                "components": [
                    {
                        "slug": component,
                        "purpose": f"Perform the {slot['slot_id']} cognitive job.",
                    }
                ],
            }
        )
    return PathStructuralPlan(
        anchor=PathAnchor(description="A leaf kept in light and a leaf kept in darkness", source="new"),
        cards=[
            {
                "id": context["concept_id"],
                "title": context["title"],
                "objective": context["objective"],
                "prereqs": [],
                "misconceptions": [],
                "no_known_misconceptions": True,
                "opens_by": "Connect to the unit starting knowledge.",
            }
        ],
        sections=sections,
        deviation_request=None,
        objective_concern=None,
    )


async def _fake_component_selector(context: dict) -> ComponentSelection:
    component_id = context["slot"]["allowed_components"][0]
    return ComponentSelection(
        components=[
            SelectedComponent(
                slug=component_id,
                purpose=f"Perform the {context['slot']['slot_id']} cognitive job.",
                reason="Matches the supplied registry cognitive job.",
            )
        ],
        budget_pressure=None,
    )


async def test_prepare_bridge_locks_slots_and_objective_hash(db_session) -> None:
    user = UserModel(id="bridge-owner", email="bridge@example.invalid", name="Bridge")
    db_session.add(user)
    plan = PathPlan.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=UnitCreate(
            title=plan.unit or "Photosynthesis",
            topic=plan.unit or "Photosynthesis",
            subject=plan.subject or "Science",
            grade_level=plan.grade_level or "Grade 4",
            destination_objective=plan.destination_objective or "Destination",
            starting_knowledge=plan.starting_knowledge,
        ),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None

    response, structural_plan = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=_fake_structural_planner,
        component_selector=_fake_component_selector,
    )

    assert response.slots == response.section_roles
    assert [section.role for section in structural_plan.sections] == response.slots
    assert structural_plan.cards[0].objective == lesson.objective
    assert response.objective_hash == hash_path_objective(lesson.objective)
    provenance = await db_session.get(LessonProvenanceModel, response.generation_id)
    assert provenance is not None
    assert provenance.path_lesson_id == lesson.id
    assert provenance.objective_hash == response.objective_hash

    reused, reused_plan = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=_fake_structural_planner,
        component_selector=_fake_component_selector,
    )
    assert reused.reused is True
    assert reused.generation_id == response.generation_id
    assert reused_plan.cards[0].objective == lesson.objective


async def test_prepare_bridge_rejects_objective_rewrite(db_session) -> None:
    user = UserModel(id="bridge-rewrite", email="rewrite@example.invalid", name="Rewrite")
    db_session.add(user)
    plan = PathPlan.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=UnitCreate(
            title="Photosynthesis",
            topic="Photosynthesis",
            subject="Science",
            grade_level="Grade 4",
            destination_objective=plan.destination_objective or "Destination",
            starting_knowledge=plan.starting_knowledge,
        ),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None

    async def rewriting_planner(context: dict) -> PathStructuralPlan:
        generated = await _fake_structural_planner(context)
        generated.cards[0]["objective"] = "A plausible but rewritten objective."
        return generated

    with pytest.raises(PathPreparationBlocked, match="objective"):
        await prepare_path_lesson(
            db_session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(lesson_mode="first_exposure"),
            structural_planner=rewriting_planner,
            component_selector=_fake_component_selector,
        )
