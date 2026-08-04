from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.auth.middleware import get_current_user
from core.entities.user import User
from telemetry.dependencies import get_llm_call_repository
from telemetry.repositories.sql_llm_call_repo import SqlLLMCallRepository

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


@router.get("/telemetry/llm-usage")
async def get_llm_usage(
    current_user: User = Depends(get_current_user),
    llm_repo: SqlLLMCallRepository = Depends(get_llm_call_repository),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    caller: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    slot: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
):
    usage = await llm_repo.aggregate_usage(
        user_id=current_user.id,
        date_from=date_from,
        date_to=date_to,
        caller=caller,
        model_name=model_name,
        slot=slot,
        trace_id=trace_id,
    )
    return usage.model_dump(mode="json", exclude_none=True)
