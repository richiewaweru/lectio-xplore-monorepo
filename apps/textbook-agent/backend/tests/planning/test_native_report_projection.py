"""Native execution status projection into the shared generation report."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, UserModel
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    empty_page_document_state,
)


async def _seed_generation(session: AsyncSession, *, status: str) -> str:
    generation_id = str(uuid.uuid4())
    user_id = f"user-{generation_id[:8]}"
    session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
    session.add(
        GenerationModel(
            id=generation_id,
            user_id=user_id,
            subject="Science",
            requested_template_id="guided-concept-path",
            requested_preset_id="default",
            status=status,
            chunked_state_json={
                "native_whole_lesson": True,
                "page_document_v2": empty_page_document_state(),
                "stage": status,
            },
            report_json={
                "booklet_status": "streaming_preview",
                "summary": {"planned_sections": 5},
                "process_status": "stale",
            },
        )
    )
    await session.commit()
    return generation_id


def _assert_report(
    generation: GenerationModel,
    *,
    native_stage: str,
    process_status: str,
) -> None:
    report = dict(generation.report_json or {})
    assert report["native_stage"] == native_stage
    assert report["process_status"] == process_status
    assert report["booklet_status"] == "streaming_preview"
    assert report["summary"] == {"planned_sections": 5}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (TimeoutError("provider timed out"), "failed_recoverable"),
        (TypeError("invalid writer output"), "failed_terminal"),
    ],
    ids=["recoverable", "terminal"],
)
async def test_persist_native_failure_projects_consistent_report_status(
    db_session_factory,
    failure: Exception,
    expected_status: str,
) -> None:
    async with db_session_factory() as session:
        generation_id = await _seed_generation(session, status="planning_forms")
        repo = PageDocumentRepository(session, generation_id)

        await repo.persist_native_failure(exc=failure, stage="planning_forms")

        generation = await session.get(GenerationModel, generation_id)
        assert generation is not None
        assert generation.status == expected_status
        assert generation.chunked_state_json["stage"] == expected_status
        _assert_report(
            generation,
            native_stage=expected_status,
            process_status=expected_status,
        )


@pytest.mark.asyncio
async def test_retry_reset_and_claim_project_running_status(db_session_factory) -> None:
    async with db_session_factory() as session:
        generation_id = await _seed_generation(session, status="failed_recoverable")
        repo = PageDocumentRepository(session, generation_id)

        await repo.transition(
            expected={"failed_recoverable"},
            target="queued",
            event="native_retry_accepted",
        )
        generation = await session.get(GenerationModel, generation_id)
        assert generation is not None
        _assert_report(
            generation,
            native_stage="queued",
            process_status="running",
        )

        lease = await repo.claim_execution(worker_id="report-projection-worker")

        assert lease is not None
        assert lease.stage == "planning_forms"
        generation = await session.get(GenerationModel, generation_id)
        assert generation is not None
        _assert_report(
            generation,
            native_stage="planning_forms",
            process_status="running",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "native_stage",
    [
        "item_generation",
        "planning_teaching",
        "awaiting_teaching_approval",
        "queued",
        "planning_forms",
        "writing_sections",
        "writing_blocks",
        "assembling",
        "awaiting_visuals",
    ],
)
async def test_active_native_stages_project_running(
    db_session_factory,
    native_stage: str,
) -> None:
    async with db_session_factory() as session:
        generation_id = await _seed_generation(session, status=native_stage)
        repo = PageDocumentRepository(session, generation_id)

        await repo.mutate_state(mutation=lambda _generation, _state: None)

        generation = await session.get(GenerationModel, generation_id)
        assert generation is not None
        _assert_report(
            generation,
            native_stage=native_stage,
            process_status="running",
        )


@pytest.mark.asyncio
async def test_ready_projects_completed_without_changing_booklet_status(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        generation_id = await _seed_generation(session, status="assembling")
        repo = PageDocumentRepository(session, generation_id)

        await repo.transition(
            expected={"assembling"},
            target="ready",
            event="document_ready",
        )

        generation = await session.get(GenerationModel, generation_id)
        assert generation is not None
        _assert_report(
            generation,
            native_stage="ready",
            process_status="completed",
        )
