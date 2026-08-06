"""Phase 02.1: transitions, atomic claim, lease fencing."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, UserModel
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    claim_next_native_job,
    empty_page_document_state,
)
from planning.whole_lesson.service import approve_teaching_and_queue
from planning.whole_lesson.states import (
    LEGAL_TRANSITIONS,
    ExecutionLease,
    IllegalTransitionError,
    LeaseLostError,
    assert_legal_transition,
)


async def _seed_native_generation(
    session: AsyncSession,
    *,
    generation_id: str | None = None,
    status: str = "awaiting_teaching_approval",
) -> str:
    gid = generation_id or str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
    state = empty_page_document_state()
    state["lesson_packet"] = {"lesson": {"objective": "Learn X"}}
    state["teaching_plan"] = {"arc": "test", "sections": []}
    state["teaching_review"] = {
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "revision": 1,
        "teacher_note": None,
    }
    session.add(
        GenerationModel(
            id=gid,
            user_id=user_id,
            subject="Science",
            requested_template_id="guided-concept-path",
            requested_preset_id="default",
            status=status,
            chunked_state_json={"page_document_v2": state, "stage": status},
        )
    )
    await session.commit()
    return gid


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (src, dst)
        for src, targets in LEGAL_TRANSITIONS.items()
        for dst in sorted(targets)
    ],
)
def test_legal_transitions_allowed(current: str, target: str) -> None:
    assert_legal_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("awaiting_teaching_approval", "planning_forms"),
        ("queued", "ready"),
        ("ready", "queued"),
        ("failed_terminal", "queued"),
        ("planning_forms", "ready"),
        ("writing_blocks", "queued"),
    ],
)
def test_illegal_transitions_rejected(current: str, target: str) -> None:
    with pytest.raises(IllegalTransitionError):
        assert_legal_transition(current, target)


@pytest.mark.asyncio
async def test_repository_transition_updates_status_and_stage(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session)
        repo = PageDocumentRepository(session, gid)
        await repo.transition(
            expected={"awaiting_teaching_approval"},
            target="queued",
            event="teaching_plan_approved",
        )
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "queued"
        state = await repo.load_page_generation_state()
        assert state["execution"]["heartbeat_at"]


@pytest.mark.asyncio
async def test_illegal_repository_transition_raises(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session)
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(IllegalTransitionError):
            await repo.transition(
                expected={"awaiting_teaching_approval"},
                target="ready",
                event="bad",
            )


@pytest.mark.asyncio
async def test_approve_queues_without_executing(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session)
        result = await approve_teaching_and_queue(
            session, gid, expected_revision=1, reviewed_by="teacher"
        )
        assert result["status"] == "queued"
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "queued"
        result2 = await approve_teaching_and_queue(
            session, gid, expected_revision=2, reviewed_by="teacher"
        )
        assert result2["status"] == "queued"


@pytest.mark.asyncio
async def test_two_workers_cannot_both_claim_queued(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session, status="queued")

    async def _claim(worker_id: str) -> ExecutionLease | None:
        async with db_session_factory() as session:
            return await claim_next_native_job(session, worker_id=worker_id, lease_seconds=90)

    first, second = await asyncio.gather(_claim("worker-a"), _claim("worker-b"))
    winners = [item for item in (first, second) if item is not None]
    losers = [item for item in (first, second) if item is None]
    assert len(winners) == 1
    assert len(losers) == 1
    assert winners[0].generation_id == gid
    assert winners[0].lease_token == 1

    async with db_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "planning_forms"
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        assert state["execution"]["worker_id"] in {"worker-a", "worker-b"}
        assert int(state["execution"]["lease_token"]) == 1


@pytest.mark.asyncio
async def test_stale_active_contention_one_winner(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session, status="writing_blocks")
        repo = PageDocumentRepository(session, gid)

        def _stale(_gen, state):
            state["execution"] = {
                "worker_id": "old-worker",
                "lease_token": 3,
                "attempt": 1,
                "claimed_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "heartbeat_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "lease_seconds": 90,
                "last_error": None,
            }
            state["lesson_packet"] = {"lesson": {"objective": "Learn X"}}
            state["teaching_plan"] = {"arc": "test", "sections": []}

        await repo.mutate_state(mutation=_stale)

    async def _claim(worker_id: str) -> ExecutionLease | None:
        async with db_session_factory() as session:
            return await claim_next_native_job(session, worker_id=worker_id, lease_seconds=90)

    first, second = await asyncio.gather(_claim("reclaimer-a"), _claim("reclaimer-b"))
    winners = [item for item in (first, second) if item is not None]
    assert len(winners) == 1
    assert winners[0].lease_token == 4
    assert winners[0].stage == "writing_blocks"


@pytest.mark.asyncio
async def test_fresh_heartbeat_prevents_reclaim(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session, status="writing_blocks")
        repo = PageDocumentRepository(session, gid)

        def _fresh(_gen, state):
            state["execution"] = {
                "worker_id": "owner",
                "lease_token": 2,
                "attempt": 1,
                "claimed_at": _now_iso(),
                "heartbeat_at": _now_iso(),
                "lease_seconds": 90,
                "last_error": None,
            }
            state["lesson_packet"] = {"lesson": {"objective": "Learn X"}}
            state["teaching_plan"] = {"arc": "test", "sections": []}

        await repo.mutate_state(mutation=_fresh)
        claimed = await claim_next_native_job(session, worker_id="intruder", lease_seconds=90)
        assert claimed is None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_stale_worker_write_rejected(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session, status="queued")
        lease_a = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="worker-a"
        )
        assert lease_a is not None
        assert lease_a.lease_token == 1

    async with db_session_factory() as session:
        # Expire heartbeat and reclaim.
        repo = PageDocumentRepository(session, gid)

        def _expire(_gen, state):
            execution = dict(state["execution"])
            execution["heartbeat_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=10)
            ).isoformat()
            state["execution"] = execution

        await repo.mutate_state(mutation=_expire)
        lease_b = await repo.claim_execution(worker_id="worker-b")
        assert lease_b is not None
        assert lease_b.lease_token == 2

        with pytest.raises(LeaseLostError):
            await repo.save_block_outcome(
                "orient:b1:everyone",
                {"status": "ready", "content": {"paragraphs": ["late"]}},
                worker_id="worker-a",
                lease_token=1,
            )
        await repo.save_block_outcome(
            "orient:b1:everyone",
            {"status": "ready", "content": {"paragraphs": ["ok"]}},
            worker_id="worker-b",
            lease_token=2,
        )
        stored = await repo.load_block_results()
        assert stored["orient:b1:everyone"]["content"]["paragraphs"] == ["ok"]


@pytest.mark.asyncio
async def test_wrong_token_heartbeat_rejected(db_session_factory) -> None:
    async with db_session_factory() as session:
        gid = await _seed_native_generation(session, status="queued")
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="owner"
        )
        assert lease is not None
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(LeaseLostError):
            await repo.heartbeat(worker_id="owner", lease_token=999)
        with pytest.raises(LeaseLostError):
            await repo.heartbeat(worker_id="other", lease_token=lease.lease_token)
        await repo.heartbeat(worker_id="owner", lease_token=lease.lease_token)
