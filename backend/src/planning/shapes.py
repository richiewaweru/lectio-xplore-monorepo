from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import PathLessonDeviationModel, PathLessonModel
from planning.models import ShapeDeviationCreateRequest
from v3_blueprint.skeletons import (
    DeviationRequest,
    SkeletonPreviewRequest,
    load_skeleton_catalog,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _payload(model: PathLessonDeviationModel) -> dict[str, Any]:
    return {
        "id": model.id,
        "skeleton_id": model.skeleton_id,
        "skeleton_version": model.skeleton_version,
        "lesson_mode": model.lesson_mode,
        "operation": model.operation,
        "target_slot": model.target_slot,
        "replacement_slot": model.replacement_slot,
        "reason": model.reason,
        "requested_by": model.requested_by,
        "status": model.status,
        "requested_at": model.requested_at.isoformat(),
        "decided_at": model.decided_at.isoformat() if model.decided_at else None,
        "decided_by": model.decided_by,
    }


def _contract(model: PathLessonDeviationModel) -> DeviationRequest:
    return DeviationRequest(
        id=model.id,
        skeleton_id=model.skeleton_id,
        operation=model.operation,
        target_slot=model.target_slot,
        replacement_slot=model.replacement_slot,
        reason=model.reason,
        requested_by=model.requested_by,
        status=model.status,
    )


async def lesson_deviations(
    session: AsyncSession,
    *,
    lesson_id: str,
) -> list[PathLessonDeviationModel]:
    return list(
        await session.scalars(
            select(PathLessonDeviationModel)
            .where(PathLessonDeviationModel.path_lesson_id == lesson_id)
            .order_by(PathLessonDeviationModel.requested_at, PathLessonDeviationModel.id)
        )
    )


async def lesson_shape_payload(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    lesson_mode: str,
    misconception_count: int,
) -> dict[str, Any]:
    catalog = load_skeleton_catalog()
    skeleton = catalog.skeleton_for(lesson.primary_knowledge_type, lesson_mode)
    skeleton_id = str(skeleton["id"])
    deviations = [
        item
        for item in await lesson_deviations(session, lesson_id=lesson.id)
        if item.lesson_mode == lesson_mode and item.skeleton_id == skeleton_id
    ]
    approved = [_contract(item) for item in deviations if item.status == "approved"]
    canonical = catalog.preview(
        SkeletonPreviewRequest(
            objective=lesson.objective,
            lesson_mode=lesson_mode,
            misconception_count=misconception_count,
            group_profiles=["core"],
            approved_deviations=approved,
        ),
        knowledge_type=lesson.primary_knowledge_type,
    )
    expanded = catalog.preview(
        SkeletonPreviewRequest(
            objective=lesson.objective,
            lesson_mode=lesson_mode,
            misconception_count=misconception_count,
            group_profiles=["support", "core", "extension"],
            approved_deviations=approved,
        ),
        knowledge_type=lesson.primary_knowledge_type,
    )
    blocking = [
        {"group_profile": variant.group_profile, **issue.model_dump(mode="json")}
        for variant in expanded.variants
        for issue in variant.blocking_issues
    ]
    pending = [item for item in deviations if item.status == "pending_teacher"]
    return {
        "path_lesson_id": lesson.id,
        "lesson_revision": lesson.revision,
        "objective": lesson.objective,
        "objective_hash": lesson.objective_hash,
        "concept_id": lesson.concept_id,
        "scope_exclusions": list(lesson.exclusions or []),
        "lesson_mode": lesson_mode,
        "misconception_count": misconception_count,
        "skeleton_id": expanded.skeleton_id,
        "skeleton_version": expanded.skeleton_version,
        "canonical": canonical.variants[0].model_dump(mode="json"),
        "variants": [variant.model_dump(mode="json") for variant in expanded.variants],
        "deviations": [_payload(item) for item in deviations],
        "available_slots": sorted(catalog.slots),
        "blocking_issues": blocking,
        "can_prepare": not blocking and not pending,
    }


async def request_shape_deviation(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    request: ShapeDeviationCreateRequest,
) -> PathLessonDeviationModel:
    catalog = load_skeleton_catalog()
    skeleton = catalog.skeleton_for(lesson.primary_knowledge_type, request.lesson_mode)
    skeleton_id = str(skeleton["id"])
    contract = DeviationRequest(
        skeleton_id=skeleton_id,
        operation=request.operation,
        target_slot=request.target_slot,
        replacement_slot=request.replacement_slot,
        reason=request.reason.strip(),
        requested_by="teacher",
    )
    if contract.target_slot not in skeleton["slots"]:
        raise ValueError("A deviation target must be present in the canonical skeleton")
    if contract.replacement_slot is not None and contract.replacement_slot not in catalog.slots:
        raise ValueError("A deviation replacement must be a declared skeleton slot")
    existing = await lesson_deviations(session, lesson_id=lesson.id)
    if any(
        item.lesson_mode == request.lesson_mode
        and item.skeleton_id == skeleton_id
        and item.operation == contract.operation
        and item.target_slot == contract.target_slot
        and item.replacement_slot == contract.replacement_slot
        and item.status in {"pending_teacher", "approved"}
        for item in existing
    ):
        raise ValueError("This shape deviation is already pending or approved")
    model = PathLessonDeviationModel(
        path_lesson_id=lesson.id,
        skeleton_id=skeleton_id,
        skeleton_version=catalog.version,
        lesson_mode=request.lesson_mode,
        operation=contract.operation,
        target_slot=contract.target_slot,
        replacement_slot=contract.replacement_slot,
        reason=contract.reason,
        requested_by="teacher",
        status="pending_teacher",
    )
    session.add(model)
    await session.flush()
    return model


async def decide_shape_deviation(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    deviation_id: str,
    approved: bool,
    decided_by: str,
) -> PathLessonDeviationModel:
    model = await session.get(PathLessonDeviationModel, deviation_id)
    if model is None or model.path_lesson_id != lesson.id:
        raise ValueError("Shape deviation not found for this path lesson")
    if model.status != "pending_teacher":
        raise ValueError("Only a pending shape deviation can be decided")
    if approved:
        contract = _contract(model).model_copy(update={"status": "approved"})
        preview = load_skeleton_catalog().preview(
            SkeletonPreviewRequest(
                objective=lesson.objective,
                lesson_mode=model.lesson_mode,
                misconception_count=0,
                group_profiles=["core"],
                approved_deviations=[contract],
            ),
            knowledge_type=lesson.primary_knowledge_type,
        )
        own_issues = [
            issue
            for issue in preview.variants[0].blocking_issues
            if issue.toggle_id == f"deviation:{model.id}"
        ]
        if own_issues:
            raise ValueError(own_issues[0].message)
        model.status = "approved"
        lesson.revision += 1
    else:
        model.status = "rejected"
    model.decided_at = _utcnow()
    model.decided_by = decided_by
    await session.flush()
    return model


def deviation_payload(model: PathLessonDeviationModel) -> dict[str, Any]:
    return _payload(model)


def approved_deviation_contracts(
    deviations: list[PathLessonDeviationModel],
    *,
    lesson_mode: str,
    skeleton_id: str,
) -> list[DeviationRequest]:
    return [
        _contract(item)
        for item in deviations
        if item.lesson_mode == lesson_mode
        and item.skeleton_id == skeleton_id
        and item.status == "approved"
    ]
