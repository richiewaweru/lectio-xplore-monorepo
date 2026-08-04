from __future__ import annotations

from v3_blueprint.models import ProductionBlueprint
from v3_blueprint.work_orders import (
    AnswerKeyItem,
    AnswerKeyWorkOrder,
    CoherenceReviewWorkOrder,
    CompiledWorkOrders,
    InteractionWorkOrder,
    SectionWorkOrder,
    VisualWorkOrder,
)


class BlueprintCompiler:
    """Deterministically compile a production blueprint into executable work orders."""

    def compile_all(self, blueprint: ProductionBlueprint) -> CompiledWorkOrders:
        section_orders = [
            SectionWorkOrder(
                section_id=section.section_id,
                title=section.title,
                role=section.role,
                components=list(section.components),
            )
            for section in blueprint.sections
        ]

        visual_order = VisualWorkOrder(visuals=list(blueprint.visual_strategy.visuals))

        interaction_orders: list[InteractionWorkOrder] = []
        question_ids_by_section: dict[str, list[str]] = {}
        for item in blueprint.question_plan:
            question_ids_by_section.setdefault(item.section_id, []).append(item.question_id)
        for section in blueprint.sections:
            interaction_orders.append(
                InteractionWorkOrder(
                    section_id=section.section_id,
                    question_ids=question_ids_by_section.get(section.section_id, []),
                )
            )

        answer_key_order = AnswerKeyWorkOrder(
            style=blueprint.answer_key.style,
            items=[
                AnswerKeyItem(
                    question_id=item.question_id,
                    expected_answer=item.expected_answer,
                )
                for item in blueprint.question_plan
            ],
        )

        coherence_review_order = CoherenceReviewWorkOrder(
            checklist=[
                "All component plans include content_intent.",
                "All question plans include expected_answer.",
                "All required visuals are covered by visual_strategy.",
            ]
        )

        return CompiledWorkOrders(
            section_orders=section_orders,
            visual_order=visual_order,
            interaction_orders=interaction_orders,
            answer_key_order=answer_key_order,
            coherence_review_order=coherence_review_order,
        )
