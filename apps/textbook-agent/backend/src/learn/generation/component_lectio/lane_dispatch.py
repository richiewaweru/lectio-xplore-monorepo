"""ExactWorkOrder lane adapters and identity join (Component Lectio production)."""

from __future__ import annotations

from typing import Any

from contracts.lectio import get_component_card
from learn.generation.component_lectio.errors import WorkOrderIdentityError
from learn.generation.component_lectio.payload_strategies import (
    SCHEMA_SUMMARIES,
    assemble_answer_key_content,
    assemble_items_content,
    assemble_visual_content,
    question_refs_from_payload,
    questions_from_refs,
)
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.work_orders import ExactWorkOrder, assert_writer_cannot_change_component
from v3_execution.compile_orders import COMPONENT_TO_VISUAL_MODE
from v3_execution.models import (
    AnswerKeyExecutorWorkOrder,
    AnswerKeyPlanSpec,
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    QuestionWriterWorkOrder,
    RegisterSpec,
    SectionWriterWorkOrder,
    SourceOfTruthEntry,
    VisualFrameSpec,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
    WriterMisconception,
    WriterQuestion,
    WriterSection,
    WriterSectionComponent,
)

__all__ = [
    "WorkOrderIdentityError",
    "adapt_answer_key_order",
    "adapt_content_order",
    "adapt_items_order",
    "adapt_visual_order",
    "assemble_answer_key_from_refs",
    "payload_from_answer_key",
    "payload_from_component_block",
    "payload_from_questions",
    "payload_from_visual",
    "payload_from_visuals",
    "question_refs_from_payload",
    "questions_from_item_payload",
    "resolve_exact_order",
    "stamp_component_block",
]


def resolve_exact_order(
    generated: Any,
    *,
    scoped_orders: list[ExactWorkOrder],
) -> ExactWorkOrder:
    """Map generated output to exactly one ExactWorkOrder.

    Preferred hierarchy: block_id → work_order_id → section_id + component_id (scoped).
    """
    if not scoped_orders:
        raise WorkOrderIdentityError("No ExactWorkOrders in scope")

    block_id = _field(generated, "block_id")
    if isinstance(generated, GeneratedVisualBlock):
        block_id = generated.visual_id
    if isinstance(generated, GeneratedQuestionBlock):
        block_id = generated.question_id

    by_block = {order.block_id: order for order in scoped_orders}
    if isinstance(block_id, str) and block_id in by_block:
        order = by_block[block_id]
        _assert_component_lock(generated, order)
        return order

    source_id = _field(generated, "source_work_order_id")
    by_wo = {order.work_order_id: order for order in scoped_orders}
    if isinstance(source_id, str) and source_id in by_wo:
        order = by_wo[source_id]
        _assert_component_lock(generated, order)
        return order

    section_id = _field(generated, "section_id") or _field(generated, "attaches_to")
    component_id = _field(generated, "component_id")
    matches = [
        order
        for order in scoped_orders
        if order.section_id == section_id and order.component_id == component_id
    ]
    if len(matches) == 1:
        _assert_component_lock(generated, matches[0])
        return matches[0]
    if len(matches) > 1:
        raise WorkOrderIdentityError(
            f"Ambiguous identity for component {component_id!r} in section {section_id!r}"
        )
    raise WorkOrderIdentityError(
        f"Generated output does not map to a scoped ExactWorkOrder (block_id={block_id!r})"
    )


def _field(generated: Any, name: str) -> Any:
    if isinstance(generated, dict):
        return generated.get(name)
    return getattr(generated, name, None)


def _assert_component_lock(generated: Any, order: ExactWorkOrder) -> None:
    if isinstance(generated, GeneratedQuestionBlock):
        return
    component_id = _field(generated, "component_id")
    if component_id is None:
        return
    if component_id != order.locked_component_id:
        raise WorkOrderIdentityError(
            f"Writer attempted to change component_id from "
            f"'{order.locked_component_id}' to '{component_id}'"
        )


