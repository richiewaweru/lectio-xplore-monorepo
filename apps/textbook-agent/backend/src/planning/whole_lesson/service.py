"""Orchestrate teaching-plan creation after approved items exist."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, GenerationModel, PackItemModel
from planning.approved_items import ItemPoolEmptyError, load_approved_item_records
from planning.whole_lesson.events import make_event
from planning.whole_lesson.legality import (
    build_lesson_legality_snapshot,
    validate_legality_snapshot,
)
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.packet_builder import (
    CONCEPTUAL_FIRST_EXPOSURE_SLOTS,
    build_lesson_packet,
)
from planning.whole_lesson.repository import PageDocumentRepository
from planning.whole_lesson.teaching_agent import run_lesson_approach_planner
from planning.whole_lesson.teaching_plan import TeachingPlan
from v3_blueprint.planning.persistence import load_chunked_state


def slot_ids_from_structural_plan(plan_raw: Mapping[str, Any] | dict[str, Any] | None) -> tuple[str, ...]:
    """Derive packet slot IDs from persisted structural-plan section order."""
    sections = (plan_raw or {}).get("sections") or []
    return tuple(
        str(section.get("role") or section.get("id"))
        for section in sections
        if isinstance(section, dict) and (section.get("role") or section.get("id"))
    )


async def _concept_card_for_generation(
    session: AsyncSession, generation: GenerationModel
) -> ConceptCardModel | None:
    pack_id = generation.pack_id or generation.id
    result = await session.execute(
        select(ConceptCardModel)
        .where(ConceptCardModel.pack_id == pack_id)
        .order_by(ConceptCardModel.created_at.asc())
        .limit(1)
    )
    card = result.scalar_one_or_none()
    if card is not None:
        return card
    # Fallback: items may be keyed to generation id as pack
    result = await session.execute(
        select(ConceptCardModel)
        .where(ConceptCardModel.pack_id == generation.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_packet_for_generation(
    session: AsyncSession,
    generation: GenerationModel,
    *,
    require_items: bool = True,
) -> ImmutableLessonPacket:
    chunked = await load_chunked_state(generation.id, session)
    context = chunked.get("context") or {}
    plan_raw = chunked.get("structural_plan") or {}
    if isinstance(generation.planning_spec_json, str) and generation.planning_spec_json:
        import json

        try:
            plan_raw = json.loads(generation.planning_spec_json)
        except json.JSONDecodeError:
            pass

    card = await _concept_card_for_generation(session, generation)
    if card is None:
        raise ItemPoolEmptyError(card_id="missing-card", pack_id=generation.pack_id)

    items = await load_approved_item_records(
        session=session,
        concept_card=card,
        require_nonempty=require_items,
    )

    anchor = plan_raw.get("anchor") or {}
    anchor_desc = (
        anchor.get("example")
        or anchor.get("description")
        or context.get("anchor")
        or "lesson-anchor"
    )
    anchor_id = str(anchor.get("id") or "anchor-1")

    misconceptions = []
    cards = plan_raw.get("cards") or []
    if cards and isinstance(cards[0], dict):
        misconceptions = list(cards[0].get("misconceptions") or [])
    elif card.misconceptions:
        misconceptions = list(card.misconceptions)

    scope = context.get("scope_contract") or {}
    slot_ids = slot_ids_from_structural_plan(plan_raw if isinstance(plan_raw, dict) else {})
    return build_lesson_packet(
        path_lesson_id=str(context.get("path_lesson_id") or generation.id),
        subject=str(generation.subject or context.get("subject") or "General"),
        grade_level=str(context.get("grade_level") or "Grade"),
        objective=str(
            (plan_raw.get("lesson_intent") or {}).get("goal")
            or card.objective
            or generation.context
            or "Lesson objective"
        ),
        knowledge_type=str(
            context.get("primary_knowledge_type")
            or plan_raw.get("knowledge_type")
            or "conceptual"
        ),
        lesson_mode=str(context.get("lesson_mode") or plan_raw.get("lesson_mode") or "first_exposure"),
        must_establish=scope.get("must_establish") or context.get("must_establish") or [],
        must_not_introduce=scope.get("must_not_introduce")
        or context.get("exclusions")
        or [],
        terminology=list(scope.get("terminology") or []),
        anchor_id=anchor_id,
        anchor_description=str(anchor_desc),
        misconceptions=[
            item
            if isinstance(item, dict)
            else {"id": f"misconception-{i+1}", "statement": str(item)}
            for i, item in enumerate(misconceptions)
        ],
        prior_established=list(context.get("prior_established") or plan_raw.get("prior_knowledge") or []),
        approved_items=items,
        slot_ids=slot_ids or CONCEPTUAL_FIRST_EXPOSURE_SLOTS,
    )


async def run_and_persist_teaching_plan(
    session: AsyncSession,
    generation_id: str,
    *,
    require_items: bool = True,
) -> dict[str, Any]:
    generation = await session.get(GenerationModel, generation_id)
    if generation is None:
        raise KeyError(generation_id)

    repo = PageDocumentRepository(session, generation_id)
    await repo.append_event(
        make_event("teaching_plan_started", generation_id=generation_id, status="started")
    )
    packet = await build_packet_for_generation(
        session, generation, require_items=require_items
    )
    await repo.save_lesson_packet(packet.model_dump(mode="json"))

    legality = build_lesson_legality_snapshot(packet)
    validate_legality_snapshot(packet, legality)
    await repo.save_lesson_legality(legality.model_dump(mode="json"))

    result = await run_lesson_approach_planner(
        packet,
        legality=legality,
        generation_id=generation_id,
        require_items=require_items,
    )
    await repo.save_catalogue_meta(
        version=result.teaching_guidance.catalogue_version,
        teaching_projection_hash=result.teaching_guidance.projection_hash,
    )
    state = await repo.save_teaching_plan(
        plan=result.plan.model_dump(mode="json"),
        validation=result.validation.to_dict(),
        qc=result.qc,
        prompt=result.prompt,
        raw=result.raw_response,
        stage="awaiting_teaching_approval",
    )
    await repo.append_event(
        make_event(
            "teaching_plan_ready",
            generation_id=generation_id,
            status="ready",
            arc=result.plan.arc,
        )
    )
    await repo.append_event(
        make_event(
            "awaiting_teaching_approval",
            generation_id=generation_id,
            status="pending",
        )
    )
    return {
        "teaching_plan": result.plan.model_dump(mode="json"),
        "validation": result.validation.to_dict(),
        "qc": result.qc,
        "review": state.get("teaching_review"),
        "packet": packet.model_dump(mode="json"),
    }


async def approve_teaching_and_queue(
    session: AsyncSession,
    generation_id: str,
    *,
    expected_revision: int,
    reviewed_by: str | None = None,
    teacher_note: str | None = None,
) -> dict[str, Any]:
    """Validate revision, persist approval, transition to queued. Never runs planners inline."""
    repo = PageDocumentRepository(session, generation_id)
    state = await repo.load_page_generation_state()
    if not state.get("teaching_plan"):
        raise RuntimeError("no teaching plan to approve")
    state = await repo.save_teaching_review(
        status="approved",
        expected_revision=expected_revision,
        reviewed_by=reviewed_by,
        teacher_note=teacher_note,
        queue=True,
    )
    generation = await session.get(GenerationModel, generation_id)
    status = str(generation.status if generation else "queued") or "queued"
    return {
        "status": status,
        "teaching_review": state.get("teaching_review"),
        "queued": True,
    }


async def approve_teaching_and_execute(
    session: AsyncSession,
    generation_id: str,
    *,
    expected_revision: int,
    reviewed_by: str | None = None,
    teacher_note: str | None = None,
) -> dict[str, Any]:
    """Queue approval only (Phase 02). Execution is owned by the leased worker."""
    return await approve_teaching_and_queue(
        session,
        generation_id,
        expected_revision=expected_revision,
        reviewed_by=reviewed_by,
        teacher_note=teacher_note,
    )


def generation_is_native_whole_lesson(
    generation: GenerationModel | None = None,
    *,
    state: Mapping[str, Any] | None = None,
) -> bool:
    """Delegate to planning.whole_lesson.native_routing (GenerationModel-first API)."""
    from planning.whole_lesson.native_routing import (
        generation_is_native_whole_lesson as _detect,
    )

    return _detect(state, generation)
