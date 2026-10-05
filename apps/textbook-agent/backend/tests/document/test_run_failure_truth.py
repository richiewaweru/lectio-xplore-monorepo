"""A failed_recoverable shared-document Run is reported as a failure, not as queued."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_lesson_approved_source import _prepared

from application.unit_lesson.realization_projection import (
    effective_status,
    project_realization_status,
    recovery_action_for,
)
from application.unit_lesson.realization_retry import retry_failed_run_in_place
from document.shared_lesson.realization_source import (
    ensure_shared_document_run,
    load_realization_source,
)
from infra.database.models import GenerationRunModel, GenerationWorkItemModel

OWNER = "source-owner"
SAFE_403 = "Figure generation failed: the image provider rejected the request (HTTP 403)."


async def _seed_failed_media(db_session, lesson, *, error_code: str, attempt: int = 1):
    run = await ensure_shared_document_run(
        db_session, owner_user_id=OWNER, path_lesson_id=lesson.id
    )
    run_id = run.id
    for existing in (
        await db_session.scalars(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
        )
    ).all():
        existing.status = "ready"
        existing.output_json = {"ok": True}
        existing.output_hash = "f" * 64
    db_session.add(
        GenerationWorkItemModel(
            run_id=run_id,
            item_key="write:s1",
            stage="section_writing",
            status="ready",
            input_hash="a" * 64,
            definition_hash="b" * 64,
            output_json={"ok": True},
            output_hash="c" * 64,
        )
    )
    media = GenerationWorkItemModel(
        run_id=run_id,
        item_key="media:fig-1",
        stage="media_generation",
        status="failed_recoverable",
        attempt=attempt,
        max_attempts=3,
        input_hash="d" * 64,
        definition_hash="e" * 64,
        error_code=error_code,
        error_class="provider_transport",
        error_summary=SAFE_403,
        recovery_action="retry",
    )
    db_session.add(media)
    run_row = await db_session.get(GenerationRunModel, run_id)
    run_row.status = "failed_recoverable"
    await db_session.commit()
    return run_id, media.id


@pytest.mark.asyncio
async def test_failed_media_run_loads_as_recoverable_with_specific_code(db_session) -> None:
    _generation, lesson, _provenance, _source = await _prepared(db_session)
    run_id, item_id = await _seed_failed_media(db_session, lesson, error_code="provider_http_503")

    result = await load_realization_source(db_session, owner_user_id=OWNER, path_lesson_id=lesson.id)

    assert result.state == "recoverable"
    failure = result.recoverable.failure
    assert result.recoverable.run_id == run_id
    assert failure.error_code == "provider_http_503"
    assert failure.work_item_id == item_id
    assert failure.retryable is True
    assert failure.auto_retrying is True  # transient, attempts remain


@pytest.mark.asyncio
async def test_auth_failure_is_not_reported_as_auto_retrying(db_session) -> None:
    _generation, lesson, _provenance, _source = await _prepared(db_session)
    await _seed_failed_media(db_session, lesson, error_code="provider_http_403")

    result = await load_realization_source(db_session, owner_user_id=OWNER, path_lesson_id=lesson.id)

    assert result.state == "recoverable"
    assert result.recoverable.failure.auto_retrying is False
    assert result.recoverable.failure.retryable is True


@pytest.mark.asyncio
async def test_projection_marks_realization_failed_recoverable_not_queued(db_session) -> None:
    _generation, lesson, _provenance, _source = await _prepared(db_session)
    run_id, _item = await _seed_failed_media(db_session, lesson, error_code="provider_http_403")
    result = await load_realization_source(db_session, owner_user_id=OWNER, path_lesson_id=lesson.id)
    row = SimpleNamespace(
        status="queued",
        error_summary=None,
        shared_document_state="pending",
        shared_document_run_id=None,
        generation_run_id=None,
    )

    project_realization_status(row, doc_source=result)

    assert row.status == "failed_recoverable"
    assert row.shared_document_run_id == run_id
    assert row.error_summary == f"provider_http_403: {SAFE_403}"
    assert row.shared_document_state == "recoverable"
    # Not mistaken for a legacy (terminal) row, and Retry is offered.
    assert effective_status(row) == "failed_recoverable"
    assert recovery_action_for(row) == "retry"


@pytest.mark.asyncio
async def test_retry_requeues_only_failed_media_leaves(db_session) -> None:
    _generation, lesson, _provenance, _source = await _prepared(db_session)
    run_id, media_id = await _seed_failed_media(db_session, lesson, error_code="provider_http_403")
    row = SimpleNamespace(
        status="failed_recoverable",
        error_summary="x",
        shared_document_state="recoverable",
        shared_document_run_id=run_id,
        generation_run_id=None,
        teaching_plan_revision=1,
        realization_revision=1,
    )

    assert await retry_failed_run_in_place(db_session, row=row, owner_user_id=OWNER) is True
    await db_session.commit()

    db_session.expire_all()
    items = {
        item.item_key: item
        for item in (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
            )
        ).all()
    }
    assert items["media:fig-1"].status == "queued"
    assert items["media:fig-1"].attempt == 2
    assert items["media:fig-1"].error_code is None
    # Healthy siblings keep their output; the plan revision/realization are untouched.
    assert items["write:s1"].status == "ready"
    assert items["write:s1"].output_json == {"ok": True}
    assert (await db_session.get(GenerationRunModel, run_id)).status == "queued"
    assert row.status == "queued"
    assert row.shared_document_state == "pending"
    assert row.teaching_plan_revision == 1
    assert row.realization_revision == 1


@pytest.mark.asyncio
async def test_retry_declines_when_leaf_needs_review(db_session) -> None:
    _generation, lesson, _provenance, _source = await _prepared(db_session)
    run_id, media_id = await _seed_failed_media(db_session, lesson, error_code="provider_http_403")
    item = await db_session.get(GenerationWorkItemModel, media_id)
    item.recovery_action = "review"
    await db_session.commit()
    row = SimpleNamespace(
        status="failed_recoverable",
        error_summary="x",
        shared_document_state="recoverable",
        shared_document_run_id=run_id,
        generation_run_id=None,
    )

    assert await retry_failed_run_in_place(db_session, row=row, owner_user_id=OWNER) is False
