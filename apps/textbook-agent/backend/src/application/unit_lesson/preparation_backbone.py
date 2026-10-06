"""Lesson-backbone generation for a Preparation Run.

The single ``backbone`` work item calls :func:`generate_lesson_backbone` once
per run, after the teacher approves the structure and before any ``items:*``
work item exists.  The backbone is stored under ``chunked_state["backbone"]``
(never inside ``structural_plan`` / ``context``, so the run's source hash is
unaffected) and every provider attempt is journaled under
``chunked_state["backbone_generation"]``.

The caller owns lease fencing: ``fence`` is awaited immediately before the
backbone is written so a worker that lost its lease cannot overwrite the
winner's result.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from application.unit_lesson.preparation_items import (
    decode_chunked_context,
    load_structural_plan,
)
from core.database.models import ConceptCardModel, GenerationModel
from curriculum.backbone.inputs import build_backbone_inputs
from curriculum.backbone.persistence import (
    append_backbone_journal,
    load_backbone_record,
    store_backbone,
)
from curriculum.backbone.writer import BACKBONE_MAX_ATTEMPTS, BackboneRun
from curriculum.planning.persistence import load_chunked_state

LOGGER = logging.getLogger(__name__)

BackboneRunner = Callable[..., Awaitable[BackboneRun]]
SessionFactory = Callable[[], Any]
Fence = Callable[[], Awaitable[None]]


async def generate_lesson_backbone(
    *,
    session_factory: SessionFactory,
    generation_id: str,
    backbone_runner: BackboneRunner,
    fence: Fence | None = None,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """Generate and persist the lesson backbone; returns the work item's output summary."""
    async with session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        pack_id = generation.pack_id or generation.id
        rows = list(
            (
                await session.scalars(
                    select(ConceptCardModel)
                    .where(ConceptCardModel.pack_id == pack_id)
                    .order_by(ConceptCardModel.created_at, ConceptCardModel.id)
                )
            ).all()
        )
        card_rows = [
            {
                "id": row.id,
                "title": row.title,
                "objective": row.objective,
                "misconceptions": [
                    dict(item)
                    for item in (row.misconceptions or [])
                    if isinstance(item, dict)
                ],
            }
            for row in rows
        ]
        state = await load_chunked_state(generation_id, session)
        existing = await load_backbone_record(session, generation_id)

    plan = await load_structural_plan(state, generation_id=generation_id)
    _signals, form, _resource_spec = decode_chunked_context(state)
    inputs = build_backbone_inputs(
        structural_plan=plan,
        context=state.get("context") or {},
        card_rows=card_rows,
        subject=form.subject,
        level=form.grade_level,
        notation=plan.variant_spec().voice.notation,
    )
    input_hash = inputs.input_hash()
    if existing is not None and existing[2] == input_hash:
        # Same approved inputs already produced a backbone (e.g. a regenerated
        # plan attempt): reuse it so the already-written questions stay valid.
        backbone, digest, _ = existing
        return _summary(backbone, digest, input_hash, skipped=True)

    budget = max_attempts if max_attempts is not None else BACKBONE_MAX_ATTEMPTS
    try:
        run = await backbone_runner(inputs, generation_id=generation_id, max_attempts=budget)
    except Exception as exc:
        async with session_factory() as session:
            await append_backbone_journal(
                session,
                generation_id,
                attempts=list(getattr(exc, "backbone_attempts", []) or []),
                error=str(exc),
                correlation_id=getattr(exc, "backbone_correlation_id", None),
            )
            await session.commit()
        raise
    if fence is not None:
        await fence()
    async with session_factory() as session:
        digest = await store_backbone(
            session,
            generation_id,
            run.backbone,
            input_hash=input_hash,
            attempts=list(run.attempts),
            correlation_id=run.correlation_id,
        )
        await session.commit()
    return _summary(run.backbone, digest, input_hash, skipped=False)


def _summary(backbone: Any, digest: str, input_hash: str, *, skipped: bool) -> dict[str, Any]:
    return {
        "hash": digest,
        "input_hash": input_hash,
        "skipped": skipped,
        "variant_count": len(backbone.variants),
        "figure_count": len(backbone.figures),
    }


__all__ = ["generate_lesson_backbone"]
