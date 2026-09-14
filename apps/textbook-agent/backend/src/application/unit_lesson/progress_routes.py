"""Durable realization progress status + replayable events (P04 G16–G18)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import get_realization
from core.capabilities import require_xplore_v2
from core.database.models import PathLessonModel, PathVersionModel, UnitModel
from core.entities.user import User
from infra.auth.middleware import get_current_user
from infra.dependencies import get_async_session
from infra.execution.progress import ProgressStore, default_progress_store

router = APIRouter(
    prefix="/api/v1/realizations",
    tags=["realization-progress"],
    dependencies=[Depends(require_xplore_v2)],
)

HEARTBEAT_SECONDS = 15.0


def get_progress_store() -> ProgressStore:
    return default_progress_store


async def _authorize_realization(
    session: AsyncSession,
    *,
    realization_id: str,
    user_id: str,
    store: ProgressStore,
) -> Any:
    realization = await get_realization(session, realization_id)
    if realization is None:
        raise HTTPException(status_code=404, detail="Realization not found")

    lesson = await session.get(PathLessonModel, realization.path_lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Realization not found")
    version = await session.get(PathVersionModel, lesson.path_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Realization not found")
    unit = await session.scalar(
        select(UnitModel).where(UnitModel.id == version.unit_id, UnitModel.owner_id == user_id)
    )
    if unit is None:
        # Same shape as other units routes: do not leak existence to non-owners.
        raise HTTPException(status_code=404, detail="Realization not found")

    store.sync_from_db(
        realization.id,
        path=str(realization.path),
        owner_user_id=user_id,
        status=str(realization.status),
        realization_revision=int(realization.realization_revision),
        teaching_plan_revision=int(realization.teaching_plan_revision),
    )
    return realization


def _sse_chunk(*, event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    return "\n".join(lines) + "\n\n"


@router.get("/{realization_id}/status")
async def get_realization_progress_status(
    realization_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    store: ProgressStore = Depends(get_progress_store),
) -> dict[str, Any]:
    realization = await _authorize_realization(
        session,
        realization_id=realization_id,
        user_id=current_user.id,
        store=store,
    )
    view = store.get_status(realization.id)
    # Authoritative DB fields win for status/revisions agreement (G16).
    payload = view.to_dict()
    payload["status"] = str(realization.status)
    payload["path"] = str(realization.path)
    payload["revisions"] = {
        **payload["revisions"],
        "realization_revision": int(realization.realization_revision),
        "teaching_plan_revision": int(realization.teaching_plan_revision),
    }
    payload["db_status"] = str(realization.status)
    return payload


@router.get("/{realization_id}/events")
async def get_realization_progress_events(
    realization_id: str,
    after_seq: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    store: ProgressStore = Depends(get_progress_store),
) -> dict[str, Any]:
    realization = await _authorize_realization(
        session,
        realization_id=realization_id,
        user_id=current_user.id,
        store=store,
    )
    return store.replay(realization.id, after_seq=after_seq).to_dict()


@router.get("/{realization_id}/events/stream")
async def stream_realization_progress_events(
    realization_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    store: ProgressStore = Depends(get_progress_store),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after_seq: int = Query(default=0, ge=0),
) -> StreamingResponse:
    realization = await _authorize_realization(
        session,
        realization_id=realization_id,
        user_id=current_user.id,
        store=store,
    )
    cursor = after_seq
    if last_event_id and last_event_id.strip().isdigit():
        cursor = max(cursor, int(last_event_id.strip()))

    async def event_generator():
        nonlocal cursor
        # Initial reconnect recovery / replay.
        replay = store.replay(realization.id, after_seq=cursor)
        if replay.mode == "snapshot" and replay.snapshot is not None:
            yield _sse_chunk(event="snapshot", data=replay.snapshot, event_id=replay.latest_seq)
        for event in replay.events:
            yield _sse_chunk(
                event=event.event_type,
                data=event.to_dict(),
                event_id=event.seq,
            )
            cursor = max(cursor, event.seq)

        # Live tail: poll store for new sequences (durable, reconnect-safe).
        idle = 0.0
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.25)
            idle += 0.25
            replay = store.replay(realization.id, after_seq=cursor)
            for event in replay.events:
                yield _sse_chunk(
                    event=event.event_type,
                    data=event.to_dict(),
                    event_id=event.seq,
                )
                cursor = max(cursor, event.seq)
                idle = 0.0
            if idle >= HEARTBEAT_SECONDS:
                yield ": ping\n\n"
                idle = 0.0

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{realization_id}/traces")
async def get_realization_model_traces(
    realization_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    store: ProgressStore = Depends(get_progress_store),
) -> dict[str, Any]:
    realization = await _authorize_realization(
        session,
        realization_id=realization_id,
        user_id=current_user.id,
        store=store,
    )
    traces = [trace.to_dict() for trace in store.list_traces(realization.id)]
    return {"run_id": realization.id, "traces": traces}
