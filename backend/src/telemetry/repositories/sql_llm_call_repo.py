from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import LLMCallModel
from telemetry.dtos.usage import LLMUsageBreakdownItem, LLMUsageResponse


class SqlLLMCallRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_call(
        self,
        *,
        trace_id: str,
        generation_id: str | None,
        user_id: str | None,
        caller: str,
        slot: str,
        family: str | None,
        model_name: str | None,
        endpoint_host: str | None,
        attempt: int,
        section_id: str | None,
        status: str,
        latency_ms: float | None,
        tokens_in: int | None,
        tokens_out: int | None,
        cost_usd: float | None,
        error: str | None,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                LLMCallModel(
                    id=str(uuid4()),
                    trace_id=trace_id,
                    generation_id=generation_id,
                    user_id=user_id,
                    caller=caller,
                    node=caller,
                    slot=slot,
                    family=family,
                    model_name=model_name,
                    endpoint_host=endpoint_host,
                    attempt=attempt,
                    section_id=section_id,
                    status=status,
                    latency_ms=latency_ms,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                    error=error,
                )
            )
            await session.commit()

    async def aggregate_usage(
        self,
        *,
        user_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        caller: str | None = None,
        model_name: str | None = None,
        slot: str | None = None,
        trace_id: str | None = None,
    ) -> LLMUsageResponse:
        conditions: list[Any] = [LLMCallModel.user_id == user_id]
        if date_from:
            conditions.append(LLMCallModel.created_at >= date_from)
        if date_to:
            conditions.append(LLMCallModel.created_at <= date_to)
        if caller:
            conditions.append(LLMCallModel.caller == caller)
        if model_name:
            conditions.append(LLMCallModel.model_name == model_name)
        if slot:
            conditions.append(LLMCallModel.slot == slot)
        if trace_id:
            conditions.append(LLMCallModel.trace_id == trace_id)

        async with self._session_factory() as session:
            totals_stmt = select(
                func.count(LLMCallModel.id),
                func.coalesce(func.sum(LLMCallModel.tokens_in), 0),
                func.coalesce(func.sum(LLMCallModel.tokens_out), 0),
                func.coalesce(func.sum(LLMCallModel.cost_usd), 0.0),
            ).where(*conditions)
            totals_row = (await session.execute(totals_stmt)).one()

            async def breakdown_for(column) -> list[LLMUsageBreakdownItem]:
                stmt = (
                    select(
                        column,
                        func.count(LLMCallModel.id),
                        func.coalesce(func.sum(LLMCallModel.tokens_in), 0),
                        func.coalesce(func.sum(LLMCallModel.tokens_out), 0),
                        func.coalesce(func.sum(LLMCallModel.cost_usd), 0.0),
                    )
                    .where(*conditions)
                    .group_by(column)
                    .order_by(func.count(LLMCallModel.id).desc(), column.asc())
                )
                rows = (await session.execute(stmt)).all()
                return [
                    LLMUsageBreakdownItem(
                        key=row[0] or "unknown",
                        calls=int(row[1] or 0),
                        tokens_in=int(row[2] or 0),
                        tokens_out=int(row[3] or 0),
                        cost_usd=float(row[4] or 0.0),
                    )
                    for row in rows
                ]

            return LLMUsageResponse(
                total_calls=int(totals_row[0] or 0),
                total_tokens_in=int(totals_row[1] or 0),
                total_tokens_out=int(totals_row[2] or 0),
                total_cost_usd=float(totals_row[3] or 0.0),
                by_caller=await breakdown_for(LLMCallModel.caller),
                by_model=await breakdown_for(LLMCallModel.model_name),
                by_slot=await breakdown_for(LLMCallModel.slot),
            )
