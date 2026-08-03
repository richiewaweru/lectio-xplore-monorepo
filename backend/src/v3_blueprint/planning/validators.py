from __future__ import annotations

import logging

from contracts.lectio import get_component_card
from v3_blueprint.planning.models import QPlanItem, SectionBrief, SectionPlan, StructuralPlan

log = logging.getLogger(__name__)

CONTENT_INTENT_MAX_WORDS = 80


def _word_count(text: str) -> int:
    return len(text.split())


def _get_component_registry(slugs: set[str]) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for slug in slugs:
        card = get_component_card(slug)
        if card is not None:
            registry[slug] = card
    return registry


def _allowed_roles_from_skeletons(skeleton_catalog: dict | None) -> set[str]:
    if not isinstance(skeleton_catalog, dict):
        return set()
    slots = skeleton_catalog.get("slots")
    if not isinstance(slots, dict):
        return set()

    return {
        slot_id
        for slot_id in slots
        if isinstance(slot_id, str) and slot_id
    }


def validate_structural_plan_roles(
    plan: StructuralPlan,
    skeleton_catalog: dict | None,
) -> list[str]:
    allowed_roles = _allowed_roles_from_skeletons(skeleton_catalog)
    if not allowed_roles:
        log.warning(
            "skeleton role validation unavailable; StructuralPlan roles were not "
            "validated because no loaded skeleton slot catalog was supplied"
        )
        return []

    return [
        (
            f"Section '{section.id}' emitted role '{section.role}' "
            f"which is not a skeleton slot id: {sorted(allowed_roles)}."
        )
        for section in plan.sections
        if section.role not in allowed_roles
    ]


