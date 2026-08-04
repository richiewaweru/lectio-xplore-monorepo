from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    PathLessonModel,
    UserModel,
)
from generation.path_preparation import enforce_path_owned_card_objective
from planning.bridge import PathPreparationBlocked, prepare_path_lesson
from planning.models import (
    ComponentSelection,
    GroupVoice,
    LessonActualWriteRequest,
    PathAnchor,
    PathPlan,
    PathStructuralPlan,
    PrepareLessonRequest,
    SelectedComponent,
    ShapeDeviationCreateRequest,
    UnitCreate,
    UnitGroupInput,
    UnitGroupsWriteRequest,
)
from planning.outcomes import record_lesson_actual
from planning.schedule import write_groups
from planning.service import approve_path, create_unit, persist_path_plan
from planning.shapes import decide_shape_deviation, request_shape_deviation
from v3_blueprint.planning.objective_ownership import hash_path_objective
from v3_blueprint.planning.persistence import load_chunked_state


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
                "title": f"{slot['purpose']} — an advisory explanation that may exceed the display limit",
                "role": slot["slot_id"],
                "card_id": None if slot["slot_id"] in {"orient", "close"} else context["concept_id"],
                "visual_required": slot["visual_required"],
                "transition_note": (
                    "The model may provide a useful but overly detailed transition note that "
                    "explains how the prior section establishes knowledge for the next cognitive "
                    "move without changing the lesson structure or objective."
                ),
                "components": [
                    {
                        "slug": component,
                        "purpose": f"Perform the {slot['slot_id']} cognitive job.",
                        "reason": "The selector's advisory rationale is not persisted.",
                    }
                ],
            }
        )
    return PathStructuralPlan(
        anchor=PathAnchor(
            description=(
                "A leaf kept in bright light beside another leaf kept in darkness, with both "
                "leaves observed closely before and after the investigation as one shared anchor"
            ),
            source="new",
        ),
        cards=[
            {
                "id": context["concept_id"],
                "title": context["title"],
                "objective": context["objective"],
                "prereqs": [],
                "misconceptions": [],
                "no_known_misconceptions": True,
                "opens_by": None,
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
    assert structural_plan.cards[0].opens_by == ""
    assert structural_plan.sections[0].transition_note is None
    assert all(
        section.transition_note is None or len(section.transition_note) <= 120
        for section in structural_plan.sections
    )
    assert all(len(section.title) <= 80 for section in structural_plan.sections)
    assert len(structural_plan.anchor.example) <= 100
    assert response.objective_hash == hash_path_objective(lesson.objective)
    provenance = await db_session.get(LessonProvenanceModel, response.generation_id)
    assert provenance is not None
    assert provenance.path_lesson_id == lesson.id
    assert provenance.objective_hash == response.objective_hash
    assert provenance.path_lesson_revision == lesson.revision
    assert provenance.lesson_mode == "first_exposure"
    assert len(provenance.preparation_key or "") == 64
    generation = await db_session.get(GenerationModel, response.generation_id)
    assert generation is not None
    assert generation.mode == "v3"
    assert generation.status == "awaiting_review"
    state = await load_chunked_state(response.generation_id, db_session)
    assert state["stage"] == "awaiting_review"
    assert state["path_prepared"] is True
    assert state["structural_plan"]["cards"][0]["objective"] == lesson.objective
    card = await db_session.get(
        ConceptCardModel,
        f"{response.generation_id}:{lesson.concept_id}",
    )
    assert card is not None
    assert card.canonical_concept_id == lesson.concept_id
    await enforce_path_owned_card_objective(
        db_session,
        pack_id=response.generation_id,
        objective=lesson.objective,
    )
    with pytest.raises(ValueError, match="cannot rewrite"):
        await enforce_path_owned_card_objective(
            db_session,
            pack_id=response.generation_id,
            objective="A rewritten objective",
        )

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
    with pytest.raises(ValueError, match="active and owned"):
        await prepare_path_lesson(
            db_session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(
                lesson_mode="first_exposure",
                group_ids=["not-a-persisted-group"],
            ),
            structural_planner=_fake_structural_planner,
            component_selector=_fake_component_selector,
        )

    regenerated, _ = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=_fake_structural_planner,
        component_selector=_fake_component_selector,
        regenerate=True,
        regeneration_reason="Teacher requested a fresh preparation.",
    )
    assert regenerated.generation_id != response.generation_id
    assert regenerated.reused is False
    replacement = await db_session.get(LessonProvenanceModel, regenerated.generation_id)
    assert replacement is not None
    assert replacement.supersedes_pack_id == response.generation_id
    assert replacement.regeneration_reason == "Teacher requested a fresh preparation."
    await db_session.refresh(provenance)
    assert provenance.invalidated_at is not None
    assert lesson.pack_id == regenerated.generation_id


async def test_later_preparation_receives_actuals_as_explicit_advisory_context(db_session) -> None:
    user = UserModel(id="bridge-actual", email="bridge-actual@example.invalid", name="Actual")
    db_session.add(user)
    plan = PathPlan.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=UnitCreate(
            title="Photosynthesis", topic="Photosynthesis", subject="Science",
            grade_level="Grade 4", destination_objective=plan.destination_objective or "Destination",
            starting_knowledge=plan.starting_knowledge,
        ),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lessons = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    assert len(lessons) >= 2
    first, second = lessons[:2]
    await record_lesson_actual(
        db_session,
        unit=unit,
        version=version,
        lesson=first,
        user_id=user.id,
        request=LessonActualWriteRequest(
            path_version_id=version.id, path_revision=version.revision,
            lesson_revision=first.revision, actual_revision=0, status="partial",
            pace="slower", established_concepts=[first.must_establish[0]],
            unresolved_misconceptions=["soil-food"],
            teacher_note="Use a recovery prompt before new material.",
        ),
    )
    captured: dict = {}

    async def capture(context: dict) -> PathStructuralPlan:
        captured.update(context)
        return await _fake_structural_planner(context)

    await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=second,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=capture,
        component_selector=_fake_component_selector,
    )

    assert captured["lesson_actuals"] == [
        {
            "path_lesson_id": first.id,
            "status": "partial",
            "taught": True,
            "pace": "slower",
            "established_concepts": [first.must_establish[0]],
            "unresolved_misconceptions": ["soil-food"],
            "anchor_used": None,
            "teacher_note": "Use a recovery prompt before new material.",
            "recorded_at": captured["lesson_actuals"][0]["recorded_at"],
            "advisory": True,
        }
    ]
    assert second.objective == lessons[1].objective


async def test_approved_shape_deviation_survives_safe_regeneration(db_session) -> None:
    user = UserModel(id="bridge-shape", email="bridge-shape@example.invalid", name="Shape")
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
        .where(
            PathLessonModel.path_version_id == version.id,
            PathLessonModel.primary_knowledge_type == "conceptual",
        )
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None
    deviation = await request_shape_deviation(
        db_session,
        lesson=lesson,
        request=ShapeDeviationCreateRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            lesson_revision=lesson.revision,
            lesson_mode="first_exposure",
            operation="remove",
            target_slot="orient",
            reason="Make room for misconception repair without scope drift.",
        ),
    )
    await decide_shape_deviation(
        db_session,
        lesson=lesson,
        deviation_id=deviation.id,
        approved=True,
        decided_by=user.id,
    )

    first, first_plan = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=_fake_structural_planner,
        component_selector=_fake_component_selector,
    )
    regenerated, regenerated_plan = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=_fake_structural_planner,
        component_selector=_fake_component_selector,
        regenerate=True,
        regeneration_reason="Refresh after teacher review.",
    )

    assert "orient" not in [section.role for section in first_plan.sections]
    assert "orient" not in [section.role for section in regenerated_plan.sections]
    first_provenance = await db_session.get(LessonProvenanceModel, first.generation_id)
    replacement = await db_session.get(LessonProvenanceModel, regenerated.generation_id)
    assert first_provenance is not None and replacement is not None
    assert replacement.deviations_approved == first_provenance.deviations_approved
    assert replacement.deviations_applied == first_provenance.deviations_applied
    assert replacement.deviations_applied[0]["target_slot"] == "orient"


