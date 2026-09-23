from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, GenerationModel, GenerationStepModel
from core.database.session import async_session_factory
from print.http.v3_studio.dtos import V3InputForm, V3SignalSummary
from curriculum.planning.models import (
    ConceptCard,
    Misconception,
    SectionBrief,
    StructuralPlan,
    VariantSpec,
)

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]

DEFAULT_VARIANT_ID = "everyone"
DEFAULT_KIND = "lesson"


@asynccontextmanager
async def _session_scope(session: AsyncSession | None):
    if session is not None:
        yield session, False
        return
    async with async_session_factory() as managed:
        yield managed, True


async def _read_chunked_state(
    generation_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    result = await session.execute(
        text("SELECT chunked_state_json FROM generations WHERE id = :generation_id"),
        {"generation_id": generation_id},
    )
    row = result.first()
    if row is None:
        raise ValueError(f"Generation '{generation_id}' not found")
    raw = row[0]
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


async def _write_chunked_state(
    generation_id: str,
    state: dict[str, Any],
    session: AsyncSession,
) -> None:
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        await session.execute(
            text(
                "UPDATE generations "
                "SET chunked_state_json = CAST(:state AS JSONB) "
                "WHERE id = :generation_id"
            ),
            {"generation_id": generation_id, "state": json.dumps(state)},
        )
    else:
        await session.execute(
            text(
                "UPDATE generations "
                "SET chunked_state_json = :state "
                "WHERE id = :generation_id"
            ),
            {"generation_id": generation_id, "state": json.dumps(state)},
        )


def fold(rows: list[GenerationStepModel] | list[Any]) -> dict[str, Any]:
    """Build the part-output maps today's callers expect from immutable step rows.

    State is computed rather than stored as a mutable section_briefs blob so that
    concurrent lane/step writers cannot clobber each other via read-modify-write.
    Do not reintroduce a cached mutable copy of these maps.
    """
    section_briefs: dict[str, Any] = {}
    part_prose: dict[str, Any] = {}
    part_questions: dict[str, Any] = {}
    part_visuals: dict[str, Any] = {}
    for row in rows:
        payload = row.payload if hasattr(row, "payload") else row.get("payload")
        part_id = row.part_id if hasattr(row, "part_id") else row["part_id"]
        step = row.step if hasattr(row, "step") else row["step"]
        if step == "brief":
            section_briefs[part_id] = payload
        elif step == "prose":
            part_prose[part_id] = payload
        elif step == "questions":
            part_questions[part_id] = payload
        elif step == "visual":
            part_visuals[part_id] = payload
    return {
        "section_briefs": section_briefs,
        "part_prose": part_prose,
        "part_questions": part_questions,
        "part_visuals": part_visuals,
    }


async def load_steps(
    generation_id: str,
    session: AsyncSession | None = None,
    *,
    variant_id: str | None = None,
) -> list[GenerationStepModel]:
    async with _session_scope(session) as (db, _):
        stmt = select(GenerationStepModel).where(
            GenerationStepModel.generation_id == generation_id
        )
        if variant_id is not None:
            stmt = stmt.where(GenerationStepModel.variant_id == variant_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())


async def insert_step(
    generation_id: str,
    *,
    part_id: str,
    step: str,
    payload: dict[str, Any],
    variant_id: str = DEFAULT_VARIANT_ID,
    kind: str = DEFAULT_KIND,
    session: AsyncSession | None = None,
) -> GenerationStepModel:
    """Append one immutable step row. Simultaneous inserts need no coordination."""
    import uuid

    row = GenerationStepModel(
        id=str(uuid.uuid4()),
        generation_id=generation_id,
        part_id=part_id,
        variant_id=variant_id,
        step=step,
        kind=kind,
        payload=payload,
    )
    async with _session_scope(session) as (db, should_commit):
        db.add(row)
        if should_commit:
            await db.commit()
            await db.refresh(row)
        else:
            await db.flush()
        return row


async def step_exists(
    generation_id: str,
    *,
    part_id: str,
    step: str,
    variant_id: str = DEFAULT_VARIANT_ID,
    session: AsyncSession | None = None,
) -> bool:
    async with _session_scope(session) as (db, _):
        result = await db.execute(
            select(GenerationStepModel.id).where(
                GenerationStepModel.generation_id == generation_id,
                GenerationStepModel.part_id == part_id,
                GenerationStepModel.variant_id == variant_id,
                GenerationStepModel.step == step,
            )
        )
        return result.scalar_one_or_none() is not None


async def load_step_payload(
    generation_id: str,
    *,
    part_id: str,
    step: str,
    variant_id: str = DEFAULT_VARIANT_ID,
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Load one immutable checkpoint payload for a resumable execution step."""
    async with _session_scope(session) as (db, _):
        result = await db.execute(
            select(GenerationStepModel.payload)
            .where(
                GenerationStepModel.generation_id == generation_id,
                GenerationStepModel.part_id == part_id,
                GenerationStepModel.variant_id == variant_id,
                GenerationStepModel.step == step,
            )
            .order_by(GenerationStepModel.created_at.desc())
            .limit(1)
        )
        payload = result.scalar_one_or_none()
        return dict(payload) if isinstance(payload, Mapping) else None


async def persist_chunked_state(
    generation_id: str,
    update: dict,
    session: AsyncSession | None = None,
) -> None:
    async with _session_scope(session) as (db, should_commit):
        current = await _read_chunked_state(generation_id, db)
        current.update(update)
        await _write_chunked_state(generation_id, current, db)
        if should_commit:
            await db.commit()


def _attempt_key(record: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(record.get("correlation_id") or ""),
        str(record.get("card_id") or ""),
        int(record.get("attempt") or 0),
    )


def _failed_card_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("card_id") or ""),
        str(record.get("correlation_id") or ""),
    )


def merge_failed_card_records(
    prior: list[Any],
    incoming: list[Any] | None,
) -> list[dict[str, Any]]:
    """Append-only merge of failed_cards, deduped by (card_id, correlation_id)."""
    merged = [dict(row) for row in prior if isinstance(row, dict)]
    seen = {_failed_card_key(row) for row in merged}
    for row in incoming or []:
        if not isinstance(row, dict):
            continue
        key = _failed_card_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(row))
    return merged


def merge_item_generation_summary(
    existing: Mapping[str, Any] | None,
    summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge an item-generation summary without wiping attempt/failed_card journals."""
    base = dict(existing or {})
    incoming = dict(summary or {})
    prior_attempts = [
        dict(row) for row in (base.get("attempts") or []) if isinstance(row, dict)
    ]
    prior_failed = [
        dict(row) for row in (base.get("failed_cards") or []) if isinstance(row, dict)
    ]
    base.update(incoming)
    # Prefer existing journal when summary omits/empties it; still merge incoming rows.
    summary_attempts = [
        dict(row)
        for row in (incoming.get("attempts") or [])
        if isinstance(row, dict)
    ]
    seen = {_attempt_key(row) for row in prior_attempts}
    for row in summary_attempts:
        key = _attempt_key(row)
        if key in seen:
            continue
        seen.add(key)
        prior_attempts.append(row)
    base["attempts"] = prior_attempts
    base["failed_cards"] = merge_failed_card_records(
        prior_failed,
        list(incoming.get("failed_cards") or []),
    )
    return base


async def append_item_attempt_records(
    generation_id: str,
    *,
    attempts: list[dict[str, Any]],
    failed_cards: list[dict[str, Any]] | None = None,
    pack_id: str | None = None,
    session: AsyncSession | None = None,
    worker_id: str | None = None,
    lease_token: int | None = None,
) -> dict[str, Any]:
    """Append-only merge of item-generation attempt journals into chunked state.

    Never wipes prior attempts. Dedupes by (correlation_id, card_id, attempt).
    When worker_id/lease_token are provided, lease verification and journal write
    share one row-locked transaction.
    """
    leased = worker_id is not None or lease_token is not None
    if leased and (worker_id is None or lease_token is None):
        raise ValueError("worker_id and lease_token must both be provided for leased writes")

    async with _session_scope(session) as (db, should_commit):
        if leased:
            from print.generation.whole_lesson.repository import (
                PageDocumentRepository,
                _page_state_lock,
            )

            lock = await _page_state_lock(generation_id)
            async with lock:
                repo = PageDocumentRepository(db, generation_id)
                await repo.require_execution_lease(
                    worker_id=str(worker_id),
                    lease_token=int(lease_token),
                )
                item_gen = await _merge_item_attempt_journal(
                    generation_id,
                    db,
                    attempts=attempts,
                    failed_cards=failed_cards,
                    pack_id=pack_id,
                )
                if should_commit:
                    await db.commit()
                return item_gen

        item_gen = await _merge_item_attempt_journal(
            generation_id,
            db,
            attempts=attempts,
            failed_cards=failed_cards,
            pack_id=pack_id,
        )
        if should_commit:
            await db.commit()
        return item_gen


async def _merge_item_attempt_journal(
    generation_id: str,
    db: AsyncSession,
    *,
    attempts: list[dict[str, Any]],
    failed_cards: list[dict[str, Any]] | None,
    pack_id: str | None,
) -> dict[str, Any]:
    current = await _read_chunked_state(generation_id, db)
    item_gen = dict(current.get("item_generation") or {})
    existing = [
        dict(row)
        for row in (item_gen.get("attempts") or [])
        if isinstance(row, dict)
    ]
    seen = {_attempt_key(row) for row in existing}
    for record in attempts:
        if not isinstance(record, dict):
            continue
        key = _attempt_key(record)
        if key in seen:
            continue
        seen.add(key)
        existing.append(dict(record))
    item_gen["attempts"] = existing
    if pack_id:
        item_gen["pack_id"] = pack_id
    if failed_cards:
        item_gen["failed_cards"] = merge_failed_card_records(
            [
                dict(row)
                for row in (item_gen.get("failed_cards") or [])
                if isinstance(row, dict)
            ],
            failed_cards,
        )
    current["item_generation"] = item_gen
    await _write_chunked_state(generation_id, current, db)
    return item_gen

async def persist_structural_plan(
    generation_id: str,
    plan: StructuralPlan,
    session: AsyncSession | None = None,
    *,
    signals: V3SignalSummary | None = None,
    form: V3InputForm | None = None,
    resource_spec: dict | None = None,
) -> None:
    async with _session_scope(session) as (db, should_commit):
        generation = await db.get(GenerationModel, generation_id)
        if generation is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        pack_id = generation.pack_id or generation_id
        effective_cards: list[ConceptCard] = []
        existing_by_slug: dict[str, ConceptCardModel | None] = {}
        for planned_card in plan.cards:
            existing_result = await db.execute(
                select(ConceptCardModel).where(
                    ConceptCardModel.pack_id == pack_id,
                    ConceptCardModel.slug == planned_card.id,
                )
            )
            existing = existing_result.scalar_one_or_none()
            existing_by_slug[planned_card.id] = existing
            if existing is None or not existing.teacher_edited:
                effective_cards.append(planned_card)
                continue
            effective_cards.append(
                planned_card.model_copy(
                    update={
                        "title": existing.title,
                        "objective": existing.objective,
                        "prereqs": list(existing.prereqs or []),
                        "misconceptions": [
                            Misconception.model_validate(row)
                            for row in (
                                existing.misconceptions
                                if isinstance(existing.misconceptions, list)
                                else []
                            )
                            if isinstance(row, dict)
                        ],
                        "no_known_misconceptions": not bool(
                            existing.misconceptions
                        ),
                    },
                    deep=True,
                )
            )
        effective_plan = plan.model_copy(
            update={"cards": effective_cards},
            deep=True,
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "plan_ready",
                "structural_plan": effective_plan.model_dump(mode="json"),
                "section_briefs": {s.id: None for s in effective_plan.sections},
                "failed_sections": [],
                "context": {
                    "signals": (
                        signals.model_dump(mode="json")
                        if signals is not None
                        else None
                    ),
                    "form": form.model_dump(mode="json") if form is not None else None,
                    "resource_spec": resource_spec,
                },
            },
            session=db,
        )

        for card in effective_plan.cards:
            existing = existing_by_slug.get(card.id)
            if existing is not None and existing.teacher_edited:
                continue

            payload = {
                "pack_id": pack_id,
                "slug": card.id,
                "title": card.title,
                "objective": card.objective,
                "prereqs": list(card.prereqs),
                "misconceptions": [
                    misconception.model_dump(mode="json")
                    for misconception in card.misconceptions
                ],
            }
            if existing is None:
                db.add(ConceptCardModel(id=f"{pack_id}:{card.id}", **payload))
            else:
                for field, value in payload.items():
                    setattr(existing, field, value)

        if should_commit:
            await db.commit()


async def persist_section_brief(
    generation_id: str,
    brief: SectionBrief,
    session: AsyncSession | None = None,
) -> None:
    async with _session_scope(session) as (db, should_commit):
        if getattr(brief, "_failed", False):
            current = await _read_chunked_state(generation_id, db)
            failed = list(current.get("failed_sections", []) or [])
            if brief.section_id not in failed:
                failed.append(brief.section_id)
            current["failed_sections"] = failed
            current["stage"] = f"section_{brief.section_id}_failed"
            # Do not write section_briefs into the mutable blob — no brief step row
            # means resume will rebuild this part.
            await _write_chunked_state(generation_id, current, db)
        else:
            await insert_step(
                generation_id,
                part_id=brief.section_id,
                step="brief",
                payload=brief.model_dump(mode="json"),
                session=db,
            )
            current = await _read_chunked_state(generation_id, db)
            failed = [
                section
                for section in current.get("failed_sections", [])
                if section != brief.section_id
            ]
            current["failed_sections"] = failed
            current["stage"] = f"section_{brief.section_id}_complete"
            # Keep placeholder map keys for UI, but fold() is the source of truth.
            section_briefs = dict(current.get("section_briefs") or {})
            section_briefs.setdefault(brief.section_id, None)
            current["section_briefs"] = section_briefs
            await _write_chunked_state(generation_id, current, db)
        if should_commit:
            await db.commit()


async def load_chunked_state(
    generation_id: str,
    session: AsyncSession | None = None,
) -> dict:
    async with _session_scope(session) as (db, _):
        state = await _read_chunked_state(generation_id, db)
        if not state:
            raise ValueError(
                f"No chunked state found for generation {generation_id}"
            )
        rows = await load_steps(generation_id, db)
        folded = fold(rows)
        # Overlay folded part outputs onto generation-level metadata from the blob.
        placeholders = dict(state.get("section_briefs") or {})
        placeholders.update(folded.get("section_briefs") or {})
        state["section_briefs"] = placeholders
        if folded.get("part_prose"):
            state["part_prose"] = folded["part_prose"]
        if folded.get("part_questions"):
            state["part_questions"] = folded["part_questions"]
        if folded.get("part_visuals"):
            state["part_visuals"] = folded["part_visuals"]
        return state


async def resume_stage2(
    generation_id: str,
    session: AsyncSession | None = None,
    emit_event: EmitFn | None = None,
) -> list[SectionBrief]:
    """Legacy stage2 back half is disabled. Preserved as a historical disabled stub."""
    raise RuntimeError("Legacy stage2 back half is disabled; use native whole-lesson path")



__all__ = [
    "append_item_attempt_records",
    "fold",
    "insert_step",
    "load_chunked_state",
    "load_step_payload",
    "load_steps",
    "merge_failed_card_records",
    "merge_item_generation_summary",
    "persist_chunked_state",
    "persist_section_brief",
    "persist_structural_plan",
    "resume_stage2",
    "step_exists",
]