def validate_structural_plan(
    plan: StructuralPlan,
    resource_spec: dict | None = None,
    *,
    skeleton_catalog: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    all_slugs = {
        component.slug
        for section in plan.sections
        for component in section.components
    }
    registry = _get_component_registry(all_slugs)

    # 1. All slugs exist in registry
    for section in plan.sections:
        for comp in section.components:
            if comp.slug not in registry:
                errors.append(
                    f"Section '{section.id}': unknown slug '{comp.slug}'. "
                    f"Must be from AVAILABLE COMPONENTS."
                )

    # 2. section_field uniqueness per section
    for section in plan.sections:
        seen_fields: dict[str, str] = {}
        for comp in section.components:
            if comp.slug not in registry:
                continue  # already flagged above
            card = registry[comp.slug]
            field = card.get("sectionField") or card.get("section_field")
            if not isinstance(field, str):
                errors.append(
                    f"Section '{section.id}': component '{comp.slug}' is missing section_field metadata."
                )
                continue
            if field in seen_fields:
                errors.append(
                    f"Section '{section.id}': components '{comp.slug}' and "
                    f"'{seen_fields[field]}' share section_field '{field}'. "
                    f"Only one component per section_field is allowed."
                )
            else:
                seen_fields[field] = comp.slug

    # 3. visual_required=true sections have a visual-capable slug
    visual_capable = {
        "diagram-block",
        "diagram-series",
        "diagram-compare",
        "worked-example-card",
        "timeline-block",
    }
    for section in plan.sections:
        if section.visual_required:
            slugs = {c.slug for c in section.components}
            if not slugs.intersection(visual_capable):
                errors.append(
                    f"Section '{section.id}' has visual_required=true but "
                    f"no visual-capable component. Add one of: "
                    f"{sorted(visual_capable)}"
                )

    # 4. question_plan section_ids reference valid sections
    valid_section_ids = {s.id for s in plan.sections}
    for q in plan.question_plan:
        if q.section_id not in valid_section_ids:
            errors.append(
                f"question_plan item '{q.question_id}' references "
                f"section_id '{q.section_id}' which does not exist."
            )

    # 5. concept-card ids and misconception ids are unique
    card_ids = [card.id for card in plan.cards]
    duplicate_card_ids = sorted(
        card_id for card_id in set(card_ids) if card_ids.count(card_id) > 1
    )
    for card_id in duplicate_card_ids:
        errors.append(f"Concept card id '{card_id}' is duplicated within the plan.")

    known_card_ids = set(card_ids)
    for card in plan.cards:
        misconception_ids = [item.id for item in card.misconceptions]
        duplicate_misconception_ids = sorted(
            item_id
            for item_id in set(misconception_ids)
            if misconception_ids.count(item_id) > 1
        )
        for misconception_id in duplicate_misconception_ids:
            errors.append(
                f"Concept card '{card.id}' has duplicate misconception id "
                f"'{misconception_id}'."
            )
        if not card.misconceptions and not card.no_known_misconceptions:
            errors.append(
                f"Concept card '{card.id}' must contain a misconception or set "
                "no_known_misconceptions=true."
            )
        if card.misconceptions and card.no_known_misconceptions:
            errors.append(
                f"Concept card '{card.id}' cannot set no_known_misconceptions=true "
                "while misconceptions are present."
            )

    for section in plan.sections:
        if section.card_id is not None and section.card_id not in known_card_ids:
            errors.append(
                f"Section '{section.id}' references unknown card_id '{section.card_id}'."
            )

    # 6. repair_focus present when lesson_mode=repair
    if plan.lesson_mode == "repair" and plan.repair_focus is None:
        errors.append(
            "lesson_mode=repair requires repair_focus to be populated."
        )

    # 7. first section has transition_note=null
    if plan.sections and plan.sections[0].transition_note is not None:
        errors.append(
            f"First section '{plan.sections[0].id}' must have "
            f"transition_note=null."
        )

    errors.extend(validate_structural_plan_roles(plan, skeleton_catalog))

    return errors


def validate_section_brief(
    brief: SectionBrief,
    section_plan: SectionPlan,
    question_plan: list[QPlanItem],
) -> list[str]:
    errors: list[str] = []

    planned_slugs = {c.slug for c in section_plan.components}
    returned_slugs = {c.component_id for c in brief.components}

    missing_components = planned_slugs - returned_slugs
    if missing_components:
        errors.append(
            f"Section '{section_plan.id}': missing briefs for "
            f"planned components: {sorted(missing_components)}"
        )

    additional_components = returned_slugs - planned_slugs
    if additional_components:
        log.info(
            "Section '%s' returned additional component briefs that will not be consumed "
            "during assembly: %s",
            section_plan.id,
            sorted(additional_components),
        )

    for component in brief.components:
        words = _word_count(component.content_intent)
        if words > CONTENT_INTENT_MAX_WORDS:
            errors.append(
                f"Section '{section_plan.id}': component '{component.component_id}' "
                f"content_intent has {words} words (max {CONTENT_INTENT_MAX_WORDS}). "
                f"Rewrite as direction only — no finished problem, hint, option, "
                f"or solution text."
            )

    assigned_question_ids = {
        item.question_id
        for item in question_plan
        if item.section_id == section_plan.id
    }

    if section_plan.visual_required and not brief.visual_strategy:
        errors.append(
            f"Section '{section_plan.id}': visual_required is true "
            f"but no visual_strategy returned."
        )

    if section_plan.visual_required and brief.visual_strategy:
        vs = brief.visual_strategy
        visual_slugs = {c.slug for c in section_plan.components}
        if "diagram-series" in visual_slugs:
            if len(vs.frames) < 2:
                errors.append(
                    f"Section '{section_plan.id}': diagram-series component "
                    f"requires >= 2 frames in visual_strategy, got {len(vs.frames)}."
                )
        if vs.source_question_ids:
            bad_qids = set(vs.source_question_ids) - assigned_question_ids
            if bad_qids:
                errors.append(
                    f"Section '{section_plan.id}': source_question_ids references "
                    f"questions not in this section: {sorted(bad_qids)}"
                )

        if not vs.visual_job.strip():
            errors.append(
                f"Section '{section_plan.id}': visual_strategy.visual_job is empty."
            )

    if brief.section_id != section_plan.id:
        errors.append(
            f"Returned section_id '{brief.section_id}' does not match "
            f"assigned section '{section_plan.id}'."
        )

    return errors
