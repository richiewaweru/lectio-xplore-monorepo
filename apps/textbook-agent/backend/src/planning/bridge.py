from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UnitScopeContractModel,
    UnitModel,
)
from contracts.lectio import get_component_card
from generation.path_preparation import initialise_path_generation
from planning.agents import run_component_selector, run_path_structural_planner
from planning.models import (
    ComponentSelection,
    PathStructuralPlan,
    PrepareLessonRequest,
    PreparedLessonResponse,
)
from planning.outcomes import actual_context_for_lessons
from planning.schedule import selected_unit_groups
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    ConceptCard,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
    VariantSpec,
)
from v3_blueprint.planning.objective_ownership import ObjectiveOwnership, ObjectiveOwnershipError
from v3_blueprint.planning.persistence import load_chunked_state
from v3_blueprint.skeletons import (
    SkeletonPreviewRequest,
    SkeletonVariantPreview,
    load_skeleton_catalog,
)
from planning.shapes import (
    approved_deviation_contracts,
    deviation_payload,
    lesson_deviations,
)


class PathPreparationBlocked(ValueError):
    pass


StructuralPlanner = Callable[[dict[str, Any]], Awaitable[PathStructuralPlan]]
ComponentSelector = Callable[[dict[str, Any]], Awaitable[ComponentSelection]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _preparation_key(*, version_id: str, lesson_id: str, revision: int) -> str:
    raw = json.dumps(
        {"path_version_id": version_id, "path_lesson_id": lesson_id, "revision": revision},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clip_advisory_text(value: str, *, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


async def _preparation_context(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
) -> tuple[dict[str, Any], list[str], list[dict[str, str]], list[dict[str, Any]]]:
    scope = await session.get(UnitScopeContractModel, unit.id)
    scope_contract = {
        "must_establish": list(scope.must_establish or []) if scope else [],
        "may_include": list(scope.may_include or []) if scope else [],
        "must_not_introduce": list(scope.must_not_introduce or []) if scope else [],
        "assumed_prerequisites": list(scope.assumed_prerequisites or []) if scope else [],
        "terminology": list(scope.terminology or []) if scope else [],
        "notation": scope.notation if scope else None,
    }
    earlier = list(
        await session.scalars(
            select(PathLessonModel)
            .where(
                PathLessonModel.path_version_id == version.id,
                PathLessonModel.position < lesson.position,
            )
            .order_by(PathLessonModel.position)
        )
    )
    prior_established = list(dict.fromkeys([
        *list(unit.starting_knowledge or []),
        *(capability for prior in earlier if not prior.skipped for capability in (prior.must_establish or [])),
    ]))
    prerequisite_ids = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel.prerequisite_lesson_id).where(
                PathLessonPrerequisiteModel.path_lesson_id == lesson.id
            )
        )
    )
    prerequisite_by_id = {prior.id: prior for prior in earlier}
    prerequisites = [
        {
            "path_lesson_id": prerequisite_id,
            "concept_id": prerequisite_by_id[prerequisite_id].concept_id,
            "objective": prerequisite_by_id[prerequisite_id].objective,
        }
        for prerequisite_id in prerequisite_ids
        if prerequisite_id in prerequisite_by_id
    ]
    actuals = await actual_context_for_lessons(
        session, path_lesson_ids=[prior.id for prior in earlier]
    )
    return scope_contract, prior_established, prerequisites, actuals


