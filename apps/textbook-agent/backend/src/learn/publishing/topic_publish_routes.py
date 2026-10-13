"""Publish a unit's topic path to a class (doc 38 section 3.4).

Teacher-only. For each chosen path lesson of the unit's active path this
publishes the generated Learn lesson through the existing release code
(explicit ``path_lesson_id``) and then creates a rolling assignment for the
class, so current members get instances now and future members on join.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import resolve_by_path
from core.database.models import (
    EditableLessonModel,
    LearnReleaseModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from core.entities.user import User
from infra.auth.middleware import get_current_user
from infra.database.session import get_async_session
from learn.class_service import create_assignment, require_class_owner
from learn.publishing.release_routes import (
    PublishLearnReleaseRequest,
    document_hash,
    publish_learn_release,
)
from learn.runtime_models import (
    LearnAssignmentModel,
    LearnAssignmentTargetModel,
)

router = APIRouter(prefix="/api/v1/units", tags=["learn-topic-publish"])

PublishItemStatus = Literal[
    "not_generated", "published", "already_published", "failed"
]


class PublishCandidate(BaseModel):
    path_lesson_id: str
    position: int
    title: str
    generated: bool
    editable_lesson_id: str | None = None
    # Latest published release carrying this path_lesson_id (any class).
    release_id: str | None = None
    release_number: int | None = None
    # True when the generated lesson differs from that release (publishing
    # would create a new release).
    has_unpublished_changes: bool = False
    # Only set when class_id was supplied.
    assigned_to_class: bool | None = None
    # not_generated | ready_to_publish | published (to the class when class_id
    # given, otherwise a release exists)
    status: Literal["not_generated", "ready_to_publish", "published"]


class PublishCandidatesResponse(BaseModel):
    unit_id: str
    unit_title: str
    class_id: str | None = None
    lessons: list[PublishCandidate]


class PublishToClassRequest(BaseModel):
    class_id: str
    path_lesson_ids: list[str] = Field(min_length=1, max_length=100)


class PublishItemResult(BaseModel):
    path_lesson_id: str
    position: int
    title: str
    status: PublishItemStatus
    release_id: str | None = None
    release_number: int | None = None
    release_created: bool = False
    assignment_id: str | None = None
    assignment_created: bool = False
    message: str | None = None


class PublishToClassResponse(BaseModel):
    unit_id: str
    class_id: str
    results: list[PublishItemResult]


async def _owned_unit_active_lessons(
    session: AsyncSession, *, unit_id: str, user_id: str
) -> tuple[UnitModel, list[PathLessonModel]]:
    unit = await session.get(UnitModel, unit_id)
    if unit is None or unit.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Unit not found")
    if not unit.active_path_version_id:
        return unit, []
    version = await session.get(PathVersionModel, unit.active_path_version_id)
    if version is None or version.unit_id != unit.id:
        return unit, []
    rows = await session.scalars(
        select(PathLessonModel)
        .where(
            PathLessonModel.path_version_id == version.id,
            PathLessonModel.skipped.is_(False),
        )
        .order_by(PathLessonModel.position.asc())
    )
    return unit, list(rows.all())


async def _generated_editable_lesson(
    session: AsyncSession, *, path_lesson_id: str, user_id: str
) -> EditableLessonModel | None:
    """Path lesson -> ready Learn realization -> its editable lesson (doc 38 s7)."""
    realization = await resolve_by_path(session, path_lesson_id=path_lesson_id, path="learn")
    if realization is None or realization.status != "ready" or not realization.output_id:
        return None
    return await session.scalar(
        select(EditableLessonModel)
        .where(
            EditableLessonModel.source_generation_id == realization.output_id,
            EditableLessonModel.user_id == user_id,
        )
        .order_by(EditableLessonModel.created_at.desc())
        .limit(1)
    )


async def _latest_linked_release(
    session: AsyncSession, *, path_lesson_id: str, user_id: str
) -> LearnReleaseModel | None:
    return await session.scalar(
        select(LearnReleaseModel)
        .where(
            LearnReleaseModel.path_lesson_id == path_lesson_id,
            LearnReleaseModel.owner_user_id == user_id,
            LearnReleaseModel.status == "published",
        )
        .order_by(LearnReleaseModel.published_at.desc(), LearnReleaseModel.release_number.desc())
        .limit(1)
    )


async def _active_rolling_assignment(
    session: AsyncSession, *, release_id: str, class_id: str
) -> LearnAssignmentModel | None:
    rows = await session.scalars(
        select(LearnAssignmentModel).where(
            LearnAssignmentModel.learn_release_id == release_id,
            LearnAssignmentModel.mode == "rolling",
            LearnAssignmentModel.active.is_(True),
        )
    )
    for assignment in rows.all():
        if assignment.class_id == class_id:
            return assignment
        target = await session.scalar(
            select(LearnAssignmentTargetModel.id).where(
                LearnAssignmentTargetModel.assignment_id == assignment.id,
                LearnAssignmentTargetModel.class_id == class_id,
            )
        )
        if target is not None:
            return assignment
    return None


def _has_changes(editable: EditableLessonModel, release: LearnReleaseModel | None) -> bool:
    if release is None:
        return False
    doc = editable.document_json if isinstance(editable.document_json, dict) else {}
    try:
        return document_hash(doc) != release.document_hash
    except (TypeError, ValueError):
        return True


@router.get("/{unit_id}/publish-candidates", response_model=PublishCandidatesResponse)
async def list_publish_candidates(
    unit_id: str,
    class_id: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PublishCandidatesResponse:
    unit, lessons = await _owned_unit_active_lessons(
        session, unit_id=unit_id, user_id=current_user.id
    )
    if class_id:
        await require_class_owner(session, class_id=class_id, teacher_id=current_user.id)

    out: list[PublishCandidate] = []
    for pl in lessons:
        editable = await _generated_editable_lesson(
            session, path_lesson_id=pl.id, user_id=current_user.id
        )
        release = await _latest_linked_release(
            session, path_lesson_id=pl.id, user_id=current_user.id
        )
        assigned: bool | None = None
        if class_id:
            assigned = False
            if release is not None:
                assigned = (
                    await _active_rolling_assignment(
                        session, release_id=release.id, class_id=class_id
                    )
                    is not None
                )
        if editable is None:
            item_status: Literal["not_generated", "ready_to_publish", "published"] = (
                "not_generated"
            )
        elif (assigned if class_id else release is not None) and not _has_changes(
            editable, release
        ):
            item_status = "published"
        else:
            item_status = "ready_to_publish"
        out.append(
            PublishCandidate(
                path_lesson_id=pl.id,
                position=pl.position,
                title=pl.title,
                generated=editable is not None,
                editable_lesson_id=editable.id if editable else None,
                release_id=release.id if release else None,
                release_number=release.release_number if release else None,
                has_unpublished_changes=(
                    _has_changes(editable, release) if editable is not None else False
                ),
                assigned_to_class=assigned,
                status=item_status,
            )
        )
    return PublishCandidatesResponse(
        unit_id=unit.id, unit_title=unit.title, class_id=class_id, lessons=out
    )


@router.post("/{unit_id}/publish-to-class", response_model=PublishToClassResponse)
async def publish_unit_to_class(
    unit_id: str,
    body: PublishToClassRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PublishToClassResponse:
    _unit, lessons = await _owned_unit_active_lessons(
        session, unit_id=unit_id, user_id=current_user.id
    )
    await require_class_owner(session, class_id=body.class_id, teacher_id=current_user.id)

    by_id = {pl.id: pl for pl in lessons}
    unknown = [pid for pid in body.path_lesson_ids if pid not in by_id]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PATH_LESSON_NOT_IN_UNIT",
                "message": "Some path lessons are not part of this unit's active path.",
                "path_lesson_ids": unknown,
            },
        )

    results: list[PublishItemResult] = []
    seen: set[str] = set()
    for pid in body.path_lesson_ids:
        if pid in seen:
            continue
        seen.add(pid)
        pl = by_id[pid]
        base: dict[str, Any] = {
            "path_lesson_id": pl.id,
            "position": pl.position,
            "title": pl.title,
        }
        editable = await _generated_editable_lesson(
            session, path_lesson_id=pl.id, user_id=current_user.id
        )
        if editable is None:
            results.append(
                PublishItemResult(
                    **base,
                    status="not_generated",
                    message="No generated lesson yet; students will see 'Being prepared'.",
                )
            )
            continue

        try:
            # Reuse the existing publish handler so validation, provenance
            # (resolve_release_provenance) and idempotent replay are identical.
            release = await publish_learn_release(
                editable.id,
                PublishLearnReleaseRequest(path_lesson_id=pl.id),
                current_user,
                session,
                None,
            )
        except HTTPException as exc:
            await session.rollback()
            results.append(
                PublishItemResult(**base, status="failed", message=_detail_message(exc.detail))
            )
            continue

        if release.path_lesson_id != pl.id:
            # Identical content was already published without (or with another)
            # topic link; an immutable release cannot be relinked.
            results.append(
                PublishItemResult(
                    **base,
                    status="failed",
                    release_id=release.id,
                    release_number=release.release_number,
                    message=(
                        "An identical release exists that is not linked to this topic "
                        "lesson; edit the lesson and publish again."
                    ),
                )
            )
            continue

        assignment = await _active_rolling_assignment(
            session, release_id=release.id, class_id=body.class_id
        )
        assignment_created = False
        if assignment is None:
            assignment = await create_assignment(
                session,
                teacher_id=current_user.id,
                learn_release_id=release.id,
                title=release.title,
                class_id=body.class_id,
                mode="rolling",
            )
            await session.commit()
            assignment_created = True

        release_created = not release.idempotent_replay
        results.append(
            PublishItemResult(
                **base,
                status="published" if (release_created or assignment_created) else "already_published",
                release_id=release.id,
                release_number=release.release_number,
                release_created=release_created,
                assignment_id=assignment.id,
                assignment_created=assignment_created,
            )
        )
    return PublishToClassResponse(unit_id=unit_id, class_id=body.class_id, results=results)


def _detail_message(detail: Any) -> str:
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or detail)
    return str(detail)
