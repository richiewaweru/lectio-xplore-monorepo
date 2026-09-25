"""Owner-scoped HTTP status and recovery actions for generic generation runs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.entities.user import User
from infra.auth.middleware import get_current_user
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.database.session import get_async_session
from infra.generation_runtime.repository import (
    AttemptLimitExceeded,
    InvalidRunTransition,
    InvalidWorkItemTransition,
    RunNotFound,
    WorkItemNotFound,
    WorkItemUnavailable,
    active_work_items,
    cancel_run,
    get_run_status,
    retry_work_item,
)

router = APIRouter(prefix="/api/v1/generation", tags=["generation-runtime"])

_ACTIVE_ITEM_STATUSES = frozenset({"queued", "running"})
_FAILED_ITEM_STATUSES = frozenset({"failed_recoverable", "failed_terminal"})
_RETRYABLE_ERROR_CLASSES = frozenset({"validation", "provider_transport", "provider_output"})


def _safe_error(record: Any) -> dict[str, str] | None:
    if not record.error_code:
        return None
    result = {"code": record.error_code}
    if record.error_class:
        result["class"] = record.error_class
    if record.error_summary:
        result["summary"] = record.error_summary
    if record.recovery_action:
        result["recovery_action"] = record.recovery_action
    return result


def _latest_error(run: GenerationRunModel, items: list[GenerationWorkItemModel]):
    candidates = [record for record in [run, *items] if record.error_code]
    if not candidates:
        return None
    latest = max(candidates, key=lambda record: record.updated_at)
    return _safe_error(latest)


def _run_status(run: GenerationRunModel) -> dict[str, Any]:
    items = sorted(run.work_items, key=lambda item: (item.created_at, item.id))
    current_items = active_work_items(items)
    current_ids = {item.id for item in current_items}
    replaced_by = {
        item.replaces_work_item_id: item.id for item in items if item.replaces_work_item_id
    }
    active = sum(item.status in _ACTIVE_ITEM_STATUSES for item in current_items)
    ready = sum(item.status == "ready" for item in current_items)
    failed = sum(item.status in _FAILED_ITEM_STATUSES for item in current_items)
    cancelled = sum(item.status == "cancelled" for item in current_items)
    active_stages = sorted(
        {item.stage for item in current_items if item.status in _ACTIVE_ITEM_STATUSES}
    )
    run_actions = ["cancel"] if run.status in {"queued", "running", "failed_recoverable"} else []
    work_items = []
    for item in items:
        is_current = item.id in current_ids
        can_retry = (
            is_current
            and item.status == "failed_recoverable"
            and item.recovery_action == "retry"
            and item.error_class in _RETRYABLE_ERROR_CLASSES
            and item.attempt < item.max_attempts
            and run.status in {"queued", "running", "failed_recoverable"}
        )
        actions = ["retry"] if can_retry else []
        item_status: dict[str, Any] = {
            "id": item.id,
            "key": item.item_key,
            "stage": item.stage,
            "status": item.status,
            "current": is_current,
            "replaced_by": replaced_by.get(item.id),
            "attempt": item.attempt,
            "max_attempts": item.max_attempts,
            "latest_error": _safe_error(item),
            "allowed_actions": actions,
            "links": {},
        }
        if can_retry:
            item_status["links"]["retry"] = f"/api/v1/generation/work-items/{item.id}/retry"
        work_items.append(item_status)

    output = None
    if run.output_artifact_id is not None:
        output = {
            "type": run.output_artifact_type,
            "id": run.output_artifact_id,
            "revision": run.output_revision,
            "hash": run.output_hash,
        }
    return {
        "id": run.id,
        "build_id": run.build_id,
        "run_type": run.run_type,
        "status": run.status,
        "stage": active_stages[0] if len(active_stages) == 1 else run.stage,
        "active_stages": active_stages,
        "run_stage": run.stage,
        "progress": {
            "active": active,
            "completed": ready,
            "failed": failed,
            "cancelled": cancelled,
            "total": len(current_items),
        },
        "source": {
            "type": run.source_artifact_type,
            "id": run.source_artifact_id,
            "revision": run.source_revision,
            "hash": run.source_hash,
        },
        "output": output,
        "latest_error": _latest_error(run, list(current_items)),
        "work_items": work_items,
        "allowed_actions": run_actions,
        "links": {
            "status": f"/api/v1/generation/runs/{run.id}",
            "build": f"/api/v1/generation/builds/{run.build_id}",
            **(
                {"cancel": f"/api/v1/generation/runs/{run.id}/cancel"}
                if "cancel" in run_actions
                else {}
            ),
        },
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Generation resource not found")


def _build_status(runs: list[GenerationRunModel]) -> dict[str, Any]:
    """Project one universal Run status; mixed terminal outcomes have no single status."""
    run_statuses = {run.status for run in runs}
    if not runs:
        status = None
    elif "running" in run_statuses:
        status = "running"
    elif "queued" in run_statuses:
        status = "queued"
    elif "awaiting_review" in run_statuses:
        status = "awaiting_review"
    else:
        status = next(iter(run_statuses)) if len(run_statuses) == 1 else None
    items = [item for run in runs for item in active_work_items(run.work_items)]
    active = sum(item.status in _ACTIVE_ITEM_STATUSES for item in items)
    ready = sum(item.status == "ready" for item in items)
    failed = sum(item.status in _FAILED_ITEM_STATUSES for item in items)
    cancelled = sum(item.status == "cancelled" for item in items)
    return {
        "status": status,
        "runs": len(runs),
        "ready_runs": sum(run.status == "ready" for run in runs),
        "active_runs": sum(run.status in {"queued", "running"} for run in runs),
        "failed_runs": sum(run.status in {"failed_recoverable", "failed_terminal"} for run in runs),
        "cancelled_runs": sum(run.status == "cancelled" for run in runs),
        "progress": {
            "active": active,
            "completed": ready,
            "failed": failed,
            "cancelled": cancelled,
            "total": len(items),
        },
    }


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/builds/{build_id}")
async def get_build_status_route(
    build_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    build = await session.scalar(
        select(GenerationBuildModel).where(
            GenerationBuildModel.id == build_id,
            GenerationBuildModel.owner_user_id == current_user.id,
        )
    )
    if build is None:
        raise _not_found()
    runs = list(
        (
            await session.scalars(
                select(GenerationRunModel)
                .options(selectinload(GenerationRunModel.work_items))
                .where(
                    GenerationRunModel.build_id == build.id,
                    GenerationRunModel.owner_user_id == current_user.id,
                )
            )
        ).all()
    )
    runs.sort(key=lambda run: (run.created_at, run.id))
    return {
        "id": build.id,
        "created_at": build.created_at,
        "aggregate": _build_status(runs),
        "runs": [_run_status(run) for run in runs],
    }


@router.get("/runs/{run_id}")
async def get_run_status_route(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    run = await get_run_status(session, run_id=run_id, owner_user_id=current_user.id)
    if run is None:
        raise _not_found()
    return _run_status(run)


@router.post("/work-items/{work_item_id}/retry")
async def retry_work_item_route(
    work_item_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    try:
        async with session.begin():
            item = await retry_work_item(
                session,
                work_item_id=work_item_id,
                owner_user_id=current_user.id,
            )
            run_id = item.run_id
    except (RunNotFound, WorkItemNotFound):
        raise _not_found() from None
    except (
        InvalidRunTransition,
        InvalidWorkItemTransition,
        AttemptLimitExceeded,
        WorkItemUnavailable,
    ) as exc:
        raise _conflict(exc) from None

    run = await get_run_status(session, run_id=run_id, owner_user_id=current_user.id)
    if run is None:
        raise _not_found()
    return _run_status(run)


@router.post("/runs/{run_id}/cancel")
async def cancel_run_route(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    try:
        async with session.begin():
            await cancel_run(session, run_id=run_id, owner_user_id=current_user.id)
    except RunNotFound:
        raise _not_found() from None
    except InvalidRunTransition as exc:
        raise _conflict(exc) from None

    run = await get_run_status(session, run_id=run_id, owner_user_id=current_user.id)
    if run is None:
        raise _not_found()
    return _run_status(run)
