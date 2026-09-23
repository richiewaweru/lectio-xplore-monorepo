from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _approved_native_preparation
from tests.print_learn.test_p08_integration_gates import P08LearnMockProvider

from application.unit_lesson.realizations import request_outputs
from application.unit_lesson.realize_learn_handoff import (
    realize_learn_from_preparation,
    retry_learn_realization,
)
from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    NativeRealizationModel,
    PathVersionModel,
)
from core.entities.user import User
from curriculum.models import PathLessonMutationRequest
from curriculum.workspace_projection import project_lesson_workspace
from learn.generation import native_execution
from learn.generation.fencing import (
    LEARN_EXECUTION_KEY,
    empty_learn_execution_meta,
    fail_stale_learn_executions,
)
from learn.generation.units_routes import generate_learn_realization
from learn.generation.worker import LearnRealizationWorker


@pytest.mark.asyncio
async def test_p04_create_is_durable_queued_and_duplicate_reuses_output(
    db_session: AsyncSession,
) -> None:
    lesson, plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-admit"
    )

    first = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-admit",
        path_lesson_id=lesson.id,
        admission_request_key="create-once",
    )
    second = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-admit",
        path_lesson_id=lesson.id,
        admission_request_key="create-once",
    )

    assert first["status"] == second["status"] == "queued"
    assert first["output_id"] != lesson.pack_id
    assert second["output_id"] == first["output_id"]
    assert second["realization_id"] == first["realization_id"]
    output = await db_session.get(GenerationModel, first["output_id"])
    assert output is not None
    assert output.status == "queued"
    assert output.document_json is None
    state = output.chunked_state_json or {}
    assert state["native_learn"] is True
    assert state["preparation_generation_id"] == lesson.pack_id
    assert state["teaching_plan_revision"] == plan.revision
    assert state["teaching_plan_hash"] == first["teaching_plan_hash"]
    count = await db_session.scalar(
        select(func.count()).select_from(NativeRealizationModel).where(
            NativeRealizationModel.path_lesson_id == lesson.id,
            NativeRealizationModel.path == "learn",
        )
    )
    assert count == 1
    generation_count = await db_session.scalar(
        select(func.count()).select_from(GenerationModel).where(
            GenerationModel.id == first["output_id"]
        )
    )
    assert generation_count == 1


@pytest.mark.asyncio
async def test_p04_create_replay_leaves_recoverable_failure_parked(
    db_session: AsyncSession,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-create-parked"
    )
    result = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-create-parked",
        path_lesson_id=lesson.id,
        admission_request_key="same-create",
    )
    row = await db_session.get(NativeRealizationModel, result["realization_id"])
    output = await db_session.get(GenerationModel, result["output_id"])
    assert row is not None and output is not None
    row.status = "failed_recoverable"
    output.status = "failed"
    await db_session.flush()

    replay = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-create-parked",
        path_lesson_id=lesson.id,
        admission_request_key="same-create",
    )
    assert replay["status"] == "failed_recoverable"
    assert replay["output_id"] == result["output_id"]
    assert row.realization_revision == 1
    assert output.status == "failed"


@pytest.mark.asyncio
async def test_p04_pathless_studio_learn_returns_typed_recovery_conflict(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        GenerationModel(
            id="p04-pathless",
            user_id="p04-studio-user",
            subject="science",
            context="standalone Studio prep",
            status="awaiting_teaching_approval",
            requested_template_id="lesson",
            requested_preset_id="standard",
            chunked_state_json={},
        )
    )
    await db_session.flush()

    with pytest.raises(HTTPException) as raised:
        await realize_learn_from_preparation(
            db_session,
            preparation_generation_id="p04-pathless",
            user_id="p04-studio-user",
        )

    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "LEARN_PATH_LESSON_REQUIRED"
    assert raised.value.detail["recovery_action"] == "open_unit_lesson"


