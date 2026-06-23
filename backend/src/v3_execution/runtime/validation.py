from __future__ import annotations

from typing import Iterable

from contracts.lectio import get_section_field_for_component

from v3_execution.models import (
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    QuestionWriterWorkOrder,
    SectionWriterWorkOrder,
    VisualGeneratorWorkOrder,
)


def _image_url_valid(url: str) -> bool:
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def check_anchor_units_present(
    data: dict,
    truth_entries: list,
    anchor_id: str,
) -> list[str]:
    errors: list[str] = []
    _ = anchor_id
    text_blob = str(data).lower()
    for entry in truth_entries:
        for token in entry.unit_tokens:
            if token and token.lower() not in text_blob:
                errors.append(f"Missing anchor unit token '{token}' for component output.")
    return errors


def validate_component_block(
    block: GeneratedComponentBlock,
    work_order: SectionWriterWorkOrder,
    component_cards: dict | None = None,
) -> list[str]:
    errors: list[str] = []

    planned_ids = [c.component_id for c in work_order.section.components]
    if block.component_id not in planned_ids:
        errors.append(f"Unplanned component: {block.component_id}")

    expected_field: str | None = None
    if component_cards and block.component_id in component_cards:
        card = component_cards[block.component_id] or {}
        expected_field = card.get("section_field")
    else:
        expected_field = get_section_field_for_component(block.component_id)
    if expected_field and block.section_field != expected_field:
        errors.append(
            f"section_field mismatch for {block.component_id}: "
            f"expected '{expected_field}', got '{block.section_field}'"
        )

    for comp in work_order.section.components:
        if comp.uses_anchor_id:
            errors.extend(
                check_anchor_units_present(
                    block.data,
                    work_order.source_of_truth,
                    comp.uses_anchor_id,
                )
            )
    return errors


def validate_question_block(
    block: GeneratedQuestionBlock,
    work_order: QuestionWriterWorkOrder,
) -> list[str]:
    errors: list[str] = []
    planned_ids = [q.id for q in work_order.questions]
    if block.question_id not in planned_ids:
        errors.append(f"Unplanned question: {block.question_id}")

    planned = next((q for q in work_order.questions if q.id == block.question_id), None)
    if planned:
        if block.difficulty != planned.difficulty:
            errors.append(f"Difficulty changed: {planned.difficulty} → {block.difficulty}")
        if block.expected_answer != planned.expected_answer:
            errors.append(f"Expected answer changed for {block.question_id}")
    return errors


def validate_visual_block(
    block: GeneratedVisualBlock,
    work_order: VisualGeneratorWorkOrder,
) -> list[str]:
    errors: list[str] = []
    valid_visual_id = block.visual_id == work_order.visual.id
    if (
        not valid_visual_id
        and block.frame_index is not None
        and work_order.visual.mode == "diagram_series"
    ):
        valid_visual_id = block.visual_id == f"{work_order.visual.id}_frame_{block.frame_index}"
    if not valid_visual_id:
        errors.append("visual_id mismatch")
    if block.mode in {"diagram", "image", "diagram_series", "diagram_compare"}:
        if not block.image_url or not _image_url_valid(block.image_url):
            errors.append("image_url not a valid hosted URL")
    if block.mode == "simulation":
        if not block.html_content and not block.fallback_image_url:
            errors.append("simulation requires html_content or fallback_image_url")
    return errors


def validate_component_batch(
    blocks: Iterable[GeneratedComponentBlock],
    order: SectionWriterWorkOrder,
    *,
    component_cards: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    blocks_list = list(blocks)
    planned = {c.component_id for c in order.section.components}
    seen: set[str] = set()
    for block in blocks_list:
        errors.extend(validate_component_block(block, order, component_cards=component_cards))
        seen.add(block.component_id)
    missing = planned - seen
    for mid in missing:
        errors.append(f"Missing component output for {mid}")
    extra = seen - planned
    for eid in extra:
        errors.append(f"Extra component block for {eid}")
    return errors


def validate_question_batch(
    blocks: Iterable[GeneratedQuestionBlock],
    order: QuestionWriterWorkOrder,
) -> list[str]:
    errors: list[str] = []
    blocks_list = list(blocks)
    planned = {q.id for q in order.questions}
    seen = {b.question_id for b in blocks_list}
    for block in blocks_list:
        errors.extend(validate_question_block(block, order))
    missing = planned - seen
    for mid in missing:
        errors.append(f"Missing question block for {mid}")
    extra = seen - planned
    for eid in extra:
        errors.append(f"Extra question block for {eid}")
    return errors


__all__ = [
    "check_anchor_units_present",
    "validate_component_batch",
    "validate_component_block",
    "validate_question_batch",
    "validate_question_block",
    "validate_visual_block",
]