async def test_prepare_bridge_uses_persisted_groups_and_one_shared_pack(db_session) -> None:
    user = UserModel(id="bridge-groups", email="bridge-groups@example.invalid", name="Groups")
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
    groups = await write_groups(
        db_session,
        unit=unit,
        request=UnitGroupsWriteRequest(
            groups_revision=unit.groups_revision,
            groups=[
                UnitGroupInput(
                    label="Support",
                    profile="support",
                    description="More modelling and guided practice.",
                    voice=GroupVoice(register_name="simple", tone="encouraging"),
                ),
                UnitGroupInput(
                    label="Core",
                    profile="core",
                    description="The main class route.",
                    voice=GroupVoice(register_name="balanced", tone="neutral"),
                ),
                UnitGroupInput(
                    label="Extension",
                    profile="extension",
                    description="Independent transfer and application.",
                    voice=GroupVoice(register_name="formal", tone="direct"),
                ),
            ],
        ),
    )
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None

    group_ids = [group["id"] for group in groups["groups"]]
    response, _plan = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(
            lesson_mode="first_exposure",
            group_ids=group_ids,
        ),
        structural_planner=_fake_structural_planner,
        component_selector=_fake_component_selector,
    )

    generation = await db_session.get(GenerationModel, response.generation_id)
    assert generation is not None
    assert generation.pack_id is not None
    pack = await db_session.get(LearningPackModel, generation.pack_id)
    assert pack is not None
    assert pack.learning_job_type == "xplore_variants"
    assert pack.resource_count == 3
    pack_plan = json.loads(pack.pack_plan_json)
    assert pack_plan["shared_quiz"] is True
    assert [resource["label"] for resource in pack_plan["resources"]] == [
        "Support",
        "Core",
        "Extension",
    ]
    state = await load_chunked_state(response.generation_id, db_session)
    assert state["pack_id"] == pack.id
    assert [variant["label"] for variant in state["variants"]] == [
        "Support",
        "Core",
        "Extension",
    ]
    variant_plans = state["variant_structural_plans"]
    support_roles = [section["role"] for section in variant_plans["Support"]["sections"]]
    core_roles = [section["role"] for section in variant_plans["Core"]["sections"]]
    extension_roles = [section["role"] for section in variant_plans["Extension"]["sections"]]
    assert support_roles != core_roles
    assert extension_roles != core_roles
    assert all(roles.count("check") == 1 for roles in (support_roles, core_roles, extension_roles))
    assert {
        variant_plans[label]["lesson_intent"]["goal"]
        for label in ("Support", "Core", "Extension")
    } == {lesson.objective}
    card = await db_session.get(
        ConceptCardModel,
        f"{pack.id}:{lesson.concept_id}",
    )
    assert card is not None
    assert card.pack_id == pack.id
    provenance = await db_session.get(LessonProvenanceModel, response.generation_id)
    assert provenance is not None
    assert provenance.group_ids == sorted(group_ids)
    assert "support.high.drop_independent" in provenance.toggles_applied
    assert "support.low.add_transfer" in provenance.toggles_applied


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