@pytest.mark.asyncio
async def test_p04_unit_create_route_returns_202_with_durable_queued_identity(
    db_session: AsyncSession,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-route-202"
    )
    user = User(
        id="p04-route-202",
        email="p04-route-202@example.invalid",
        name="P04 route test",
        created_at="2026-09-23T00:00:00+00:00",
        updated_at="2026-09-23T00:00:00+00:00",
    )
    version = await db_session.get(PathVersionModel, lesson.path_version_id)
    assert version is not None
    response = Response()

    result = await generate_learn_realization(
        unit_id=version.unit_id,
        lesson_id=lesson.id,
        body=PathLessonMutationRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            lesson_revision=lesson.revision,
        ),
        current_user=user,
        session=db_session,
        idempotency_key=None,
        response=response,
    )
    assert response.status_code == 202
    assert result["status"] == "queued"
    assert result["output_id"] != lesson.pack_id
    row = await db_session.get(NativeRealizationModel, result["realization_id"])
    assert row is not None and row.status == "queued"


@pytest.mark.asyncio
async def test_p04_worker_completes_only_learn_output_and_links_editable_document(
    db_session: AsyncSession,
    db_session_factory,
    monkeypatch,
) -> None:
    lesson, plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-worker-ready"
    )
    result = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-worker-ready",
        path_lesson_id=lesson.id,
    )
    learn_row = await db_session.get(NativeRealizationModel, result["realization_id"])
    assert learn_row is not None
    print_rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=int(plan.revision or 1),
        teaching_plan_hash=result["teaching_plan_hash"],
        preparation_generation_id=str(lesson.pack_id),
    )
    assert len(print_rows) == 1
    print_row = print_rows[0][0]
    print_row.status = "ready"
    print_row.output_id = "p04-existing-print-output"
    # API admission commits before a separate worker process can poll it.
    await db_session.commit()
    # The reliability checkpoint writer uses its own session. Point it at this
    # test's database rather than the process-wide runtime database.
    from learn.generation import reliability_persist

    monkeypatch.setattr(reliability_persist, "async_session_factory", db_session_factory)

    worker = LearnRealizationWorker(worker_id="p04-test-worker", provider=P08LearnMockProvider())
    # Match the lifespan worker: each claim runs in a disposable session. A
    # fresh session below proves success was committed before that session
    # closed rather than merely visible in its identity map.
    async with db_session_factory() as worker_session:
        assert await worker.run_one(worker_session) is True
        assert await worker.run_one(worker_session) is False

    await db_session.refresh(learn_row)
    await db_session.refresh(print_row)
    output = await db_session.get(GenerationModel, result["output_id"])
    assert output is not None
    assert learn_row.status == "ready"
    assert learn_row.output_id == output.id
    assert output.status == "completed"
    assert isinstance(output.document_json, dict)
    editable = await db_session.scalar(
        select(EditableLessonModel).where(
            EditableLessonModel.source_generation_id == output.id,
            EditableLessonModel.user_id == "p04-worker-ready",
        )
    )
    assert editable is not None
    assert editable.document_json["id"] == editable.id
    assert print_row.status == "ready"
    assert print_row.output_id == "p04-existing-print-output"
    source = await db_session.get(GenerationModel, str(lesson.pack_id))
    assert source is not None
    page_state = (source.chunked_state_json or {}).get("page_document_v2") or {}
    assert page_state["teaching_review"]["status"] == "approved"
    assert page_state["teaching_review"]["approved_revision"] == 1