def stamp_component_block(block: GeneratedComponentBlock, order: ExactWorkOrder) -> GeneratedComponentBlock:
    return block.model_copy(
        update={
            "block_id": order.block_id,
            "section_id": order.section_id,
            "component_id": order.locked_component_id,
            "source_work_order_id": order.work_order_id,
            "section_field": order.section_field or block.section_field,
        }
    )


def adapt_content_order(
    order: ExactWorkOrder,
    *,
    plan: StructuralPlan,
    template_id: str,
    prior_errors: list[str] | None = None,
) -> SectionWriterWorkOrder:
    assert_writer_cannot_change_component(order, order.component_id)
    section_meta = {section.id: section for section in plan.sections}
    meta = section_meta.get(order.section_id)
    card_by_id = {card.id: card for card in plan.cards}
    card = get_component_card(order.component_id) or dict(order.component_card)
    misconceptions = []
    if meta and meta.card_id and meta.card_id in card_by_id:
        for item in card_by_id[meta.card_id].misconceptions:
            misconceptions.append(WriterMisconception(id=item.id, description=item.description))
    return SectionWriterWorkOrder(
        work_order_id=order.work_order_id,
        section=WriterSection(
            id=order.section_id,
            title=meta.title if meta else order.section_id,
            learning_intent=meta.purpose if meta else "",
            role=meta.role if meta else "",
            transition_note=meta.transition_note if meta else None,
            card_id=meta.card_id if meta else None,
            anchor_example=plan.anchor.example,
            anchor_reuse_scope=plan.anchor.reuse_scope,
            misconceptions=misconceptions,
            components=[
                WriterSectionComponent(
                    component_id=order.locked_component_id,
                    teacher_label=order.locked_component_id,
                    content_intent=order.purpose,
                )
            ],
        ),
        register_spec=RegisterSpec(),
        source_of_truth=[SourceOfTruthEntry(key="anchor", text=plan.anchor.example)],
        component_cards={order.component_id: card},
        template_id=template_id,
        prior_validation_errors=list(prior_errors or []),
    )


def adapt_items_order(
    order: ExactWorkOrder,
    *,
    plan: StructuralPlan,
    prior_errors: list[str] | None = None,
) -> QuestionWriterWorkOrder:
    schema_summary = SCHEMA_SUMMARIES.get(order.locked_component_id, "")
    if not schema_summary and isinstance(order.schema_shape, dict):
        schema_summary = str(order.schema_shape)[:800]
    return QuestionWriterWorkOrder(
        work_order_id=order.work_order_id,
        section_id=order.section_id,
        questions=[
            WriterQuestion(
                id=order.block_id,
                difficulty="core",
                expected_answer="(pending)",
                purpose=order.purpose,
                skill_target="lesson_objective",
            )
        ],
        source_of_truth=[SourceOfTruthEntry(key="anchor", text=plan.anchor.example)],
        register=RegisterSpec(),
        consistency_rules=[],
        component_id=order.locked_component_id,
        section_field=order.section_field,
        purpose=order.purpose,
        schema_summary=schema_summary,
        prior_validation_errors=list(prior_errors or []),
    )


