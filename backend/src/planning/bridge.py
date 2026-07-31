from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from contracts.lectio import get_component_card
from planning.agents import run_component_selector, run_path_structural_planner
from planning.models import (
    ComponentSelection,
    PathStructuralPlan,
    PrepareLessonRequest,
    PreparedLessonResponse,
)
from v3_blueprint.planning.models import (
    AnchorSpec,
    ConceptCard,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
)
from v3_blueprint.planning.objective_ownership import ObjectiveOwnership, ObjectiveOwnershipError
from v3_blueprint.skeletons import SkeletonPreviewRequest, load_skeleton_catalog


class PathPreparationBlocked(ValueError):
    pass


StructuralPlanner = Callable[[dict[str, Any]], Awaitable[PathStructuralPlan]]
ComponentSelector = Callable[[dict[str, Any]], Awaitable[ComponentSelection]]


def _build_structural_plan(
    *,
    generated: PathStructuralPlan,
    lesson: PathLessonModel,
    unit: UnitModel,
    lesson_mode: str,
    slots: list[str],
    selected_components: dict[str, list[str]],
) -> StructuralPlan:
    if generated.deviation_request is not None:
        raise PathPreparationBlocked("A skeleton deviation requires teacher approval")
    if generated.objective_concern:
        raise PathPreparationBlocked(f"Structural planner objective concern: {generated.objective_concern}")
    if len(generated.cards) != 1:
        raise PathPreparationBlocked("Path preparation must produce exactly one concept card")
    card = ConceptCard.model_validate(generated.cards[0])
    ownership = ObjectiveOwnership.from_path_objective(lesson.objective)
    try:
        ownership.verify_generated_objective(card.objective)
    except ObjectiveOwnershipError as exc:
        raise PathPreparationBlocked(str(exc)) from exc
    if card.id != lesson.concept_id:
        raise PathPreparationBlocked("Prepared card must retain the canonical concept ID")

    sections = [SectionPlan.model_validate(section) for section in generated.sections]
    roles = [section.role for section in sections]
    if roles != slots:
        raise PathPreparationBlocked(
            f"Prepared section roles must match skeleton slots exactly: expected {slots}, got {roles}"
        )
    if any(section.id != role for section, role in zip(sections, slots, strict=True)):
        raise PathPreparationBlocked("Prepared section IDs must equal their fixed slot IDs")
    for section in sections:
        actual = [component.slug for component in section.components]
        if actual != selected_components[section.role]:
            raise PathPreparationBlocked(
                f"Section {section.role!r} components differ from the component selector output"
            )

    check = next(section for section in sections if section.role == "check")
    plan = StructuralPlan(
        lesson_mode=lesson_mode,
        lesson_intent=LessonIntent(
            goal=lesson.objective,
            structure_rationale="Path objective and skeleton slots are fixed; content awaits teacher review.",
        ),
        anchor=AnchorSpec(
            example=generated.anchor.description,
            reuse_scope="Reuse this anchor across the fixed path lesson slots.",
        ),
        prior_knowledge=list(unit.starting_knowledge or []),
        cards=[card],
        sections=sections,
        question_plan=[
            QPlanItem(
                question_id="q-check-1",
                section_id=check.id,
                temperature="cold",
            )
        ],
        answer_key_style="brief_explanations",
    )
    try:
        ownership.verify_generated_objective(plan.cards[0].objective)
    except ObjectiveOwnershipError as exc:
        raise PathPreparationBlocked(str(exc)) from exc
    return plan