@pytest.mark.asyncio
async def test_p04_worker_parks_escaped_post_production_failure(
    db_session: AsyncSession,
    db_session_factory,
    monkeypatch,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-finalize-failure"
    )
    result = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-finalize-failure",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()

    from learn.generation import reliability_persist

    monkeypatch.setattr(reliability_persist, "async_session_factory", db_session_factory)

    def fail_publication_validation(_document):
        raise ValueError("injected post-production validation failure")

    monkeypatch.setattr(
        native_execution,
        "validate_publishable_lesson_document",
        fail_publication_validation,
    )
    worker = LearnRealizationWorker(
        worker_id="p04-finalize-worker", provider=P08LearnMockProvider()
    )
    async with db_session_factory() as worker_session:
        assert await worker.run_one(worker_session) is True

    async with db_session_factory() as verify_session:
        row = await verify_session.get(NativeRealizationModel, result["realization_id"])
        output = await verify_session.get(GenerationModel, result["output_id"])
        source = await verify_session.get(GenerationModel, str(lesson.pack_id))
        assert row is not None and output is not None and source is not None
        assert row.status == "failed_recoverable"
        assert row.error_summary == "injected post-production validation failure"
        assert output.status == "failed"
        error_detail = (output.chunked_state_json or {}).get("error_detail") or {}
        assert error_detail["code"] == "LEARN_EXECUTION_FINALIZATION_FAILED"
        assert error_detail["failure_class"] == "learn_finalization"
        assert error_detail["recovery_action"] == "retry"
        assert (output.chunked_state_json or {})[LEARN_EXECUTION_KEY]["status"] == "failed"
        page_state = (source.chunked_state_json or {}).get("page_document_v2") or {}
        assert page_state["teaching_review"]["status"] == "approved"
        editable = await verify_session.scalar(
            select(EditableLessonModel).where(
                EditableLessonModel.source_generation_id == output.id
            )
        )
        assert editable is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corruption",
    ["foreign_owner", "wrong_path", "wrong_preparation", "wrong_revision", "wrong_hash"],
)
async def test_p04_worker_parks_corrupt_foreign_output_without_mutating_it(
    db_session: AsyncSession, corruption: str
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-foreign-output"
    )
    result = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-foreign-output",
        path_lesson_id=lesson.id,
    )
    row = await db_session.get(NativeRealizationModel, result["realization_id"])
    assert row is not None
    owner_id = "another-owner" if corruption == "foreign_owner" else "p04-foreign-output"
    pinned = {
        "native_learn": True,
        "preparation_generation_id": row.preparation_generation_id,
        "teaching_plan_id": row.teaching_plan_id,
        "teaching_plan_revision": row.teaching_plan_revision,
        "teaching_plan_hash": row.teaching_plan_hash,
    }
    if corruption == "wrong_path":
        pinned["native_learn"] = False
    elif corruption == "wrong_preparation":
        pinned["preparation_generation_id"] = "other-preparation"
    elif corruption == "wrong_revision":
        pinned["teaching_plan_revision"] = int(row.teaching_plan_revision) + 1
    elif corruption == "wrong_hash":
        pinned["teaching_plan_hash"] = "corrupt-content-hash"
    corrupt_state = {**pinned, "sentinel": "untouched"}
    foreign = GenerationModel(
        id=f"corrupt-learn-output-{corruption}",
        user_id=owner_id,
        subject="science",
        context="corrupt artifact pointer",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        chunked_state_json=corrupt_state,
    )
    db_session.add(foreign)
    row.output_id = foreign.id
    await db_session.commit()

    worker = LearnRealizationWorker(worker_id="p04-integrity-worker")
    assert await worker.run_one(db_session) is True
    await db_session.refresh(row)
    await db_session.refresh(foreign)
    assert row.status == "failed_terminal"
    assert foreign.status == "queued"
    assert foreign.chunked_state_json == corrupt_state


@pytest.mark.asyncio
async def test_p04_ready_replay_requires_document_and_editable_link(
    db_session: AsyncSession,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-incomplete-ready"
    )
    result = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-incomplete-ready",
        path_lesson_id=lesson.id,
    )
    row = await db_session.get(NativeRealizationModel, result["realization_id"])
    output = await db_session.get(GenerationModel, result["output_id"])
    assert row is not None and output is not None
    row.status = "ready"
    output.status = "completed"
    output.document_json = {"title": "saved but not editable"}
    await db_session.flush()

    with pytest.raises(HTTPException) as raised:
        await realize_learn_from_preparation(
            db_session,
            preparation_generation_id=str(lesson.pack_id),
            user_id="p04-incomplete-ready",
            path_lesson_id=lesson.id,
        )
    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "LEARN_READY_OUTPUT_INCOMPLETE"