def adapt_visual_order(
    order: ExactWorkOrder,
    *,
    plan: StructuralPlan,
    prior_errors: list[str] | None = None,
) -> VisualGeneratorWorkOrder:
    mode = COMPONENT_TO_VISUAL_MODE.get(order.component_id, "diagram")
    if mode not in {"diagram", "diagram_series", "diagram_compare", "image", "simulation"}:
        mode = "diagram"
    frames: list[VisualFrameSpec] = []
    if order.component_id == "diagram-compare":
        frames = [
            VisualFrameSpec(description=f"Before: {order.purpose}", must_show=[order.purpose]),
            VisualFrameSpec(description=f"After: {order.purpose}", must_show=[order.purpose]),
        ]
        mode = "diagram_series"  # executor renders multi-frame via series path
    elif order.component_id == "diagram-series":
        frames = [
            VisualFrameSpec(description=f"Step 1: {order.purpose}", must_show=[order.purpose]),
            VisualFrameSpec(description=f"Step 2: {order.purpose}", must_show=[order.purpose]),
            VisualFrameSpec(description=f"Step 3: {order.purpose}", must_show=[order.purpose]),
        ]
        mode = "diagram_series"
    return VisualGeneratorWorkOrder(
        work_order_id=order.work_order_id,
        resource_type="lesson",
        dependency="blueprint_only",
        visual=VisualPlanItem(
            id=order.block_id,
            attaches_to=order.section_id,
            component_id=order.locked_component_id,
            mode=mode,  # type: ignore[arg-type]
            purpose=order.purpose,
            must_show=[order.purpose],
            frames=frames,
        ),
        source_of_truth=[SourceOfTruthEntry(key="anchor", text=plan.anchor.example)],
        prior_validation_errors=list(prior_errors or []),
    )


def adapt_answer_key_order(
    order: ExactWorkOrder,
    *,
    questions: list[WriterQuestion],
) -> AnswerKeyExecutorWorkOrder:
    return AnswerKeyExecutorWorkOrder(
        work_order_id=order.work_order_id,
        questions=questions,
        answer_key_plan=AnswerKeyPlanSpec(
            style="brief_explanations",
            include_question_ids=[item.id for item in questions],
        ),
        source_of_truth=[],
    )


def payload_from_component_block(block: GeneratedComponentBlock, order: ExactWorkOrder) -> dict[str, Any]:
    return {
        "content": block.data,
        "component_id": order.locked_component_id,
        "section_field": order.section_field or block.section_field,
        "position": block.position,
        "block_id": order.block_id,
        "work_order_id": order.work_order_id,
        "lane": order.lane,
    }


def payload_from_questions(
    blocks: list[GeneratedQuestionBlock],
    order: ExactWorkOrder,
) -> dict[str, Any]:
    return assemble_items_content(order, blocks)


def payload_from_visual(block: GeneratedVisualBlock, order: ExactWorkOrder) -> dict[str, Any]:
    return assemble_visual_content(order, [block])


def payload_from_visuals(
    blocks: list[GeneratedVisualBlock],
    order: ExactWorkOrder,
) -> dict[str, Any]:
    return assemble_visual_content(order, blocks)


def payload_from_answer_key(block: GeneratedAnswerKeyBlock, order: ExactWorkOrder) -> dict[str, Any]:
    """Legacy generator envelope — prefer assemble_answer_key_from_refs for production."""
    refs = []
    for idx, entry in enumerate(block.entries, start=1):
        if not isinstance(entry, dict):
            continue
        refs.append(
            {
                "id": str(entry.get("question_id") or f"q{idx}"),
                "question": str(entry.get("question") or entry.get("question_id") or f"Question {idx}"),
                "expected_answer": str(
                    entry.get("correct_answer")
                    or entry.get("student_answer")
                    or entry.get("explanation")
                    or ""
                ),
            }
        )
    return assemble_answer_key_content(order, question_refs=refs)


def assemble_answer_key_from_refs(
    order: ExactWorkOrder,
    *,
    question_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return assemble_answer_key_content(order, question_refs=question_refs)


def questions_from_item_payload(payload: dict[str, Any]) -> list[WriterQuestion]:
    refs = question_refs_from_payload(payload)
    if refs:
        return questions_from_refs(refs)
    # Legacy fallback for older checkpoints
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    items = content.get("items") if isinstance(content, dict) else []
    questions: list[WriterQuestion] = []
    if not isinstance(items, list):
        return questions
    for item in items:
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id") or "")
        if not question_id:
            continue
        questions.append(
            WriterQuestion(
                id=question_id,
                difficulty=str(item.get("difficulty") or "core"),
                expected_answer=str(item.get("expected_answer") or ""),
                purpose="practice",
            )
        )
    return questions
