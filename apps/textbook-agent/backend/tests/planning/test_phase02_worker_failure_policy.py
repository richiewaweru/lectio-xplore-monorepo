"""Patch 02.1A: worker failure classification Approach B integration."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state
from planning.whole_lesson.states import LeaseLostError
from planning.whole_lesson.worker import NativeExecutionWorker


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-worker-fail",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[SlotRecord(slot_id="orient", typical_intents=["orient"])],
        limits=LessonLimits(),
    )


async def _seed(*, status: str = "writing_blocks") -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    state = empty_page_document_state()
    state["lesson_packet"] = _packet().model_dump(mode="json")
    state["teaching_plan"] = {"arc": "test", "sections": []}
    state["form_plan"] = {
        "sections": [
            {
                "slot_id": "orient",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Open.",
                        "object": "prose",
                    }
                ],
            }
        ]
    }
    state["form_validation"] = {"ok": True}
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status=status,
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": status,
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


@pytest.mark.asyncio
async def test_transport_failure_is_recoverable() -> None:
    gid = await _seed()
    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="w-transport"
        )
        assert lease is not None
    worker = NativeExecutionWorker(worker_id="w-transport")
    await worker._persist_failure(lease, httpx.ConnectError("boom"))
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"


@pytest.mark.asyncio
async def test_programming_failure_is_terminal() -> None:
    gid = await _seed()
    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="w-prog"
        )
        assert lease is not None
    worker = NativeExecutionWorker(worker_id="w-prog")
    await worker._persist_failure(lease, TypeError("broken"))
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_terminal"


@pytest.mark.asyncio
async def test_unknown_failure_is_terminal() -> None:
    gid = await _seed()
    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="w-unk"
        )
        assert lease is not None
    worker = NativeExecutionWorker(worker_id="w-unk")
    await worker._persist_failure(lease, RuntimeError("mystery"))
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_terminal"


@pytest.mark.asyncio
async def test_lease_lost_does_not_transition() -> None:
    gid = await _seed()
    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="w-lease"
        )
        assert lease is not None
    worker = NativeExecutionWorker(worker_id="w-lease")
    await worker._persist_failure(lease, LeaseLostError("stolen"))
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "writing_blocks"


@pytest.mark.asyncio
async def test_normalize_writer_status_figure_pending() -> None:
    from generation.page_objects import write_figure, WriterContext
    from planning.whole_lesson.executor import normalize_writer_status
    from v3_blueprint.planning.models import PlannedBlock

    planned = PlannedBlock(
        id="fig-1",
        position=0,
        intent="show-structure",
        brief="Show plants.",
        object="figure",
        evidence="anchor-1",
    )
    result = write_figure(
        WriterContext(
            planned=planned,
            generation_id="gen-x",
        )
    )
    assert result.status == "visual_pending"
    assert result.content["asset"]["status"] == "pending"
    assert (
        normalize_writer_status(
            object_id="figure",
            writer_status="pending",
            content=result.content,
        )
        == "visual_pending"
    )