@pytest.mark.asyncio
async def test_p04_retry_is_explicit_allocates_one_output_and_preserves_old_output(
    db_session: AsyncSession,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p04-retry"
    )
    result = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p04-retry",
        path_lesson_id=lesson.id,
    )
    row = await db_session.get(NativeRealizationModel, result["realization_id"])
    old_output = await db_session.get(GenerationModel, result["output_id"])
    assert row is not None and old_output is not None
    row.status = "failed_recoverable"
    row.error_summary = "provider timeout"
    old_output.status = "failed"
    await db_session.flush()

    retried = await retry_learn_realization(
        db_session, realization_id=row.id, user_id="p04-retry"
    )
    replayed_retry = await retry_learn_realization(
        db_session, realization_id=row.id, user_id="p04-retry"
    )

    assert retried["status"] == replayed_retry["status"] == "queued"
    assert retried["output_id"] != result["output_id"]
    assert replayed_retry["output_id"] == retried["output_id"]
    assert replayed_retry["realization_revision"] == retried["realization_revision"] == 2
    await db_session.refresh(row)
    assert row.output_id == retried["output_id"]
    assert row.realization_revision == 2
    assert old_output.status == "failed"


@pytest.mark.asyncio
async def test_p04_concurrent_retry_reuses_single_new_learn_output(
    db_session_factory,
) -> None:
    async with db_session_factory() as setup:
        lesson, _plan, _source, _document = await _approved_native_preparation(
            setup, user_id="p04-concurrent-retry"
        )
        result = await realize_learn_from_preparation(
            setup,
            preparation_generation_id=str(lesson.pack_id),
            user_id="p04-concurrent-retry",
            path_lesson_id=lesson.id,
        )
        row = await setup.get(NativeRealizationModel, result["realization_id"])
        old_output = await setup.get(GenerationModel, result["output_id"])
        assert row is not None and old_output is not None
        row.status = "failed_recoverable"
        old_output.status = "failed"
        await setup.commit()

    async def _retry() -> dict:
        async with db_session_factory() as session:
            try:
                result = await retry_learn_realization(
                    session,
                    realization_id=result_id,
                    user_id="p04-concurrent-retry",
                )
                await session.commit()
                return {"result": result}
            except HTTPException as exc:
                await session.rollback()
                return {"conflict": exc.detail}

    result_id = str(result["realization_id"])
    outcomes = await asyncio.gather(_retry(), _retry())
    accepted = [outcome["result"] for outcome in outcomes if "result" in outcome]
    conflicts = [outcome["conflict"] for outcome in outcomes if "conflict" in outcome]
    assert accepted
    assert all(outcome["output_id"] == accepted[0]["output_id"] for outcome in accepted)
    assert all(
        conflict["code"] == "LEARN_RETRY_ALREADY_CLAIMED"
        for conflict in conflicts
        if isinstance(conflict, dict)
    )
    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, result_id)
        assert row is not None
        assert row.status == "queued"
        assert row.realization_revision == 2
        assert row.output_id != result["output_id"]
        old_output = await verify.get(GenerationModel, result["output_id"])
        new_output = await verify.get(GenerationModel, row.output_id)
        assert old_output is not None and old_output.status == "failed"
        assert new_output is not None and new_output.status == "queued"
        owned_generations = await verify.scalar(
            select(func.count()).select_from(GenerationModel).where(
                GenerationModel.user_id == "p04-concurrent-retry"
            )
        )
        assert owned_generations == 3  # preparation + original output + one retry output


