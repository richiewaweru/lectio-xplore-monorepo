from __future__ import annotations

from contracts.lectio import get_component_card
from v3_blueprint.planning.models import QPlanItem, SectionBrief, SectionPlan, StructuralPlan


def _get_component_registry(slugs: set[str]) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for slug in slugs:
        card = get_component_card(slug)
        if card is not None:
            registry[slug] = card
    return registry


def _allowed_roles_from_resource_spec(resource_spec: dict | None) -> set[str]:
    if not isinstance(resource_spec, dict):
        return set()
    spec = resource_spec.get("spec")
    if not isinstance(spec, dict):
        return set()

    roles: set[str] = set()
    for key in ("required_roles", "optional_roles"):
        raw_roles = spec.get(key)
        if isinstance(raw_roles, list):
            roles.update(role for role in raw_roles if isinstance(role, str) and role)

    sections = spec.get("sections")
    if isinstance(sections, dict):
        for key in ("required", "optional"):
            raw_sections = sections.get(key)
            if not isinstance(raw_sections, list):
                continue
            for section in raw_sections:
                if not isinstance(section, dict):
                    continue
                role = section.get("role")
                if isinstance(role, str) and role:
                    roles.add(role)
    return roles


def validate_structural_plan(
    plan: StructuralPlan,
    resource_spec: dict | None = None,
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

    # 5. repair_focus present when lesson_mode=repair
    if plan.lesson_mode == "repair" and plan.repair_focus is None:
        errors.append(
            "lesson_mode=repair requires repair_focus to be populated."
        )

    # 6. first section has transition_note=null
    if plan.sections and plan.sections[0].transition_note is not None:
        errors.append(
            f"First section '{plan.sections[0].id}' must have "
            f"transition_note=null."
        )

    allowed_roles = _allowed_roles_from_resource_spec(resource_spec)
    if allowed_roles:
        for section in plan.sections:
            if section.role not in allowed_roles:
                errors.append(
                    f"Section '{section.id}' emitted role '{section.role}' "
                    f"which is not in the active resource spec roles: {sorted(allowed_roles)}."
                )

    return errors


def validate_section_brief(
    brief: SectionBrief,
    section_plan: SectionPlan,
    question_plan: list[QPlanItem],
) -> list[str]:
    errors: list[str] = []

    planned_slugs = {c.slug for c in section_plan.components}
    returned_slugs = {c.component_id for c in brief.components}

    # 1. Nothing dropped — every planned slug has a brief
    dropped = planned_slugs - returned_slugs
    if dropped:
        errors.append(
            f"Section '{section_plan.id}': missing briefs for "
            f"planned components: {sorted(dropped)}"
        )

    # 2. Nothing added — no slugs outside section plan
    added = returned_slugs - planned_slugs
    if added:
        errors.append(
            f"Section '{section_plan.id}': unexpected components "
            f"not in plan: {sorted(added)}"
        )

    # 3. No question briefs from other sections
    this_section_qids = {
        q.question_id for q in question_plan
        if q.section_id == section_plan.id
    }
    returned_qids = {q.question_id for q in brief.question_briefs}
    wrong_section = returned_qids - this_section_qids
    if wrong_section:
        errors.append(
            f"Section '{section_plan.id}': question briefs returned "
            f"for questions not assigned here: {wrong_section}"
        )

    # 4. visual_strategy present only when visual_required
    if brief.visual_strategy and not section_plan.visual_required:
        errors.append(
            f"Section '{section_plan.id}': visual_strategy returned "
            f"but visual_required is false."
        )

    # 5. visual_strategy present when visual_required
    if section_plan.visual_required and not brief.visual_strategy:
        errors.append(
            f"Section '{section_plan.id}': visual_required is true "
            f"but no visual_strategy returned."
        )

    # 6. section_id matches
    if brief.section_id != section_plan.id:
        errors.append(
            f"Returned section_id '{brief.section_id}' does not match "
            f"assigned section '{section_plan.id}'."
        )

    return errors
