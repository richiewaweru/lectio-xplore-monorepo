from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.capabilities import require_xplore_v2
from core.database.models import GenerationModel, LearningPackModel
from core.dependencies import get_async_session
from core.entities.user import User


router = APIRouter(
    prefix="/api/v1/legacy-units",
    tags=["units", "legacy-compatibility"],
    dependencies=[Depends(require_xplore_v2)],
)


def _objective(pack: LearningPackModel) -> str:
    try:
        plan = json.loads(pack.pack_plan_json)
    except (TypeError, ValueError):
        return f"Legacy learning pack for {pack.topic}."
    if not isinstance(plan, dict):
        return f"Legacy learning pack for {pack.topic}."
    learning_job = plan.get("learning_job")
    if isinstance(learning_job, dict) and isinstance(learning_job.get("objective"), str):
        return learning_job["objective"]
    pack_plan = plan.get("pack_learning_plan")
    if isinstance(pack_plan, dict) and isinstance(pack_plan.get("objective"), str):
        return pack_plan["objective"]
    return f"Legacy learning pack for {pack.topic}."


def _payload(pack: LearningPackModel, generations: list[GenerationModel]) -> dict[str, Any]:
    return {
        "id": f"legacy:{pack.id}",
        "kind": "legacy_unit",
        "legacy_pack_id": pack.id,
        "title": pack.topic,
        "subject": pack.subject,
        "destination_objective": _objective(pack),
        "status": pack.status,
        "resource_count": pack.resource_count,
        "completed_count": pack.completed_count,
        "created_at": pack.created_at,
        "lesson": {
            "title": pack.topic,
            "pack_id": pack.id,
            "generation_ids": [generation.id for generation in generations],
            "open_href": f"/packs/{pack.id}",
        },
        "computed": True,
        "migration_required": False,
    }


@router.get("")
async def list_legacy_units(
    current_user: User = Depends(require_xplore_v2),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    packs = list(
        await session.scalars(
            select(LearningPackModel)
            .where(
                LearningPackModel.user_id == current_user.id,
                LearningPackModel.learning_job_type != "xplore_variants",
            )
            .order_by(LearningPackModel.created_at.desc(), LearningPackModel.id.desc())
            .limit(100)
        )
    )
    if not packs:
        return []
    generations = list(
        await session.scalars(
            select(GenerationModel)
            .where(GenerationModel.pack_id.in_([pack.id for pack in packs]))
            .order_by(GenerationModel.created_at, GenerationModel.id)
        )
    )
    by_pack: dict[str, list[GenerationModel]] = {pack.id: [] for pack in packs}
    for generation in generations:
        if generation.pack_id in by_pack:
            by_pack[generation.pack_id].append(generation)
    return [_payload(pack, by_pack[pack.id]) for pack in packs]


@router.get("/{pack_id}")
async def get_legacy_unit(
    pack_id: str,
    current_user: User = Depends(require_xplore_v2),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    pack = await session.get(LearningPackModel, pack_id)
    if (
        pack is None
        or pack.user_id != current_user.id
        or pack.learning_job_type == "xplore_variants"
    ):
        raise HTTPException(status_code=404, detail="Legacy unit wrapper not found.")
    generations = list(
        await session.scalars(
            select(GenerationModel)
            .where(GenerationModel.pack_id == pack.id)
            .order_by(GenerationModel.created_at, GenerationModel.id)
        )
    )
    return _payload(pack, generations)
