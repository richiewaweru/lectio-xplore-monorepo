from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest
from sqlalchemy import func, select
from test_shared_lesson_approved_source import _prepared

from curriculum.shared_task_authoring import ApprovedItemSnapshot
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from document.shared_lesson import run_admission
from document.shared_lesson.approved_source import ApprovedSourceVerificationError
from document.shared_lesson.run_admission import (
    SharedRunAdmissionResult,
    admit_shared_document_run,
)
from infra.database.models import GenerationBuildModel, GenerationRunModel, GenerationWorkItemModel
from infra.generation_runtime import RunAdmissionConflict, RunNotFound


@pytest.mark.asyncio
async def test_admission_creates_one_build_run_and_sourcebook_item_without_commit(
    db_session,
) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)

    result = await admit_shared_document_run(
        db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        request_key="shared-document-request-1",
    )

    assert isinstance(result, SharedRunAdmissionResult)
    assert result.run_admission.created is True
    assert result.sourcebook_admission.created is True
    assert result.run.build_id == result.run_admission.record.build_id
    assert result.sourcebook_work_item.run_id == result.run.id
    assert result.sourcebook_work_item.item_key == "sourcebook"
    assert result.sourcebook_work_item.stage == "sourcebook_generation"
    assert result.sourcebook_work_item.status == "queued"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationBuildModel)
            .where(GenerationBuildModel.owner_user_id == "source-owner")
        )
        == 1
    )


@pytest.mark.asyncio
async def test_duplicate_request_reuses_build_run_and_sourcebook_item(db_session) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)
    first = await admit_shared_document_run(
        db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        request_key="duplicate-request",
    )
    second = await admit_shared_document_run(
        db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        request_key="duplicate-request",
    )

    assert second.run_admission.created is False
    assert second.sourcebook_admission.created is False
    assert second.run.id == first.run.id
    assert second.sourcebook_work_item.id == first.sourcebook_work_item.id
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationRunModel)
            .where(GenerationRunModel.owner_user_id == "source-owner")
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationBuildModel)
            .where(GenerationBuildModel.owner_user_id == "source-owner")
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationWorkItemModel)
            .where(GenerationWorkItemModel.run_id == first.run.id)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_source_hash_conflict_does_not_create_another_build(
    db_session,
    monkeypatch,
) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    first = await admit_shared_document_run(
        db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        request_key="hash-conflict-request",
    )

    plan = source.plan.model_copy(update={"arc": "A changed approved arc"})
    digest = teaching_plan_content_hash(plan)
    variant = source.model_copy(
        update={
            "plan": plan,
            "content_hash": digest,
            "revision_record": source.revision_record.model_copy(
                update={
                    "content_hash": digest,
                    "plan": plan.model_dump(mode="json"),
                }
            ),
        }
    )
    monkeypatch.setattr(
        run_admission,
        "load_current_approved_teaching_plan_source",
        lambda **_kwargs: _resolved(variant),
    )
    monkeypatch.setattr(
        run_admission,
        "load_approved_item_snapshot",
        lambda **_kwargs: _snapshot(variant),
    )

    with pytest.raises(RunAdmissionConflict, match="different run identity"):
        await admit_shared_document_run(
            db_session,
            owner_user_id="source-owner",
            path_lesson_id=lesson.id,
            preparation_generation_id=generation.id,
            request_key="hash-conflict-request",
        )

    assert first.run.id == await db_session.scalar(
        select(GenerationRunModel.id).where(
            GenerationRunModel.owner_user_id == "source-owner",
            GenerationRunModel.request_key == "hash-conflict-request",
        )
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationBuildModel)
            .where(GenerationBuildModel.owner_user_id == "source-owner")
        )
        == 1
    )


