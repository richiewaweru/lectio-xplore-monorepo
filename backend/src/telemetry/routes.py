from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.database.models import GenerationModel
from core.database.session import get_async_session
from core.entities.user import User
from telemetry.dependencies import get_llm_call_repository, get_report_repository
from telemetry.repositories.sql_generation_report_repo import SqlGenerationReportRepository
from telemetry.repositories.sql_llm_call_repo import SqlLLMCallRepository
from telemetry.service import hydrate_report_section_event_fallbacks

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


@router.get("/generations/{generation_id}/report")
async def get_generation_report(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    report_repo: SqlGenerationReportRepository = Depends(get_report_repository),
):
    result = await session.execute(
        select(GenerationModel.user_id).where(GenerationModel.id == generation_id)
    )
    row = result.first()
    if row is None or row[0] != current_user.id:
        raise HTTPException(status_code=404, detail="Generation not found")
    try:
        report = await report_repo.load_report(generation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    report = hydrate_report_section_event_fallbacks(report)
    return report.model_dump(mode="json", exclude_none=True)


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
