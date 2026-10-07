"""Regenerate on a realization whose shared document failed admits a fresh Run.

The realization retry handlers used to bump the revision but leave the
realization pinned to the terminally failed SharedLessonDocument Run, so it was
immediately re-projected as failed.  They now pin the new revision to a freshly
admitted (bounded, deterministic) shared document Run, shared by Learn + Print.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _approved_native_preparation

from application.unit_lesson.realization_projection import project_realization_status
from application.unit_lesson.realize_learn_handoff import (
    realize_learn_from_preparation,
    retry_learn_realization,
)
from application.unit_lesson.realize_print_handoff import (
    realize_print_from_preparation,
    retry_print_realization,
)
from core.database.models import NativeRealizationModel
from document.shared_lesson.realization_source import load_realization_source
from infra.database.models import GenerationRunModel


async def _admit_both(db_session: AsyncSession, *, user_id: str):
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id=user_id
    )
    kwargs = dict(
        preparation_generation_id=str(lesson.pack_id),
        user_id=user_id,
        path_lesson_id=lesson.id,
    )
    learn = await realize_learn_from_preparation(db_session, **kwargs)
    print_ = await realize_print_from_preparation(db_session, **kwargs)
    await db_session.commit()
    return lesson, learn["realization_id"], print_["realization_id"]


async def _shared_runs(factory) -> list[GenerationRunModel]:
    async with factory() as session:
        return list(
            (
                await session.scalars(
                    select(GenerationRunModel)
                    .where(GenerationRunModel.run_type == "shared_document")
                    .order_by(GenerationRunModel.created_at, GenerationRunModel.id)
                )
            ).all()
        )


async def _fail_shared_run(factory, run_id: str, *, status: str, realization_ids) -> None:
    async with factory() as session:
        run = await session.get(GenerationRunModel, run_id)
        run.status = status
        for rid in realization_ids:
            row = await session.get(NativeRealizationModel, rid)
            row.status = "failed_recoverable"
            row.shared_document_state = "failed"
            row.shared_document_run_id = run_id
        await session.commit()


async def _row(factory, rid: str) -> NativeRealizationModel:
    async with factory() as session:
        row = await session.get(NativeRealizationModel, rid)
        session.expunge(row)
        return row


@pytest.mark.asyncio
async def test_learn_then_print_retry_converge_on_one_fresh_shared_run(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "fresh-shared-converge"
    lesson, learn_id, print_id = await _admit_both(db_session, user_id=user_id)
    runs = await _shared_runs(db_session_factory)
    assert len(runs) == 1
    old_id = runs[0].id
    await _fail_shared_run(
        db_session_factory, old_id, status="failed_terminal", realization_ids=[learn_id, print_id]
    )
    learn_before = await _row(db_session_factory, learn_id)

    async with db_session_factory() as session:
        result = await retry_learn_realization(session, realization_id=learn_id, user_id=user_id)
        await session.commit()
    assert result["status"] == "queued"

    runs = await _shared_runs(db_session_factory)
    assert len(runs) == 2
    new_run = next(r for r in runs if r.id != old_id)
    assert new_run.status == "queued"
    learn_after = await _row(db_session_factory, learn_id)
    assert learn_after.realization_revision == learn_before.realization_revision + 1
    assert learn_after.shared_document_run_id == new_run.id
    assert learn_after.status == "queued"
    assert learn_after.shared_document_state == "pending"
    # The realization projects as pending, not failed, against the live source.
    async with db_session_factory() as session:
        source = await load_realization_source(
            session, owner_user_id=user_id, path_lesson_id=lesson.id
        )
        assert source.state == "pending"
        assert source.pending.run_id == new_run.id
        row = await session.get(NativeRealizationModel, learn_id)
        project_realization_status(row, doc_source=source)
        assert row.status == "queued"
        assert row.shared_document_state == "pending"

    async with db_session_factory() as session:
        await retry_print_realization(session, realization_id=print_id, user_id=user_id)
        await session.commit()
    runs = await _shared_runs(db_session_factory)
    assert len(runs) == 2  # converged: no second new run
    print_after = await _row(db_session_factory, print_id)
    assert print_after.shared_document_run_id == new_run.id
    assert print_after.status == "queued"
    assert print_after.shared_document_state == "pending"


@pytest.mark.asyncio
async def test_failed_recoverable_run_without_retryable_leaves_is_cancelled_and_replaced(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "fresh-shared-recoverable"
    _lesson, learn_id, _print_id = await _admit_both(db_session, user_id=user_id)
    old_id = (await _shared_runs(db_session_factory))[0].id
    # failed_recoverable with no failed leaves: in-place retry has nothing to
    # reopen, and ensure_shared_document_run alone would reuse this Run.
    await _fail_shared_run(
        db_session_factory, old_id, status="failed_recoverable", realization_ids=[learn_id]
    )
    async with db_session_factory() as session:
        await retry_learn_realization(session, realization_id=learn_id, user_id=user_id)
        await session.commit()
    runs = await _shared_runs(db_session_factory)
    by_id = {r.id: r for r in runs}
    assert by_id[old_id].status == "cancelled"
    assert len(runs) == 2
    new_run = next(r for r in runs if r.id != old_id)
    assert new_run.status == "queued"
    assert (await _row(db_session_factory, learn_id)).shared_document_run_id == new_run.id


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["learn", "print"])
async def test_exhausted_attempts_return_clear_409(
    db_session: AsyncSession, db_session_factory, path: str
) -> None:
    user_id = f"fresh-shared-exhausted-{path}"
    _lesson, learn_id, print_id = await _admit_both(db_session, user_id=user_id)
    rid = learn_id if path == "learn" else print_id
    retry = retry_learn_realization if path == "learn" else retry_print_realization
    # Attempts 1 and 2 are retried successfully; every attempt then fails.
    for _ in range(2):
        runs = await _shared_runs(db_session_factory)
        await _fail_shared_run(
            db_session_factory, runs[-1].id, status="failed_terminal", realization_ids=[rid]
        )
        async with db_session_factory() as session:
            await retry(session, realization_id=rid, user_id=user_id)
            await session.commit()
    runs = await _shared_runs(db_session_factory)
    assert len(runs) == 3
    await _fail_shared_run(
        db_session_factory, runs[-1].id, status="failed_terminal", realization_ids=[rid]
    )
    before = await _row(db_session_factory, rid)
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as caught:
            await retry(session, realization_id=rid, user_id=user_id)
    assert caught.value.status_code == 409
    detail = caught.value.detail
    assert detail["code"] == "SHARED_DOCUMENT_ATTEMPTS_EXHAUSTED"
    assert "Regenerate the lesson plan" in detail["message"]
    after = await _row(db_session_factory, rid)
    assert after.realization_revision == before.realization_revision  # rolled back
    assert len(await _shared_runs(db_session_factory)) == 3