@pytest.mark.asyncio
async def test_wrong_owner_path_and_stale_snapshot_fail_before_build_mutation(db_session) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)

    with pytest.raises(RunNotFound, match="owner"):
        await admit_shared_document_run(
            db_session,
            owner_user_id="different-owner",
            path_lesson_id=lesson.id,
            preparation_generation_id=generation.id,
            request_key="wrong-owner-request",
        )
    with pytest.raises(ApprovedSourceVerificationError, match="path lesson"):
        await admit_shared_document_run(
            db_session,
            owner_user_id="source-owner",
            path_lesson_id="missing-path-lesson",
            preparation_generation_id=generation.id,
            request_key="wrong-path-request",
        )

    state = deepcopy(generation.chunked_state_json)
    page = state["page_document_v2"]
    page["teaching_revisions"][0]["approved_item_snapshot"] = None
    page["teaching_revisions"][0]["approved_item_snapshot_hash"] = None
    generation.chunked_state_json = state
    await db_session.flush()
    with pytest.raises(ApprovedSourceVerificationError, match="snapshot"):
        await admit_shared_document_run(
            db_session,
            owner_user_id="source-owner",
            path_lesson_id=lesson.id,
            preparation_generation_id=generation.id,
            request_key="stale-snapshot-request",
        )

    assert await db_session.scalar(select(func.count()).select_from(GenerationBuildModel)) == 0


@pytest.mark.asyncio
async def test_sqlite_concurrent_duplicate_admission_has_one_build_run_and_item(
    db_session,
    db_session_factory,
) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)
    await db_session.commit()

    async def admit_once() -> tuple[bool, bool, str, str]:
        async with db_session_factory() as session:
            result = await admit_shared_document_run(
                session,
                owner_user_id="source-owner",
                path_lesson_id=lesson.id,
                preparation_generation_id=generation.id,
                request_key="sqlite-concurrent-request",
            )
            await session.commit()
            return (
                result.run_admission.created,
                result.sourcebook_admission.created,
                result.run.id,
                result.sourcebook_work_item.id,
            )

    outcomes = await asyncio.gather(admit_once(), admit_once(), return_exceptions=True)
    assert all(not isinstance(outcome, Exception) for outcome in outcomes), outcomes
    values = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    assert sorted(value[0] for value in values) == [False, True]
    assert sorted(value[1] for value in values) == [False, True]
    assert len({value[2] for value in values}) == 1
    assert len({value[3] for value in values}) == 1

    async with db_session_factory() as verify:
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationBuildModel)
                .where(GenerationBuildModel.owner_user_id == "source-owner")
            )
            == 1
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationRunModel)
                .where(GenerationRunModel.request_key == "sqlite-concurrent-request")
            )
            == 1
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.item_key == "sourcebook")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_build_run_and_sourcebook_rollback_together_before_commit(
    db_session,
    db_session_factory,
    monkeypatch,
) -> None:
    generation, lesson, _provenance, _source = await _prepared(db_session)
    real_sourcebook_admission = run_admission.admit_sourcebook_work_item

    async def admit_then_fail(*args, **kwargs):
        await real_sourcebook_admission(*args, **kwargs)
        raise RuntimeError("deliberate post-sourcebook failure")

    monkeypatch.setattr(run_admission, "admit_sourcebook_work_item", admit_then_fail)
    with pytest.raises(RuntimeError, match="post-sourcebook"):
        await admit_shared_document_run(
            db_session,
            owner_user_id="source-owner",
            path_lesson_id=lesson.id,
            preparation_generation_id=generation.id,
            request_key="rollback-request",
        )
    await db_session.rollback()

    async with db_session_factory() as verify:
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationBuildModel)
                .where(GenerationBuildModel.owner_user_id == "source-owner")
            )
            == 0
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationRunModel)
                .where(GenerationRunModel.request_key == "rollback-request")
            )
            == 0
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.item_key == "sourcebook")
            )
            == 0
        )


async def _resolved(value):
    return value


async def _snapshot(source):
    return ApprovedItemSnapshot(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        items={},
    )
