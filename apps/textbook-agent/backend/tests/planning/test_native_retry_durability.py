"""D01–D07 / H01–H03 / I01–I02: pre-worker retry durability proofs."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel
from core.database.session import async_session_factory
from core.entities.user import User
from planning.whole_lesson.native_retry import (
    accept_native_retry,
    run_pre_worker_retry,
)
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    claim_next_native_job,
    empty_execution_meta,
)
from planning.whole_lesson.states import (
    WORK_KIND_PRE_WORKER_TEACHING,
    LeaseLostError,
)
from planning.whole_lesson.worker import NativeExecutionWorker
from tests.planning.test_native_retry_pre_worker import (
    TEST_USER,
    _seed_generation,
    _teaching_ok,
    _valid_result,
)
from v3_blueprint.planning.persistence import (
    merge_failed_card_records,
    merge_item_generation_summary,
)
from v3_execution.executors.item_diagnostics import attempt_record
from v3_execution.executors.item_executor import ItemGenerationRun


async def _override_user() -> User:
    return TEST_USER


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _age_heartbeat(generation_id: str, *, seconds_ago: int = 120) -> None:
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)

        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["heartbeat_at"] = stamp
            execution["lease_seconds"] = 30
            state["execution"] = execution

        await repo.mutate_state(mutation=_mut)


@pytest.mark.asyncio
async def test_d01_http_202_while_teaching_blocked_then_worker_finishes() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    gate = asyncio.Event()
    calls = {"n": 0}

    async def _blocked_teaching(session, generation_id, **kwargs):
        calls["n"] += 1
        await gate.wait()
        return await _teaching_ok(session, generation_id, **kwargs)

    app.dependency_overrides[get_current_user] = _override_user
    try:
        with patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_blocked_teaching,
        ):
            async with _client() as client:
                resp = await client.post(f"/api/v1/v3/generations/{gid}/retry-native")
            assert resp.status_code == 202, resp.text
            body = resp.json()
            assert body["status"] == "planning_teaching"
            assert body["next_action"] == "wait"
            assert body["accepted"] is True

            async with async_session_factory() as session:
                generation = await session.get(GenerationModel, gid)
                assert generation is not None
                assert generation.status == "planning_teaching"

            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, gid)
                lease = await repo.claim_pre_worker_retry(
                    worker_id="d01-worker", lease_seconds=90
                )
            assert lease is not None
            task = asyncio.create_task(run_pre_worker_retry(lease=lease))
            await asyncio.sleep(0.05)
            assert calls["n"] == 1
            async with async_session_factory() as session:
                generation = await session.get(GenerationModel, gid)
                assert generation is not None
                assert generation.status == "planning_teaching"
            gate.set()
            result = await task
            assert result["status"] == "awaiting_teaching_approval"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_d02_client_drop_after_202_worker_still_completes() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    accepted = await accept_native_retry(gid, user_id=TEST_USER.id)
    assert accepted["accepted"] is True
    # Simulate dropped client: no further HTTP; worker alone finishes.
    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teaching_ok,
    ):
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease = await repo.claim_pre_worker_retry(
                worker_id="d02-worker", lease_seconds=90
            )
        result = await run_pre_worker_retry(lease=lease)
    assert result["status"] == "awaiting_teaching_approval"


@pytest.mark.asyncio
async def test_d03_stale_lease_reclaim_old_token_blocked() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease1 = await repo.claim_pre_worker_retry(
            worker_id="d03-w1", lease_seconds=30
        )
    assert lease1 is not None
    token1 = lease1.lease_token

    # Simulate process death without cleanup.
    await _age_heartbeat(gid, seconds_ago=120)

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease2 = await repo.claim_pre_worker_retry(
            worker_id="d03-w2", lease_seconds=90
        )
    assert lease2 is not None
    assert lease2.lease_token > token1
    assert lease2.worker_id == "d03-w2"

    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teaching_ok,
    ):
        result = await run_pre_worker_retry(lease=lease2)
    assert result["status"] == "awaiting_teaching_approval"

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(LeaseLostError):
            await repo.assert_lease(worker_id="d03-w1", lease_token=token1)


@pytest.mark.asyncio
async def test_d04_item_checkpoint_then_teaching_only_reclaim() -> None:
    gid, card_id = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "items timed out",
            "stage": "item_generation",
            "retryable": True,
        },
        skip_items=False,
        ready_card=False,
    )
    item_calls: list[str] = []

    async def _ok_items(card, **_k):
        item_calls.append(card.id)
        return ItemGenerationRun(
            result=_valid_result(card.id),
            attempts=[
                attempt_record(
                    correlation_id=f"item:{gid}:{card.id}",
                    card_id=card.id,
                    attempt=1,
                    started_at=0.0,
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=f"item:{gid}:{card.id}",
        )

    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease1 = await repo.claim_pre_worker_retry(
            worker_id="d04-w1", lease_seconds=30
        )
    assert lease1 is not None

    from planning.whole_lesson.native_retry import _run_items_under_lease

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=_ok_items,
        ),
        patch(
            "generation.v3_studio.router._persist_item_results",
            new=AsyncMock(),
        ),
    ):
        await _run_items_under_lease(gid, lease1)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "planning_teaching"
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        assert (page.get("execution") or {}).get("work_kind") == WORK_KIND_PRE_WORKER_TEACHING

    # Process death without cleanup; reclaim teaches only.
    await _age_heartbeat(gid, seconds_ago=120)
    teaching_calls = {"n": 0}

    async def _teach(session, generation_id, **kwargs):
        teaching_calls["n"] += 1
        return await _teaching_ok(session, generation_id, **kwargs)

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=AsyncMock(side_effect=AssertionError("items must not rerun")),
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_teach,
        ),
    ):
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease2 = await repo.claim_pre_worker_retry(
                worker_id="d04-w2", lease_seconds=90
            )
        assert lease2 is not None
        assert lease2.lease_token > lease1.lease_token
        result = await run_pre_worker_retry(lease=lease2)

    assert result["status"] == "awaiting_teaching_approval"
    assert item_calls == [card_id]
    assert teaching_calls["n"] == 1


@pytest.mark.asyncio
async def test_d05_concurrent_claim_single_winner() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    await accept_native_retry(gid, user_id=TEST_USER.id)

    async def _claim(worker_id: str):
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            return await repo.claim_pre_worker_retry(
                worker_id=worker_id, lease_seconds=90
            )

    lease_a, lease_b = await asyncio.gather(_claim("d05-a"), _claim("d05-b"))
    winners = [row for row in (lease_a, lease_b) if row is not None]
    assert len(winners) == 1

    teaching_calls = {"n": 0}

    async def _teach(session, generation_id, **kwargs):
        teaching_calls["n"] += 1
        return await _teaching_ok(session, generation_id, **kwargs)

    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teach,
    ):
        await run_pre_worker_retry(lease=winners[0])
    assert teaching_calls["n"] == 1


@pytest.mark.asyncio
async def test_d06_stale_worker_completion_lease_lost() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease_old = await repo.claim_pre_worker_retry(
            worker_id="d06-old", lease_seconds=30
        )
    assert lease_old is not None
    await _age_heartbeat(gid, seconds_ago=120)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease_new = await repo.claim_pre_worker_retry(
            worker_id="d06-new", lease_seconds=90
        )
    assert lease_new is not None
    assert lease_new.lease_token > lease_old.lease_token

    with pytest.raises(LeaseLostError):
        await run_pre_worker_retry(lease=lease_old)


@pytest.mark.asyncio
async def test_d07_worker_poll_discovers_abandoned_teaching() -> None:
    gid, _ = await _seed_generation(
        status="planning_teaching",
        last_error=None,
        skip_items=True,
        ready_card=True,
    )
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)

        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["work_kind"] = WORK_KIND_PRE_WORKER_TEACHING
            execution["pre_worker_retry_active"] = True
            execution["worker_id"] = None
            execution["heartbeat_at"] = (
                datetime.now(timezone.utc) - timedelta(seconds=120)
            ).isoformat()
            execution["lease_seconds"] = 30
            state["execution"] = execution

        await repo.mutate_state(mutation=_mut)

    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teaching_ok,
    ):
        worker = NativeExecutionWorker(
            worker_id="d07-poller",
            poll_seconds=0.05,
            lease_seconds=90,
            heartbeat_seconds=60,
        )
        await worker.start()
        try:
            for _ in range(40):
                async with async_session_factory() as session:
                    generation = await session.get(GenerationModel, gid)
                    if generation and generation.status == "awaiting_teaching_approval":
                        break
                await asyncio.sleep(0.05)
            else:
                pytest.fail("worker did not complete abandoned teaching retry")
        finally:
            await worker.stop(drain_seconds=2.0)


def test_h01_failed_cards_retained_on_success_summary() -> None:
    existing = {
        "attempts": [{"correlation_id": "c1", "card_id": "card-a", "attempt": 1}],
        "failed_cards": [
            {"card_id": "card-a", "correlation_id": "c1", "reason": "timeout"}
        ],
        "status": "partial",
    }
    summary = {
        "attempts": [{"correlation_id": "c1", "card_id": "card-a", "attempt": 2}],
        "failed_cards": [],
        "status": "ok",
        "pack_id": "p1",
    }
    merged = merge_item_generation_summary(existing, summary)
    assert merged["status"] == "ok"
    assert len(merged["failed_cards"]) == 1
    assert merged["failed_cards"][0]["reason"] == "timeout"
    assert len(merged["attempts"]) == 2


def test_h02_failed_cards_deduped_by_card_and_correlation() -> None:
    prior = [{"card_id": "a", "correlation_id": "x", "n": 1}]
    incoming = [
        {"card_id": "a", "correlation_id": "x", "n": 2},
        {"card_id": "a", "correlation_id": "y", "n": 3},
    ]
    merged = merge_failed_card_records(prior, incoming)
    assert len(merged) == 2
    assert merged[0]["n"] == 1
    assert merged[1]["correlation_id"] == "y"


def test_h03_multi_correlation_failed_cards_retained() -> None:
    existing = {
        "failed_cards": [
            {"card_id": "a", "correlation_id": "run-1"},
            {"card_id": "a", "correlation_id": "run-2"},
        ],
        "attempts": [],
    }
    summary = {
        "failed_cards": [{"card_id": "a", "correlation_id": "run-3"}],
        "attempts": [],
    }
    merged = merge_item_generation_summary(existing, summary)
    ids = {(row["card_id"], row["correlation_id"]) for row in merged["failed_cards"]}
    assert ids == {("a", "run-1"), ("a", "run-2"), ("a", "run-3")}


@pytest.mark.asyncio
async def test_i01_integrated_teaching_accept_crash_reclaim() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    accepted = await accept_native_retry(gid, user_id=TEST_USER.id)
    assert accepted["status"] == "planning_teaching"
    assert accepted["next_action"] == "wait"

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease1 = await repo.claim_pre_worker_retry(
            worker_id="i01-w1", lease_seconds=30
        )
    assert lease1 is not None

    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=AsyncMock(side_effect=TimeoutError("boom mid teaching")),
    ):
        with pytest.raises(TimeoutError):
            await run_pre_worker_retry(lease=lease1)

    # Re-accept after failure, then reclaim path via stale lease simulation on second accept.
    accepted2 = await accept_native_retry(gid, user_id=TEST_USER.id)
    assert accepted2["status"] == "planning_teaching"
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease2 = await repo.claim_pre_worker_retry(
            worker_id="i01-w2", lease_seconds=90
        )
    assert lease2 is not None
    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teaching_ok,
    ):
        result = await run_pre_worker_retry(lease=lease2)
    assert result["status"] == "awaiting_teaching_approval"


@pytest.mark.asyncio
async def test_i02_integrated_item_checkpoint_items_once() -> None:
    gid, card_id = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "items timed out",
            "stage": "item_generation",
            "retryable": True,
        },
        skip_items=False,
        ready_card=False,
    )
    item_calls: list[str] = []

    async def _ok_items(card, **_k):
        item_calls.append(card.id)
        return ItemGenerationRun(
            result=_valid_result(card.id),
            attempts=[
                attempt_record(
                    correlation_id=f"item:{gid}:{card.id}",
                    card_id=card.id,
                    attempt=1,
                    started_at=0.0,
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=f"item:{gid}:{card.id}",
        )

    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease1 = await repo.claim_pre_worker_retry(
            worker_id="i02-w1", lease_seconds=30
        )
    assert lease1 is not None

    from planning.whole_lesson.native_retry import _run_items_under_lease

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=_ok_items,
        ),
        patch(
            "generation.v3_studio.router._persist_item_results",
            new=AsyncMock(),
        ),
    ):
        await _run_items_under_lease(gid, lease1)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "planning_teaching"
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        assert (page.get("execution") or {}).get("work_kind") == WORK_KIND_PRE_WORKER_TEACHING

    await _age_heartbeat(gid, seconds_ago=120)
    async with async_session_factory() as session:
        lease2 = await claim_next_native_job(
            session, worker_id="i02-w2", lease_seconds=90
        )
    assert lease2 is not None
    assert lease2.generation_id == gid
    assert lease2.lease_token > lease1.lease_token

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=AsyncMock(side_effect=AssertionError("no item rerun")),
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_teaching_ok,
        ),
    ):
        result = await run_pre_worker_retry(lease=lease2)

    assert result["status"] == "awaiting_teaching_approval"
    assert item_calls == [card_id]
