from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import V3TraceEventModel, V3TraceRunModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class V3TraceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_run(
        self,
        *,
        trace_id: str,
        user_id: str,
        title: str | None = None,
        subject: str | None = None,
        template_id: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            run = V3TraceRunModel(
                trace_id=trace_id,
                user_id=user_id,
                title=title,
                subject=subject,
                template_id=template_id,
                status="pending",
            )
            session.add(run)
            await session.commit()

    async def start_run(
        self,
        *,
        trace_id: str,
        generation_id: str,
        user_id: str,
        title: str | None = None,
        subject: str | None = None,
        template_id: str | None = None,
        start_event_type: str,
        start_event_payload: dict,
        phase: str = "start",
    ) -> None:
        async with self._session_factory() as session:
            run = V3TraceRunModel(
                trace_id=trace_id,
                generation_id=generation_id,
                user_id=user_id,
                title=title,
                subject=subject,
                template_id=template_id,
                status="generating",
            )
            session.add(run)
            event = V3TraceEventModel(
                id=str(uuid.uuid4()),
                trace_id=trace_id,
                sequence=1,
                phase=phase,
                event_type=start_event_type,
                payload=start_event_payload,
            )
            session.add(event)
            await session.commit()

    async def bind_generation(
        self,
        *,
        trace_id: str,
        generation_id: str,
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(V3TraceRunModel).where(V3TraceRunModel.trace_id == trace_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return
            run.generation_id = generation_id
            run.status = "generating"
            run.updated_at = _utcnow()
            await session.commit()

    async def append_event(
        self,
        *,
        trace_id: str,
        phase: str,
        event_type: str,
        payload: dict,
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(V3TraceEventModel.sequence)
                .where(V3TraceEventModel.trace_id == trace_id)
                .order_by(V3TraceEventModel.sequence.desc())
                .limit(1)
            )
            last_seq = result.scalar_one_or_none()
            next_seq = (last_seq or 0) + 1

            event = V3TraceEventModel(
                id=str(uuid.uuid4()),
                trace_id=trace_id,
                sequence=next_seq,
                phase=phase,
                event_type=event_type,
                payload=payload,
            )
            session.add(event)
            await session.commit()

    async def update_report(
        self,
        *,
        trace_id: str,
        report: dict,
        status: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(V3TraceRunModel).where(V3TraceRunModel.trace_id == trace_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return
            run.report_json = report
            if status is not None:
                run.status = status
            run.updated_at = _utcnow()
            await session.commit()

    async def get_run(self, trace_id: str) -> V3TraceRunModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(V3TraceRunModel).where(V3TraceRunModel.trace_id == trace_id)
            )
            return result.scalar_one_or_none()

    async def get_events(self, trace_id: str) -> list[V3TraceEventModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(V3TraceEventModel)
                .where(V3TraceEventModel.trace_id == trace_id)
                .order_by(V3TraceEventModel.sequence)
            )
            return list(result.scalars().all())

    async def get_run_by_generation(self, generation_id: str) -> V3TraceRunModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(V3TraceRunModel).where(
                    V3TraceRunModel.generation_id == generation_id
                )
            )
            return result.scalar_one_or_none()

    async def get_full_trace(self, trace_id: str) -> dict | None:
        run = await self.get_run(trace_id)
        if run is None:
            return None

        events = await self.get_events(trace_id)
        return {
            "trace_id": run.trace_id,
            "generation_id": run.generation_id,
            "user_id": run.user_id,
            "title": run.title,
            "subject": run.subject,
            "template_id": run.template_id,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "report": run.report_json,
            "events": [
                {
                    "sequence": event.sequence,
                    "phase": event.phase,
                    "event_type": event.event_type,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
                for event in events
            ],
        }
