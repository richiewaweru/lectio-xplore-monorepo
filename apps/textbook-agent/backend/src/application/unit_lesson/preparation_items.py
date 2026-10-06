"""Per-card practice-item generation for a Preparation Run (Option D, 3A).

One ``items:{concept_card_id}`` work item calls :func:`generate_card_items` for
exactly one concept card.  The single-card function keeps the rules the old
whole-pack loop had: a card that already has five fresh items is skipped, every
provider attempt is journaled into the preparation's chunked state, and
``write_pack_item_rows`` never overwrites a teacher-edited row.

The caller owns lease fencing: ``fence`` is awaited immediately before the pack
rows are written so a worker that lost its work-item lease cannot overwrite the
winner's rows.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, GenerationModel, PackItemModel
from curriculum.backbone.models import backbone_hash
from curriculum.backbone.persistence import load_backbone
from curriculum.items.generator import ItemGenerationResult, ItemGenerationRun
from curriculum.planning.models import (
    ConceptCard,
    Misconception,
    StructuralPlan,
    VariantSpec,
    adapt_legacy_structural_plan,
)
from curriculum.planning.persistence import append_item_attempt_records, load_chunked_state
from print.http.v3_studio.dtos import V3InputForm, V3SignalSummary

logger = logging.getLogger(__name__)

FRESH_ITEMS_PER_CARD = 5

ItemRunner = Callable[..., Awaitable[ItemGenerationRun]]
SessionFactory = Callable[[], Any]
Fence = Callable[[], Awaitable[None]]


def decode_chunked_context(
    state: dict[str, Any],
) -> tuple[V3SignalSummary, V3InputForm, dict[str, Any]]:
    context = state.get("context")
    if not isinstance(context, dict):
        raise TypeError("Chunked context is missing.")
    signals_raw = context.get("signals")
    form_raw = context.get("form")
    resource_spec = context.get("resource_spec")
    if not isinstance(signals_raw, dict) or not isinstance(form_raw, dict):
        raise TypeError("Chunked context is incomplete.")
    if not isinstance(resource_spec, dict):
        raise TypeError("Chunked resource_spec is missing.")
    return (
        V3SignalSummary.model_validate(signals_raw),
        V3InputForm.model_validate(form_raw),
        resource_spec,
    )


def approved_card_for_items(
    row: ConceptCardModel,
    *,
    subject: str,
    level: str,
    notation: str | None,
) -> ConceptCard:
    misconceptions = [
        Misconception.model_validate(item)
        for item in (row.misconceptions or [])
        if isinstance(item, dict)
    ]
    return ConceptCard(
        id=row.id,
        title=row.title,
        objective=row.objective,
        prereqs=list(row.prereqs or []),
        misconceptions=misconceptions,
    ).with_item_context(subject=subject, level=level, notation=notation)


def item_row_teacher_edited(row: PackItemModel) -> bool:
    return any(
        isinstance(option, dict) and option.get("teacher_edited") is True
        for option in (row.options or [])
    )


def _stored_backbone_ref(ref: Any, digest: str | None) -> dict[str, Any] | None:
    if ref is None or digest is None:
        return None
    return {"target": ref.target, "figure_id": ref.figure_id, "backbone_hash": digest}


def item_row_matches_backbone(row: PackItemModel, digest: str | None) -> bool:
    """True when the row may be reused under the current backbone (None = no backbone)."""
    if digest is None:
        return True
    ref = row.backbone_ref
    return isinstance(ref, dict) and ref.get("backbone_hash") == digest


async def write_pack_item_rows(
    session: AsyncSession,
    pack_id: str,
    results: list[ItemGenerationResult],
    *,
    backbone_hash_value: str | None = None,
) -> None:
    for result in results:
        stored = await session.execute(
            select(PackItemModel).where(
                PackItemModel.pack_id == pack_id,
                PackItemModel.card_id == result.card_id,
            )
        )
        existing_rows = {row.id: row for row in stored.scalars()}
        generated_ids: set[str] = set()
        for item in result.items:
            correct = next(option for option in item.options if option.correct)
            db_id = f"{pack_id}:{item.question_id}"
            generated_ids.add(db_id)
            existing = existing_rows.get(db_id)
            if existing is not None and item_row_teacher_edited(existing):
                existing.stale = True
                continue
            payload = {
                "stem": item.prompt_text,
                "options": [
                    {**option.model_dump(mode="json"), "teacher_edited": False}
                    for option in item.options
                ],
                "correct_key": correct.key,
                "diagnoses": {option.key: option.diagnoses for option in item.options},
                "stale": False,
                "backbone_ref": _stored_backbone_ref(
                    result.backbone_refs.get(item.question_id), backbone_hash_value
                ),
            }
            if existing is None:
                session.add(
                    PackItemModel(id=db_id, pack_id=pack_id, card_id=result.card_id, **payload)
                )
            else:
                for field, value in payload.items():
                    setattr(existing, field, value)

        for db_id, existing in existing_rows.items():
            if db_id in generated_ids:
                continue
            if item_row_teacher_edited(existing):
                existing.stale = True
            else:
                await session.delete(existing)


async def persist_item_results(
    pack_id: str,
    results: list[ItemGenerationResult],
    *,
    session_factory: SessionFactory | None = None,
    backbone_hash_value: str | None = None,
) -> None:
    if session_factory is None:
        from core.database.session import async_session_factory as session_factory
    async with session_factory() as session:
        await write_pack_item_rows(
            session, pack_id, results, backbone_hash_value=backbone_hash_value
        )
        await session.commit()


async def load_structural_plan(state: dict[str, Any], *, generation_id: str) -> StructuralPlan:
    plan_raw = state.get("structural_plan")
    if not isinstance(plan_raw, dict):
        raise TypeError("No structural plan available for item generation")
    plan = adapt_legacy_structural_plan(plan_raw, source=f"generation:{generation_id}")
    variant_raw = state.get("variant_spec")
    if isinstance(variant_raw, dict):
        plan = plan.with_variant(VariantSpec.model_validate(variant_raw))
    return plan


async def _journal(
    session_factory: SessionFactory,
    *,
    generation_id: str,
    pack_id: str,
    attempts: list[dict[str, Any]],
    failed_cards: list[dict[str, Any]] | None,
) -> None:
    """Append attempt journals under the generation row lock (no lost updates)."""
    if not attempts and not failed_cards:
        return
    async with session_factory() as session:
        await session.execute(
            select(GenerationModel.id)
            .where(GenerationModel.id == generation_id)
            .with_for_update()
        )
        await append_item_attempt_records(
            generation_id,
            attempts=attempts,
            failed_cards=failed_cards,
            pack_id=pack_id,
            session=session,
        )
        await session.commit()


async def generate_card_items(
    *,
    session_factory: SessionFactory,
    generation_id: str,
    card_id: str,
    item_runner: ItemRunner,
    fence: Fence | None = None,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """Generate and persist the practice items of ONE concept card.

    Returns a JSON-safe summary (used as the work item's output).  Raises the
    provider/validation exception of the last attempt after journaling it.
    """
    from curriculum.items import generator as item_gen

    async with session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        pack_id = generation.pack_id or generation.id
        card_row = await session.scalar(
            select(ConceptCardModel).where(
                ConceptCardModel.pack_id == pack_id, ConceptCardModel.id == card_id
            )
        )
        if card_row is None:
            raise ValueError(f"Concept card '{card_id}' not found for generation")
        stored = list(
            (
                await session.scalars(
                    select(PackItemModel).where(
                        PackItemModel.pack_id == pack_id,
                        PackItemModel.card_id == card_id,
                    )
                )
            ).all()
        )
        backbone = await load_backbone(session, generation_id)
        current_hash = backbone_hash(backbone) if backbone is not None else None
        if current_hash is not None:
            # Items written against another (or no) backbone are stale: never reuse them.
            changed = False
            for item in stored:
                if not item.stale and not item_row_matches_backbone(item, current_hash):
                    item.stale = True
                    changed = True
            if changed:
                await session.commit()
        fresh = sum(1 for item in stored if not item.stale) == FRESH_ITEMS_PER_CARD
        state = await load_chunked_state(generation_id, session)
        session.expunge(card_row)

    if fresh:
        return {
            "card_id": card_id,
            "pack_id": pack_id,
            "skipped": True,
            "generated_item_count": 0,
            "needs_review": False,
        }

    plan = await load_structural_plan(state, generation_id=generation_id)
    _signals, form, _resource_spec = decode_chunked_context(state)
    card = approved_card_for_items(
        card_row,
        subject=form.subject,
        level=form.grade_level,
        notation=plan.variant_spec().voice.notation,
    )
    budget = max_attempts if max_attempts is not None else item_gen.ITEM_MAX_ATTEMPTS
    try:
        run = await item_runner(
            card,
            generation_id=generation_id,
            max_attempts=budget,
            **({"backbone": backbone} if backbone is not None else {}),
        )
    except Exception as exc:
        journal = list(getattr(exc, "item_attempts", []) or [])
        failed_row = {
            "card_id": card_id,
            "correlation_id": getattr(exc, "item_correlation_id", None),
            "error": str(exc)[:500],
            "attempts": journal,
        }
        await _journal(
            session_factory,
            generation_id=generation_id,
            pack_id=pack_id,
            attempts=journal,
            failed_cards=[failed_row],
        )
        raise
    await _journal(
        session_factory,
        generation_id=generation_id,
        pack_id=pack_id,
        attempts=list(run.attempts),
        failed_cards=None,
    )
    if fence is not None:
        await fence()
    async with session_factory() as session:
        await write_pack_item_rows(
            session, pack_id, [run.result], backbone_hash_value=current_hash
        )
        await session.commit()
    result = run.result
    return {
        "card_id": card_id,
        "pack_id": pack_id,
        "skipped": False,
        "generated_item_count": len(result.items),
        "needs_review": bool(result.needs_review or result.unmapped_options),
        "missing_misconceptions": list(result.missing_misconceptions),
        "unmapped_options": int(result.unmapped_options),
    }


__all__ = [
    "approved_card_for_items",
    "decode_chunked_context",
    "generate_card_items",
    "item_row_matches_backbone",
    "item_row_teacher_edited",
    "load_structural_plan",
    "persist_item_results",
    "write_pack_item_rows",
]