def _build_structural_plan(
    *,
    generated: PathStructuralPlan,
    lesson: PathLessonModel,
    lesson_mode: str,
    prior_knowledge: list[str],
    slots: list[str],
    selected_components: dict[str, list[str]],
    page_block_plans: dict[str, Any] | None = None,
) -> StructuralPlan:
    if generated.deviation_request is not None:
        raise PathPreparationBlocked("A skeleton deviation requires teacher approval")
    if generated.objective_concern:
        raise PathPreparationBlocked(f"Structural planner objective concern: {generated.objective_concern}")
    if len(generated.cards) != 1:
        raise PathPreparationBlocked("Path preparation must produce exactly one concept card")
    card_payload = dict(generated.cards[0])
    # Structured model responses occasionally encode an omitted continuity
    # instruction as JSON null. The contract already treats an omitted value
    # as an empty instruction, so normalize only that equivalent representation
    # before strict validation.
    if card_payload.get("opens_by") is None:
        card_payload["opens_by"] = ""
    card = ConceptCard.model_validate(card_payload)
    ownership = ObjectiveOwnership.from_path_objective(lesson.objective)
    try:
        ownership.verify_generated_objective(card.objective)
    except ObjectiveOwnershipError as exc:
        raise PathPreparationBlocked(str(exc)) from exc
    if card.id != lesson.concept_id:
        raise PathPreparationBlocked("Prepared card must retain the canonical concept ID")

    section_payloads: list[dict[str, Any]] = []
    for index, generated_section in enumerate(generated.sections):
        section_payload = dict(generated_section)
        title = section_payload.get("title")
        if isinstance(title, str):
            section_payload["title"] = _clip_advisory_text(title, limit=80)
        transition_note = section_payload.get("transition_note")
        if index == 0:
            section_payload["transition_note"] = None
        elif isinstance(transition_note, str):
            section_payload["transition_note"] = _clip_advisory_text(
                transition_note,
                limit=120,
            )
        components = section_payload.get("components")
        if isinstance(components, list):
            section_payload["components"] = [
                {key: value for key, value in component.items() if key != "reason"}
                if isinstance(component, dict)
                else component
                for component in components
            ]
        section_payloads.append(section_payload)
    sections = [SectionPlan.model_validate(section) for section in section_payloads]
    roles = [section.role for section in sections]
    if roles != slots:
        raise PathPreparationBlocked(
            f"Prepared section roles must match skeleton slots exactly: expected {slots}, got {roles}"
        )
    if any(section.id != role for section, role in zip(sections, slots, strict=True)):
        raise PathPreparationBlocked("Prepared section IDs must equal their fixed slot IDs")
    for section in sections:
        if page_block_plans is not None:
            plan_for_slot = page_block_plans.get(section.role)
            if plan_for_slot is not None:
                section.components = []
                section.blocks = list(plan_for_slot.blocks)
            continue
        actual = [component.slug for component in section.components]
        if actual != selected_components[section.role]:
            raise PathPreparationBlocked(
                f"Section {section.role!r} components differ from the component selector output"
            )

    check = next(section for section in sections if section.role == "check")
    plan = StructuralPlan(
        document_contract_version=2 if page_block_plans is not None else 1,
        lesson_mode=lesson_mode,
        lesson_intent=LessonIntent(
            goal=lesson.objective,
            structure_rationale="Path objective and skeleton slots are fixed; content awaits teacher review.",
        ),
        anchor=AnchorSpec(
            example=_clip_advisory_text(generated.anchor.description, limit=100),
            reuse_scope="Reuse this anchor across the fixed path lesson slots.",
        ),
        prior_knowledge=prior_knowledge,
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


def _blocking_shape_message(variants: list[SkeletonVariantPreview]) -> str | None:
    issues = [
        f"{variant.group_profile}: {issue.code} — {issue.message}"
        for variant in variants
        for issue in variant.blocking_issues
    ]
    if not issues:
        return None
    return "Shape preparation is blocked: " + "; ".join(issues)


def _materialize_variant_plan(
    *,
    base_plan: StructuralPlan,
    preview: SkeletonVariantPreview,
    component_selections: dict[str, ComponentSelection],
) -> StructuralPlan:
    base_by_role: dict[str, list[SectionPlan]] = {}
    for section in base_plan.sections:
        base_by_role.setdefault(section.role, []).append(section)
    occurrence: dict[str, int] = {}
    sections: list[SectionPlan] = []
    for position, slot in enumerate(preview.slots):
        occurrence[slot.slot_id] = occurrence.get(slot.slot_id, 0) + 1
        slot_occurrence = occurrence[slot.slot_id]
        existing = base_by_role.get(slot.slot_id, [])
        if slot_occurrence <= len(existing):
            section = existing[slot_occurrence - 1].model_copy(deep=True)
        else:
            selection = component_selections[slot.slot_id]
            section = SectionPlan(
                id=(slot.slot_id if slot_occurrence == 1 else f"{slot.slot_id}-{slot_occurrence}"),
                title=(slot.purpose.strip() or slot.role.replace("_", " ").title())[:80],
                role=slot.slot_id,
                card_id=base_plan.cards[0].id,
                visual_required=slot.visual_required,
                transition_note=None,
                components=[
                    ComponentSlot(slug=component.slug, purpose=component.purpose)
                    for component in selection.components
                ],
            )
        section.id = slot.slot_id if slot_occurrence == 1 else f"{slot.slot_id}-{slot_occurrence}"
        section.role = slot.slot_id
        section.transition_note = (
            None
            if position == 0
            else f"Builds from the prior slot to {slot.purpose.strip() or slot.role}."[:120]
        )
        sections.append(section)
    check_sections = [section for section in sections if section.role == "check"]
    if len(check_sections) != 1:
        raise PathPreparationBlocked("Every differentiated shape must retain one shared check slot")
    return base_plan.model_copy(
        deep=True,
        update={
            "sections": sections,
            "question_plan": [
                QPlanItem(
                    question_id="q-check-1",
                    section_id=check_sections[0].id,
                    temperature="cold",
                )
            ],
        },
    )


async def prepare_path_lesson(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
    request: PrepareLessonRequest,
    structural_planner: StructuralPlanner = run_path_structural_planner,
    component_selector: ComponentSelector = run_component_selector,
    regenerate: bool = False,
    regeneration_reason: str | None = None,
) -> tuple[PreparedLessonResponse, StructuralPlan]:
    if version.status != "approved":
        raise PathPreparationBlocked("Path must be approved before lesson preparation")
    if lesson.skipped:
        raise PathPreparationBlocked("Skipped path lessons cannot be prepared")
    groups = await selected_unit_groups(
        session,
        unit_id=unit.id,
        group_ids=request.group_ids,
    )
    deviations = await lesson_deviations(session, lesson_id=lesson.id)
    previous_pack_id = lesson.pack_id
    if regenerate and not previous_pack_id:
        raise PathPreparationBlocked("No existing preparation is available to regenerate")
    if regenerate and not (regeneration_reason or "").strip():
        raise PathPreparationBlocked("Regeneration requires a recorded reason")
    if previous_pack_id and not regenerate:
        generation = await session.get(GenerationModel, lesson.pack_id)
        provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
        if generation is not None and provenance is not None:
            if provenance.objective_hash != lesson.objective_hash:
                raise PathPreparationBlocked(
                    "Existing preparation is stale; use explicit regeneration"
                )
            if provenance.path_lesson_revision not in {None, lesson.revision}:
                raise PathPreparationBlocked(
                    "Existing preparation is for an earlier lesson revision; use explicit regeneration"
                )
            if provenance.lesson_mode not in {None, request.lesson_mode} or sorted(
                provenance.group_ids or []
            ) != sorted(request.group_ids):
                raise PathPreparationBlocked(
                    "Preparation settings changed; use explicit regeneration"
                )
            try:
                state = await load_chunked_state(generation.id, session)
            except ValueError as exc:
                raise PathPreparationBlocked(
                    "Existing preparation predates the resumable workflow; regenerate it explicitly"
                ) from exc
            plan = StructuralPlan.model_validate(state.get("structural_plan"))
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
                    status="awaiting_review",
                    reused=True,
                ),
                plan,
            )

    scope_contract, prior_established, prerequisites, lesson_actuals = await _preparation_context(
        session,
        unit=unit,
        version=version,
        lesson=lesson,
    )
    catalog = load_skeleton_catalog()
    skeleton = catalog.skeleton_for(lesson.primary_knowledge_type, request.lesson_mode)
    skeleton_id = str(skeleton["id"])
    relevant_deviations = [
        item
        for item in deviations
        if item.lesson_mode == request.lesson_mode and item.skeleton_id == skeleton_id
    ]
    pending_deviations = [
        item for item in relevant_deviations if item.status == "pending_teacher"
    ]
    if pending_deviations:
        raise PathPreparationBlocked(
            "Shape preparation has a pending deviation; approve or reject it first"
        )
    approved_deviations = approved_deviation_contracts(
        relevant_deviations,
        lesson_mode=request.lesson_mode,
        skeleton_id=skeleton_id,
    )
    preview = catalog.preview(
        SkeletonPreviewRequest(
            objective=lesson.objective,
            lesson_mode=request.lesson_mode,
            misconception_count=0,
            group_profiles=["core"],
            approved_deviations=approved_deviations,
        ),
        knowledge_type=lesson.primary_knowledge_type,
    )
    blocking = _blocking_shape_message(preview.variants)
    if blocking:
        raise PathPreparationBlocked(blocking)
    slots = [slot.slot_id for slot in preview.variants[0].slots]
    possible_previews = [
        catalog.preview(
            SkeletonPreviewRequest(
                objective=lesson.objective,
                lesson_mode=request.lesson_mode,
                misconception_count=count,
                group_profiles=[group.profile for group in groups] or ["core"],
                approved_deviations=approved_deviations,
            ),
            knowledge_type=lesson.primary_knowledge_type,
        )
        for count in (0, 1, 2)
    ]
    preparation_group_preview = possible_previews[0]
    slots_by_id = {
        slot.slot_id: slot
        for possible in possible_previews
        for variant in possible.variants
        for slot in variant.slots
    }
    slots_by_id.update({slot.slot_id: slot for slot in preview.variants[0].slots})
    from core.config import settings
    from planning.page_blocks import (
        page_document_scope_matches,
        plan_conceptual_first_exposure_blocks,
    )

    use_page_docs = settings.xplore_page_documents_enabled and page_document_scope_matches(
        knowledge_type=lesson.primary_knowledge_type,
        lesson_mode=request.lesson_mode,
        scope=settings.xplore_page_document_scope,
    )
    component_selections: dict[str, ComponentSelection] = {}
    page_block_plans = None
    if use_page_docs:
        # Native v2 path: plan ordered page blocks; never call component selector.
        page_block_plans = await plan_conceptual_first_exposure_blocks(
            allow_paid=settings.allow_paid_llm_tests,
        )
    else:
        for slot in slots_by_id.values():
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
        "scope_contract": scope_contract,
        "prior_established": prior_established,
        "prerequisites": prerequisites,
        "lesson_actuals": lesson_actuals,
        "external_prerequisites": list(lesson.external_prerequisites or []),
        "must_establish": list(lesson.must_establish or []),
        "exclusions": list(lesson.exclusions or []),
        "group_ids": request.group_ids,
        "groups": [
            {
                "id": group.id,
                "label": group.label,
                "profile": group.profile,
                "description": group.description,
                "toggle_profile": group.toggle_profile,
                "voice": group.voice,
            }
            for group in groups
        ],
        "variant_previews": [
            variant.model_dump(mode="json")
            for variant in preparation_group_preview.variants
        ],
    }
    generated = await structural_planner(fixed_context)
    plan = _build_structural_plan(
        generated=generated,
        lesson=lesson,
        lesson_mode=request.lesson_mode,
        prior_knowledge=prior_established,
        slots=slots,
        selected_components={
            slot_id: [component.slug for component in selection.components]
            for slot_id, selection in component_selections.items()
        },
        page_block_plans=page_block_plans,
    )
    misconception_count = min(len(plan.cards[0].misconceptions), 3)
    group_preview = catalog.preview(
        SkeletonPreviewRequest(
            objective=lesson.objective,
            lesson_mode=request.lesson_mode,
            misconception_count=misconception_count,
            group_profiles=[group.profile for group in groups] or ["core"],
            approved_deviations=approved_deviations,
        ),
        knowledge_type=lesson.primary_knowledge_type,
    )
    blocking = _blocking_shape_message(group_preview.variants)
    if blocking:
        raise PathPreparationBlocked(
            f"{blocking}. Resolve the structural conflict or narrow approved misconceptions."
        )

    generation_id = str(uuid.uuid4())
    variants = [
        VariantSpec.model_validate(
            {
                "label": group.label,
                "group_description": group.description,
                "voice": group.voice,
            }
        )
        for group in groups
    ]
    variant_plans = (
        {
            group.label: _materialize_variant_plan(
                base_plan=plan,
                preview=variant_preview,
                component_selections=component_selections,
            )
            for group, variant_preview in zip(groups, group_preview.variants, strict=True)
        }
        if groups
        else {}
    )
    learning_pack_id = str(uuid.uuid4()) if variants else None
    if learning_pack_id is not None:
        resources = [
            {
                "id": f"variant-{index}",
                "label": variant.label,
                "resource_type": "lesson",
                "enabled": True,
                "variant_spec": variant.model_dump(mode="json"),
            }
            for index, variant in enumerate(variants, start=1)
        ]
        session.add(
            LearningPackModel(
                id=learning_pack_id,
                user_id=unit.owner_id,
                learning_job_type="xplore_variants",
                subject=unit.subject,
                topic=lesson.title,
                pack_plan_json=json.dumps(
                    {"resources": resources, "shared_quiz": True},
                    sort_keys=True,
                ),
                status="pending",
                resource_count=len(resources),
                completed_count=0,
            )
        )
    generation = GenerationModel(
        id=generation_id,
        user_id=unit.owner_id,
        subject=unit.subject,
        context=f"Prepared from path lesson {lesson.id}",
        mode="v3",
        status="awaiting_review",
        requested_template_id="guided-concept-path",
        resolved_template_id="guided-concept-path",
        requested_preset_id="v3-studio",
        resolved_preset_id="v3-studio",
        section_count=len(plan.sections),
        planning_spec_json=plan.model_dump_json(),
        pack_id=learning_pack_id,
    )
    session.add(generation)
    provenance = LessonProvenanceModel(
            pack_id=generation_id,
            concept_id=lesson.concept_id,
            path_version_id=version.id,
            path_lesson_id=lesson.id,
            objective_hash=lesson.objective_hash,
            skeleton_id=preview.skeleton_id,
            skeleton_version=preview.skeleton_version,
            knowledge_type=lesson.primary_knowledge_type,
            knowledge_type_source=lesson.knowledge_type_source,
            toggles_applied=list(
                dict.fromkeys(
                    toggle
                    for variant in group_preview.variants
                    for toggle in variant.toggles_applied
                )
            ),
            deviations_requested=[deviation_payload(item) for item in relevant_deviations],
            deviations_approved=[
                deviation_payload(item)
                for item in relevant_deviations
                if item.status == "approved"
            ],
            deviations_applied=[deviation.model_dump(mode="json") for deviation in approved_deviations],
            path_lesson_revision=lesson.revision,
            lesson_mode=request.lesson_mode,
            group_ids=sorted(request.group_ids),
            preparation_key=_preparation_key(
                version_id=version.id,
                lesson_id=lesson.id,
                revision=lesson.revision,
            ),
            supersedes_pack_id=previous_pack_id if regenerate else None,
            regeneration_reason=regeneration_reason if regenerate else None,
        )
    session.add(provenance)
    if regenerate and previous_pack_id:
        previous = await session.get(LessonProvenanceModel, previous_pack_id)
        if previous is not None:
            previous.invalidated_at = _utcnow()
    await session.flush()
    await initialise_path_generation(
        session,
        generation=generation,
        plan=plan,
        concept_id=lesson.concept_id,
        topic=lesson.title,
        grade_level=unit.grade_level,
        subject=unit.subject,
        lesson_mode=request.lesson_mode,
        prior_established=prior_established,
        scope_contract=scope_contract,
        variants=variants,
        variant_plans=variant_plans,
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
            status="awaiting_review",
            reused=False,
        ),
        plan,
    )
