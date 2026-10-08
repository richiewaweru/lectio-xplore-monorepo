"""A dispatch exception for a queued Print realization is recorded on the row.

Before this, ``RealizationWorker._dispatch`` only logged the exception and left
the row ``queued`` with no reason, so a Print output could wait forever with
nothing visible explaining why.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _approved_native_preparation

from application.unit_lesson import realization_worker as worker_module
from application.unit_lesson.realization_worker import RealizationWorker
from application.unit_lesson.realize_print_handoff import realize_print_from_preparation
from core.database.models import NativeRealizationModel


@pytest.mark.asyncio
async def test_dispatch_exception_is_recorded_on_queued_print_row(
    db_session: AsyncSession, db_session_factory, monkeypatch
) -> None:
    user_id = "dispatch-visible-failure"
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id=user_id
    )
    admitted = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id=user_id,
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    realization_id = admitted["realization_id"]

    async def _raise(*_args, **_kwargs):
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(worker_module, "load_realization_source", _raise)
    worker = RealizationWorker(db_session_factory, worker_id="dispatch-visible-failure")
    async with db_session_factory() as session:
        await worker.run_one(session)

    async with db_session_factory() as session:
        row = await session.get(NativeRealizationModel, realization_id)
        assert row is not None
        assert row.status == "queued"  # still retried automatically
        assert row.generation_run_id is None
        assert row.error_summary is not None
        assert row.error_summary.startswith("REALIZATION_DISPATCH_FAILED: RuntimeError")
        # The raw exception message is never persisted, only its type.
        assert "simulated" not in row.error_summary