@pytest.mark.asyncio
async def test_p07_expired_worker_is_parked_without_touching_ready_print_sibling(
    db_session: AsyncSession,
) -> None:
    """An interrupted Learn run becomes retryable; its ready Print sibling and approval survive."""
    lesson, plan, source_state, _document = await _approved_native_preparation(
        db_session, user_id="p07-interrupted-learn"
    )
    admitted = await realize_learn_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p07-interrupted-learn",
        path_lesson_id=lesson.id,
    )
    learn = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    output = await db_session.get(GenerationModel, admitted["output_id"])
    assert learn is not None and output is not None

    print_rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=int(plan.revision or 1),
        teaching_plan_hash=admitted["teaching_plan_hash"],
        preparation_generation_id=str(lesson.pack_id),
    )
    print_row = print_rows[0][0]
    print_row.status = "ready"
    print_row.output_id = "p07-ready-print-sibling"
    print_identity = (
        print_row.status,
        print_row.output_id,
        print_row.realization_revision,
        print_row.teaching_plan_hash,
    )

    interrupted_at = datetime.now(UTC) - timedelta(minutes=30)
    execution = empty_learn_execution_meta()
    execution.update(
        {
            "worker_id": "learn-worker-lost",
            "lease_token": 7,
            "lease_seconds": 10,
            "heartbeat_at": interrupted_at.isoformat().replace("+00:00", "Z"),
            "claimed_at": interrupted_at.isoformat().replace("+00:00", "Z"),
            "status": "running",
            # A completed sibling work item must be retained when the process is recovered.
            "checkpoints": {
                "section:orient": {
                    "status": "ready",
                    "payload": {"text": "Already completed before worker loss."},
                    "lease_token": 7,
                }
            },
            "call_budgets": {"section:explain": {"consumed": 1}},
        }
    )
    output_state = dict(output.chunked_state_json or {})
    output_state[LEARN_EXECUTION_KEY] = execution
    output.chunked_state_json = output_state
    output.status = "running"
    learn.status = "running"
    source = await db_session.get(GenerationModel, str(lesson.pack_id))
    assert source is not None
    approval_before = dict(source_state.get("page_document_v2") or {})
    await db_session.commit()

    recovered = await fail_stale_learn_executions(
        db_session, now=datetime.now(UTC)
    )
    assert recovered == 1
    restarted_worker = LearnRealizationWorker(worker_id="p07-restarted-worker")
    assert await restarted_worker.run_one(db_session) is False
    await db_session.refresh(learn)
    await db_session.refresh(output)
    await db_session.refresh(print_row)
    await db_session.refresh(source)
    recovered_execution = (output.chunked_state_json or {}).get(LEARN_EXECUTION_KEY) or {}
    assert learn.status == "failed_recoverable"
    assert output.status == "failed"
    assert "interrupted" in str(learn.error_summary).lower()
    assert recovered_execution["checkpoints"]["section:orient"]["status"] == "ready"
    assert recovered_execution["checkpoints"]["section:orient"]["payload"]["text"].startswith(
        "Already completed"
    )
    assert recovered_execution["call_budgets"]["section:explain"]["consumed"] == 1
    assert (
        print_row.status,
        print_row.output_id,
        print_row.realization_revision,
        print_row.teaching_plan_hash,
    ) == print_identity
    assert (source.chunked_state_json or {}).get("page_document_v2") == approval_before


def test_p04_stale_status_does_not_offer_retry() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-p04",
        learn_realization={
            "realization_id": "learn-run",
            "path": "learn",
            "status": "stale",
            "output_id": "old-learn-output",
            "open_href": "/builder/from-native-learn/old-learn-output",
            "error_summary": "Pinned approval is stale.",
        },
    )

    assert workspace.learn.state == "failed_terminal"
    assert workspace.learn.error is not None
    assert workspace.learn.error.retryable is False
    assert workspace.learn.error.recovery_action == "reprepare"
