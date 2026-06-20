from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from core.auth.middleware import get_current_user
from core.database.models import LearningPackModel
from core.database.session import async_session_factory
from core.entities.user import User
from learning.models import PackStatusResponse, ResourceStatus
from learning.pack_repository import LearningPackRepository

router = APIRouter(prefix="/api/v1/packs", tags=["learning-packs"])


def get_pack_repository() -> LearningPackRepository:
    return LearningPackRepository(async_session_factory)


@router.get("", response_model=list[PackStatusResponse])
async def list_packs(
    current_user: User = Depends(get_current_user),
    pack_repo: LearningPackRepository = Depends(get_pack_repository),
    limit: int = 20,
) -> list[PackStatusResponse]:
    packs = await pack_repo.list_by_user(current_user.id, limit=limit)
    return [_pack_to_status(pack, []) for pack in packs]


@router.get("/{pack_id}", response_model=PackStatusResponse)
async def get_pack_status(
    pack_id: str,
    current_user: User = Depends(get_current_user),
    pack_repo: LearningPackRepository = Depends(get_pack_repository),
) -> PackStatusResponse:
    pack = await pack_repo.find_by_id(pack_id)
    if pack is None or pack.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pack not found.")
    generations = await pack_repo.generations_for_pack(pack_id)
    return _pack_to_status(pack, generations)


def _pack_to_status(pack: LearningPackModel, generations: list) -> PackStatusResponse:
    plan_data = json.loads(pack.pack_plan_json)
    resource_rows = [
        resource for resource in plan_data.get("resources", []) if resource.get("enabled", True)
    ]
    generations_by_resource = {
        generation.pack_resource_id: generation
        for generation in generations
        if generation.pack_resource_id
    }
    resources: list[ResourceStatus] = []
    for resource in resource_rows:
        gen = generations_by_resource.get(resource["id"])
        if gen is None:
            phase = "planning" if (
                pack.current_phase == "planning"
                and pack.current_resource_label == resource["label"]
            ) else "pending"
            resources.append(
                ResourceStatus(
                    resource_id=resource["id"],
                    generation_id=None,
                    label=resource["label"],
                    resource_type=resource["resource_type"],
                    status="pending",
                    phase=phase,
                )
            )
            continue
        phase = (
            "done"
            if gen.status in {"completed", "partial"}
            else "failed"
            if gen.status == "failed"
            else "generating"
        )
        resources.append(
            ResourceStatus(
                resource_id=resource["id"],
                generation_id=gen.id,
                label=gen.pack_resource_label or resource["label"],
                resource_type=resource["resource_type"],
                status=gen.status,
                phase=phase,
            )
        )
    return PackStatusResponse(
        pack_id=pack.id,
        status=pack.status,
        learning_job_type=pack.learning_job_type,
        subject=pack.subject,
        topic=pack.topic,
        resource_count=pack.resource_count,
        completed_count=pack.completed_count,
        current_phase=pack.current_phase,
        current_resource_label=pack.current_resource_label,
        resources=resources,
        created_at=pack.created_at.isoformat(),
        completed_at=pack.completed_at.isoformat() if pack.completed_at else None,
    )


