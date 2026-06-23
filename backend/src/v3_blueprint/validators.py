from __future__ import annotations

from v3_blueprint.models import ProductionBlueprint


def validate_blueprint_completeness(blueprint: ProductionBlueprint) -> list[str]:
    errors: list[str] = []

    for section in blueprint.sections:
        for component in section.components:
            if not component.content_intent.strip():
                errors.append(
                    f"Section '{section.section_id}' has component '{component.component}' "
                    "with empty content_intent."
                )

    visual_section_ids = {visual.section_id for visual in blueprint.visual_strategy.visuals}
    for section in blueprint.sections:
        if section.visual_required and section.section_id not in visual_section_ids:
            errors.append(
                f"Section '{section.section_id}' requires visuals but has no visual strategy entry."
            )
    for visual in blueprint.visual_strategy.visuals:
        if not visual.component_id:
            errors.append(
                f"Visual instruction for section '{visual.section_id}' "
                "is missing component_id."
            )

    for item in blueprint.question_plan:
        if not item.expected_answer.strip():
            errors.append(f"Question '{item.question_id}' is missing expected_answer.")

    return errors
