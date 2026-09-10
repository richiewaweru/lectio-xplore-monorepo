from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from infra.auth.middleware import get_current_user
from core.database.models import LearningPackModel
from infra.database.session import async_session_factory
from core.entities.user import User
from learn.generation.canonical import canonical_document
from learn.models import (
    CanonicalPackDocumentResponse,
    CanonicalPackResourceDocument,
    PackStatusResponse,
    ResourceStatus,
)
from learn.pack_repository import LearningPackRepository

router = APIRouter(prefix="/api/v1/packs", tags=["learning-packs"])


def get_pack_repository() -> LearningPackRepository:
    return LearningPackRepository(async_session_factory)


@router.get("", response_model=list[PackStatusResponse])
async def list_packs(
    current_user: User = Depends(get_current_user),
    pack_repo: LearningPackRepository = Depends(get_pack_repository),
    limit: int = 20,
) -> list[PackStatusResponse]:
    packs = await pack_repo.list_canonical_by_user(current_user.id, limit=limit)
    return [
        _pack_to_status(pack, await pack_repo.canonical_generations_for_pack(pack.id))
        for pack in packs
    ]


@router.get("/{pack_id}", response_model=PackStatusResponse)
async def get_pack_status(
    pack_id: str,
    current_user: User = Depends(get_current_user),
    pack_repo: LearningPackRepository = Depends(get_pack_repository),
) -> PackStatusResponse:
    pack = await pack_repo.find_by_id(pack_id)
    if pack is None or pack.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pack not found.")
    generations = await pack_repo.canonical_generations_for_pack(pack_id)
    if not generations:
        # A pack containing only retired or unmarked generations is not part of
        # the canonical product surface.
        raise HTTPException(status_code=404, detail="Pack not found.")
    return _pack_to_status(pack, generations)


@router.get("/{pack_id}/document", response_model=CanonicalPackDocumentResponse)
async def get_pack_document(
    pack_id: str,
    current_user: User = Depends(get_current_user),
    pack_repo: LearningPackRepository = Depends(get_pack_repository),
) -> CanonicalPackDocumentResponse:
    """Return active-pack resources as canonical LessonDocuments only."""
    pack = await pack_repo.find_by_id(pack_id)
    if pack is None or pack.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pack not found.")
    generations = await pack_repo.canonical_generations_for_pack(pack_id)
    if not generations:
        raise HTTPException(status_code=404, detail="Pack not found.")

    plan_data = json.loads(pack.pack_plan_json)
    labels = {
        str(resource.get("id")): str(resource.get("label") or resource.get("id"))
        for resource in plan_data.get("resources", [])
        if isinstance(resource, dict) and resource.get("id")
    }
    generations_by_resource = {
        generator.pack_resource_id: generator
        for generator in generations
        if generator.pack_resource_id
    }
    planned_resource_ids = {
        str(raw_resource["id"])
        for raw_resource in plan_data.get("resources", [])
        if isinstance(raw_resource, dict) and raw_resource.get("id")
    }
    resources: list[CanonicalPackResourceDocument] = []
    for raw_resource in plan_data.get("resources", []):
        if not isinstance(raw_resource, dict) or not raw_resource.get("id"):
            continue
        resource_id = str(raw_resource["id"])
        generator = generations_by_resource.get(resource_id)
        resources.append(
            CanonicalPackResourceDocument(
                resource_id=resource_id,
                generation_id=generator.id if generator else None,
                label=str(raw_resource.get("label") or resource_id),
                status=str(generator.status or "pending") if generator else "pending",
                document=canonical_document(generator) if generator else None,
            )
        )

    # Preserve a canonical generation even if an older pack plan omitted its
    # resource id; it remains visible under its generation id rather than being
    # silently dropped from the document projection.
    resources.extend(
        CanonicalPackResourceDocument(
            resource_id=generator.id,
            generation_id=generator.id,
            label=generator.pack_resource_label or labels.get(generator.id, generator.id),
            status=str(generator.status or "pending"),
            document=canonical_document(generator),
        )
        for generator in generations
        if not generator.pack_resource_id
        or str(generator.pack_resource_id) not in planned_resource_ids
    )
    return CanonicalPackDocumentResponse(
        pack_id=pack.id,
        subject=pack.subject,
        topic=pack.topic,
        resources=resources,
    )


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
            else "awaiting_review"
            if gen.status == "awaiting_review"
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