async def prepare_path_lesson(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
    request: PrepareLessonRequest,
    structural_planner: StructuralPlanner = run_path_structural_planner,
    component_selector: ComponentSelector = run_component_selector,
) -> tuple[PreparedLessonResponse, StructuralPlan]:
    if version.status != "approved":
        raise PathPreparationBlocked("Path must be approved before lesson preparation")
    if lesson.skipped:
        raise PathPreparationBlocked("Skipped path lessons cannot be prepared")
    if lesson.pack_id:
        generation = await session.get(GenerationModel, lesson.pack_id)
        provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
        if generation is not None and provenance is not None:
            if provenance.objective_hash != lesson.objective_hash:
                raise PathPreparationBlocked("Existing prepared pack has a stale objective hash")
            plan = StructuralPlan.model_validate_json(generation.planning_spec_json or "{}")
            slots = [section.role for section in plan.sections]
            return (
                PreparedLessonResponse(
                    generation_id=generation.id,
                    path_lesson_id=lesson.id,
                    objective=lesson.objective,
                    objective_hash=lesson.objective_hash,
                    skeleton_id=provenance.skeleton_id or "",
                    skeleton_version=provenance.skeleton_version or 0,
                    slots=slots,
                    section_roles=slots,
                    status="planning_review",
                    reused=True,
                ),
                plan,
            )

    catalog = load_skeleton_catalog()
    preview = catalog.preview(
        SkeletonPreviewRequest(
            objective=lesson.objective,
            lesson_mode=request.lesson_mode,
            misconception_count=0,
            group_profiles=["core"],
        ),
        knowledge_type=lesson.primary_knowledge_type,
    )
    slots = [slot.slot_id for slot in preview.variants[0].slots]
    component_selections: dict[str, ComponentSelection] = {}
    for slot in preview.variants[0].slots:
        registry_cards = [
            card
            for component_id in slot.allowed_components
            if (card := get_component_card(component_id)) is not None
        ]
        selection = await component_selector(
            {
                "concept_id": lesson.concept_id,
                "objective": lesson.objective,
                "primary_knowledge_type": lesson.primary_knowledge_type,
                "slot": slot.model_dump(mode="json"),
                "component_registry_cards": registry_cards,
                "component_budget": min(4, len(slot.allowed_components)),
                "max_per_section": 4,
            }
        )
        selected_slugs = [component.slug for component in selection.components]
        if not selected_slugs or not set(selected_slugs).issubset(set(slot.allowed_components)):
            raise PathPreparationBlocked(
                f"Component selector returned an invalid selection for slot {slot.slot_id!r}"
            )
        component_selections[slot.slot_id] = selection
    fixed_context = {
        "concept_id": lesson.concept_id,
        "title": lesson.title,
        "objective": lesson.objective,
        "objective_hash": lesson.objective_hash,
        "primary_knowledge_type": lesson.primary_knowledge_type,
        "secondary_demand": lesson.secondary_demand,
        "slots": [slot.model_dump(mode="json") for slot in preview.variants[0].slots],
        "component_selections": {
            slot_id: selection.model_dump(mode="json")
            for slot_id, selection in component_selections.items()
        },
        "scope_contract": version.source_plan_json.get("scope_contract", {}),
        "prior_established": list(unit.starting_knowledge or []),
        "external_prerequisites": list(lesson.external_prerequisites or []),
        "group_ids": request.group_ids,
    }
    generated = await structural_planner(fixed_context)
    plan = _build_structural_plan(
        generated=generated,
        lesson=lesson,
        unit=unit,
        lesson_mode=request.lesson_mode,
        slots=slots,
        selected_components={
            slot_id: [component.slug for component in selection.components]
            for slot_id, selection in component_selections.items()
        },
    )

    generation_id = str(uuid.uuid4())
    generation = GenerationModel(
        id=generation_id,
        user_id=unit.owner_id,
        subject=unit.subject,
        context=f"Prepared from path lesson {lesson.id}",
        mode="balanced",
        status="planning_review",
        requested_template_id="guided-concept-path",
        resolved_template_id="guided-concept-path",
        requested_preset_id="default",
        resolved_preset_id="default",
        section_count=len(plan.sections),
        planning_spec_json=plan.model_dump_json(),
    )
    session.add(generation)
    session.add(
        LessonProvenanceModel(
            pack_id=generation_id,
            concept_id=lesson.concept_id,
            path_version_id=version.id,
            path_lesson_id=lesson.id,
            objective_hash=lesson.objective_hash,
            skeleton_id=preview.skeleton_id,
            skeleton_version=preview.skeleton_version,
            knowledge_type=lesson.primary_knowledge_type,
            knowledge_type_source=lesson.knowledge_type_source,
            toggles_applied=preview.variants[0].toggles_applied,
            deviations_applied=[],
        )
    )
    lesson.pack_id = generation_id
    await session.flush()
    roles = [section.role for section in plan.sections]
    return (
        PreparedLessonResponse(
            generation_id=generation_id,
            path_lesson_id=lesson.id,
            objective=lesson.objective,
            objective_hash=lesson.objective_hash,
            skeleton_id=preview.skeleton_id,
            skeleton_version=preview.skeleton_version,
            slots=slots,
            section_roles=roles,
            status="planning_review",
            reused=False,
        ),
        plan,
    )
