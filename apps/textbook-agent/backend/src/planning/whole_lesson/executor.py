"""Native whole-lesson executor: form plan → writers → LectioDocumentV2."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from contracts.lectio_page import get_intent_catalogue
from core.database.models import GenerationModel
from generation.page_objects import WriterContext, WriterResult, dispatch_writer_async
from generation.page_objects.document_assembly import (
    assemble_document_v2,
    assemble_section,
    persist_document_json,
)
from planning.approved_items import ApprovedItemRecord, approved_items_as_writer_records
from planning.whole_lesson.events import make_event
from planning.whole_lesson.figure_ids import stable_figure_request_id
from planning.whole_lesson.form_agent import run_form_planner
from planning.whole_lesson.form_plan import FormPlan
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.repository import PageDocumentRepository
from planning.whole_lesson.teaching_plan import TeachingPlan
from v3_blueprint.planning.models import PlannedBlock, SectionBlockPlan


def form_plan_to_section_plans(form_plan: FormPlan) -> dict[str, SectionBlockPlan]:
    plans: dict[str, SectionBlockPlan] = {}
    for section in form_plan.sections:
        blocks = [
            PlannedBlock(
                id=block.id,
                position=block.position,
                intent=block.intent,
                object=block.object,  # type: ignore[arg-type]
                evidence=block.evidence or "Form-assigned block.",
                brief=block.brief,
                placement=block.placement,
                source_question_ids=list(block.source_question_ids),
            )
            for block in section.blocks
        ]
        plans[section.slot_id] = SectionBlockPlan(blocks=blocks)
    return plans


def _packet_item_records(packet: ImmutableLessonPacket) -> tuple[dict[str, Any], ...]:
    records = tuple(
        ApprovedItemRecord(
            id=item.id,
            card_id=item.card_id,
            stem=item.stem,
            options=tuple(dict(option) for option in item.options),
            correct_key=item.correct_key,
            diagnoses=dict(item.diagnoses),
        )
        for item in packet.approved_items
    )
    return approved_items_as_writer_records(records)


async def write_form_blocks(
    *,
    generation_id: str,
    form_plan: FormPlan,
    packet: ImmutableLessonPacket,
    repo: PageDocumentRepository,
) -> list[WriterResult]:
    """Write every form-assigned block. Questions stay deterministic."""
    intents = get_intent_catalogue().get("intents") or {}
    item_records = _packet_item_records(packet)
    flat_blocks = [
        (section.slot_id, block)
        for section in form_plan.sections
        for block in section.blocks
    ]
    results: list[WriterResult] = []
    for index, (slot_id, block) in enumerate(flat_blocks):
        await repo.append_event(
            make_event(
                "block_queued",
                generation_id=generation_id,
                section_id=slot_id,
                block_id=block.id,
                position=block.position,
                object_id=block.object,
                status="queued",
            )
        )
        await repo.append_event(
            make_event(
                "block_started",
                generation_id=generation_id,
                section_id=slot_id,
                block_id=block.id,
                position=block.position,
                object_id=block.object,
                status="started",
            )
        )
        prev_brief = flat_blocks[index - 1][1].brief if index > 0 else ""
        next_brief = flat_blocks[index + 1][1].brief if index + 1 < len(flat_blocks) else ""
        intent_guidance = ""
        intent_rec = intents.get(block.intent)
        if isinstance(intent_rec, dict):
            intent_guidance = str(intent_rec.get("generation_guidance") or "")
        planned = PlannedBlock(
            id=block.id,
            position=block.position,
            intent=block.intent,
            object=block.object,  # type: ignore[arg-type]
            evidence=block.evidence or "Form-assigned block.",
            brief=block.brief,
            placement=block.placement,
            source_question_ids=list(block.source_question_ids),
        )
        ctx = WriterContext(
            planned=planned,
            terminology=tuple(packet.scope.terminology),
            neighbour_summaries=(prev_brief, next_brief, intent_guidance),
            item_records=item_records,
            lesson_context={
                "objective": packet.lesson.objective,
                "grade_level": packet.lesson.grade_level,
                "subject": packet.lesson.subject,
                "anchor": packet.anchor.model_dump(mode="json"),
                "must_not_introduce": [
                    entry.statement for entry in packet.scope.must_not_introduce
                ],
            },
            generation_id=generation_id,
            use_llm=True,
        )
        try:
            result = await dispatch_writer_async(ctx)
            if result.object == "figure":
                rid = stable_figure_request_id(
                    generation_id=generation_id, block_id=block.id
                )
                content = dict(result.content)
                asset = dict(content.get("asset") or {})
                asset["request_id"] = rid
                content["asset"] = asset
                result.request_id = rid
                result.content = content
            results.append(result)
            await repo.save_block_result(
                block.id,
                {
                    "object": result.object,
                    "intent": result.intent,
                    "status": result.status,
                    "content": result.content,
                    "request_id": result.request_id,
                },
            )
            await repo.append_event(
                make_event(
                    "block_ready" if result.status == "ready" else "visual_pending",
                    generation_id=generation_id,
                    section_id=slot_id,
                    block_id=block.id,
                    position=block.position,
                    object_id=block.object,
                    status=result.status,
                )
            )
        except Exception as exc:
            await repo.append_event(
                make_event(
                    "block_failed",
                    generation_id=generation_id,
                    section_id=slot_id,
                    block_id=block.id,
                    position=block.position,
                    object_id=block.object,
                    status="failed",
                    error=str(exc),
                )
            )
            raise
    return results


async def execute_after_teaching_approval(
    *,
    session: AsyncSession,
    generation_id: str,
    packet: ImmutableLessonPacket,
    teaching_plan: TeachingPlan,
) -> dict[str, Any]:
    """Form plan → write blocks → assemble/persist LectioDocumentV2."""
    repo = PageDocumentRepository(session, generation_id)
    await repo.append_event(
        make_event("form_plan_started", generation_id=generation_id, status="started")
    )
    form_result = await run_form_planner(
        packet, teaching_plan, generation_id=generation_id
    )
    await repo.save_form_plan(
        plan=form_result.plan.model_dump(mode="json"),
        validation=form_result.validation.to_dict(),
        qc=form_result.qc,
        prompt=form_result.prompt,
        raw=form_result.raw_response,
    )
    await repo.append_event(
        make_event("form_plan_ready", generation_id=generation_id, status="ready")
    )

    writer_results = await write_form_blocks(
        generation_id=generation_id,
        form_plan=form_result.plan,
        packet=packet,
        repo=repo,
    )

    await repo.append_event(
        make_event("document_assembling", generation_id=generation_id, status="assembling")
    )
    section_plans = form_plan_to_section_plans(form_result.plan)
    sections_out = []
    for section in form_result.plan.sections:
        ordered = []
        for block in section.blocks:
            match = next((r for r in writer_results if r.block_id == block.id), None)
            if match is None:
                raise RuntimeError(f"missing writer result for {block.id}")
            ordered.append(match)
        sections_out.append(
            assemble_section(
                section_id=section.slot_id,
                title=section.slot_id.title(),
                plan=section_plans[section.slot_id],
                writer_results=ordered,
            )
        )

    document = assemble_document_v2(
        title=packet.lesson.objective[:80],
        sections=sections_out,
        metadata={
            "catalogue_version": "1.1.0",
            "resource_type": "lesson",
            "objective": packet.lesson.objective,
            "subject": packet.lesson.subject,
            "grade_level": packet.lesson.grade_level,
            "knowledge_type": packet.lesson.knowledge_type,
            "lesson_mode": packet.lesson.lesson_mode,
            "native_whole_lesson": True,
        },
    )
    generation = await session.get(GenerationModel, generation_id)
    if generation is None:
        raise KeyError(generation_id)
    generation.document_json = persist_document_json(generation.document_json, document)
    generation.status = "completed"
    await session.commit()
    await repo.append_event(
        make_event("document_ready", generation_id=generation_id, status="ready")
    )
    await repo.bump_document_revision()
    return {
        "form_plan": form_result.plan.model_dump(mode="json"),
        "document": document,
        "writer_count": len(writer_results),
    }
