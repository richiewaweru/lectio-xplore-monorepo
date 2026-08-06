"""Phase 02.1: concurrent page-document mutation safety."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from core.database.models import GenerationModel, UserModel
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    empty_page_document_state,
)


async def _seed(db_session_factory) -> tuple[str, str, int]:
    gid = str(uuid.uuid4())
    async with db_session_factory() as session:
        user_id = f"user-{gid[:8]}"
        state = empty_page_document_state()
        state["lesson_packet"] = {"lesson": {"objective": "X"}}
        state["teaching_plan"] = {"arc": "t", "sections": []}
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="T"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="queued",
                chunked_state_json={"page_document_v2": state, "stage": "queued"},
            )
        )
        await session.commit()
        repo = PageDocumentRepository(session, gid)
        lease = await repo.claim_execution(worker_id="mut-worker")
        assert lease is not None
        await repo.transition(
            expected={"planning_forms"},
            target="writing_blocks",
            event="writing_blocks_started",
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
        )
        return gid, lease.worker_id, lease.lease_token


@pytest.mark.asyncio
async def test_heartbeat_and_block_outcome_do_not_clobber(db_session_factory) -> None:
    gid, worker_id, token = await _seed(db_session_factory)

    async def _heartbeat() -> None:
        async with db_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            for _ in range(8):
                await repo.heartbeat(worker_id=worker_id, lease_token=token)

    async def _blocks() -> None:
        async with db_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            for i in range(8):
                await repo.save_block_outcome(
                    f"explain:b{i}:everyone",
                    {
                        "status": "ready",
                        "block_id": f"b{i}",
                        "content": {"paragraphs": [f"p{i}"]},
                    },
                    worker_id=worker_id,
                    lease_token=token,
                )

    await asyncio.gather(_heartbeat(), _blocks())
    async with db_session_factory() as session:
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        assert state["execution"]["heartbeat_at"]
        assert state["execution"]["worker_id"] == worker_id
        assert len(state["block_execution"]) == 8


@pytest.mark.asyncio
async def test_event_append_and_block_write_preserve_both(db_session_factory) -> None:
    gid, worker_id, token = await _seed(db_session_factory)

    async def _events() -> None:
        async with db_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            for i in range(10):
                await repo.append_event(
                    {"type": "ping", "i": i},
                    worker_id=worker_id,
                    lease_token=token,
                )

    async def _block() -> None:
        async with db_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            await repo.save_block_outcome(
                "orient:o1:everyone",
                {"status": "ready", "content": {"paragraphs": ["keep"]}},
                worker_id=worker_id,
                lease_token=token,
            )

    await asyncio.gather(_events(), _block())
    async with db_session_factory() as session:
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        assert state["block_execution"]["orient:o1:everyone"]["status"] == "ready"
        assert any(e.get("type") == "ping" for e in state["events"])
