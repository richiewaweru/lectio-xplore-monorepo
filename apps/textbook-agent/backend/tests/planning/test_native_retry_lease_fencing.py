"""F01–F07: lease fencing for mid-LLM reclaim races on pre-worker retry."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from core.database.models import GenerationModel, PackItemModel
from core.database.session import async_session_factory
from planning.whole_lesson.native_retry import accept_native_retry, run_pre_worker_retry
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    empty_execution_meta,
)
from planning.whole_lesson.states import LeaseLostError
from tests.planning.test_native_retry_pre_worker import (
    TEST_USER,
    _seed_generation,
    _teaching_ok,
    _valid_result,
)
from v3_blueprint.planning.models import ItemOption, QuestionBrief
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state
from v3_execution.executors.item_diagnostics import attempt_record
from v3_execution.executors.item_executor import ItemGenerationResult, ItemGenerationRun


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


def _stem_result(card_id: str, stem_prefix: str) -> ItemGenerationResult:
    return ItemGenerationResult(
        card_id=card_id,
        items=[
            QuestionBrief(
                question_id=f"q{i}",
                prompt_text=f"{stem_prefix} {i}",
                options=[
                    ItemOption(key="A", text="correct", correct=True, diagnoses=None),
                    ItemOption(key="B", text="wrong", correct=False, diagnoses="m1"),
                    ItemOption(key="C", text="other", correct=False, diagnoses=None),
                    ItemOption(key="D", text="other2", correct=False, diagnoses=None),
                ],
                expected_answer="correct",
            )
            for i in range(1, 6)
        ],
    )


async def _count_pack_items(pack_id: str) -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(PackItemModel)
            .where(PackItemModel.pack_id == pack_id)
        )
        return int(result.scalar_one())


async def _pack_item_stems(pack_id: str) -> list[str]:
    async with async_session_factory() as session:
        rows = await session.execute(
            select(PackItemModel).where(PackItemModel.pack_id == pack_id)
        )
        return [str(row.stem or "") for row in rows.scalars()]


def _event_names(page: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for ev in page.get("events") or []:
        if not isinstance(ev, dict):
            continue
        names.add(str(ev.get("event") or ev.get("name") or ev.get("type") or ""))
    return names


@pytest.mark.asyncio
async def test_f01_stale_item_worker_cannot_persist_after_reclaim() -> None:
    gid, _card_id = await _seed_generation(
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
    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease1 = await repo.claim_pre_worker_retry(
            worker_id="f01-w1", lease_seconds=30
        )
    assert lease1 is not None
    token1 = lease1.lease_token

    entered = asyncio.Event()
    release = asyncio.Event()

    async def _blocked_items(card, **_k):
        entered.set()
        await release.wait()
        return ItemGenerationRun(
            result=_stem_result(card.id, "Stem from worker 1"),
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

    with patch(
        "v3_execution.executors.item_executor.execute_items_with_diagnostics",
        new=_blocked_items,
    ):
        task = asyncio.create_task(run_pre_worker_retry(lease=lease1))
        await asyncio.wait_for(entered.wait(), timeout=5)
        await _age_heartbeat(gid, seconds_ago=120)
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease2 = await repo.claim_pre_worker_retry(
                worker_id="f01-w2", lease_seconds=90
            )
        assert lease2 is not None
        assert lease2.lease_token > token1
        release.set()
        with pytest.raises(LeaseLostError):
            await task

    assert await _count_pack_items(gid) == 0
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "item_generation"
        chunked = dict(generation.chunked_state_json or {})
        page = dict(chunked.get("page_document_v2") or {})
        execution = dict(page.get("execution") or {})
        assert execution.get("worker_id") == "f01-w2"
        assert int(execution.get("lease_token") or 0) == lease2.lease_token
        attempts = list((chunked.get("item_generation") or {}).get("attempts") or [])
    assert not any(row.get("class") == "OK" for row in attempts if isinstance(row, dict))


@pytest.mark.asyncio
async def test_f02_stale_item_worker_cannot_overwrite_worker2_results() -> None:
    gid, _card_id = await _seed_generation(
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
    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease1 = await repo.claim_pre_worker_retry(
            worker_id="f02-w1", lease_seconds=30
        )
    assert lease1 is not None

    entered = asyncio.Event()
    release = asyncio.Event()

    async def _blocked_w1(card, **_k):
        entered.set()
        await release.wait()
        return ItemGenerationRun(
            result=_stem_result(card.id, "Stem from worker 1"),
            attempts=[
                attempt_record(
                    correlation_id=f"item:{gid}:{card.id}:w1",
                    card_id=card.id,
                    attempt=1,
                    started_at=0.0,
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=f"item:{gid}:{card.id}:w1",
        )

    async def _ok_w2(card, **_k):
        return ItemGenerationRun(
            result=_stem_result(card.id, "Stem from worker 2"),
            attempts=[
                attempt_record(
                    correlation_id=f"item:{gid}:{card.id}:w2",
                    card_id=card.id,
                    attempt=1,
                    started_at=0.0,
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=f"item:{gid}:{card.id}:w2",
        )

    with patch(
        "v3_execution.executors.item_executor.execute_items_with_diagnostics",
        new=_blocked_w1,
    ):
        task1 = asyncio.create_task(run_pre_worker_retry(lease=lease1))
        await asyncio.wait_for(entered.wait(), timeout=5)
        await _age_heartbeat(gid, seconds_ago=120)
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease2 = await repo.claim_pre_worker_retry(
                worker_id="f02-w2", lease_seconds=90
            )
        assert lease2 is not None

        with (
            patch(
                "v3_execution.executors.item_executor.execute_items_with_diagnostics",
                new=_ok_w2,
            ),
            patch(
                "planning.whole_lesson.service.run_and_persist_teaching_plan",
                new=_teaching_ok,
            ),
        ):
            result2 = await run_pre_worker_retry(lease=lease2)
        assert result2["status"] == "awaiting_teaching_approval"

        release.set()
        with pytest.raises(LeaseLostError):
            await task1

    stems = await _pack_item_stems(gid)
    assert stems
    assert all(s.startswith("Stem from worker 2") for s in stems)
    assert not any("worker 1" in s for s in stems)


@pytest.mark.asyncio
async def test_f03_stale_teaching_worker_cannot_persist_after_reclaim() -> None:
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
            worker_id="f03-w1", lease_seconds=30
        )
    assert lease1 is not None
    token1 = lease1.lease_token

    entered = asyncio.Event()
    release = asyncio.Event()

    class _FakePlan:
        arc = "worker-1-arc"

        def model_dump(self, mode="json"):
            return {"arc": self.arc, "sections": []}

    class _FakeValidation:
        def to_dict(self):
            return {"ok": True}

    class _FakeGuidance:
        catalogue_version = "1.0.0"
        projection_hash = "hash-w1"

    class _FakeResult:
        plan = _FakePlan()
        validation = _FakeValidation()
        qc: list = []
        prompt = "p"
        raw_response = "r"
        teaching_guidance = _FakeGuidance()

    async def _blocked_planner(*_a, **_k):
        entered.set()
        await release.wait()
        return _FakeResult()

    with patch(
        "planning.whole_lesson.service.run_lesson_approach_planner",
        new=_blocked_planner,
    ):
        task = asyncio.create_task(run_pre_worker_retry(lease=lease1))
        await asyncio.wait_for(entered.wait(), timeout=10)
        await _age_heartbeat(gid, seconds_ago=120)
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease2 = await repo.claim_pre_worker_retry(
                worker_id="f03-w2", lease_seconds=90
            )
        assert lease2 is not None
        assert lease2.lease_token > token1
        release.set()
        with pytest.raises(LeaseLostError):
            await task

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        plan = page.get("teaching_plan")
        assert plan in (None, {})
        names = _event_names(page)
        assert "teaching_plan_ready" not in names
        assert "awaiting_teaching_approval" not in names
        execution = dict(page.get("execution") or {})
        assert execution.get("worker_id") == "f03-w2"
        assert int(execution.get("lease_token") or 0) == lease2.lease_token


@pytest.mark.asyncio
async def test_f04_new_teaching_worker_wins_race() -> None:
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
            worker_id="f04-w1", lease_seconds=30
        )
    assert lease1 is not None

    entered = asyncio.Event()
    release = asyncio.Event()

    class _FakePlan:
        arc = "worker-1-arc"

        def model_dump(self, mode="json"):
            return {"arc": self.arc, "sections": []}

    class _FakeValidation:
        def to_dict(self):
            return {"ok": True}

    class _FakeGuidance:
        catalogue_version = "1.0.0"
        projection_hash = "hash-w1"

    class _FakeResult:
        plan = _FakePlan()
        validation = _FakeValidation()
        qc: list = []
        prompt = "p"
        raw_response = "r"
        teaching_guidance = _FakeGuidance()

    async def _blocked_planner(*_a, **_k):
        entered.set()
        await release.wait()
        return _FakeResult()

    class _FakePlan2(_FakePlan):
        arc = "worker-2-arc"

    class _FakeGuidance2(_FakeGuidance):
        projection_hash = "hash-w2"

    class _FakeResult2(_FakeResult):
        plan = _FakePlan2()
        teaching_guidance = _FakeGuidance2()

    async def _planner_w2(*_a, **_k):
        return _FakeResult2()

    with patch(
        "planning.whole_lesson.service.run_lesson_approach_planner",
        new=_blocked_planner,
    ):
        task1 = asyncio.create_task(run_pre_worker_retry(lease=lease1))
        await asyncio.wait_for(entered.wait(), timeout=10)
        await _age_heartbeat(gid, seconds_ago=120)
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease2 = await repo.claim_pre_worker_retry(
                worker_id="f04-w2", lease_seconds=90
            )
        assert lease2 is not None

        with patch(
            "planning.whole_lesson.service.run_lesson_approach_planner",
            new=_planner_w2,
        ):
            result2 = await run_pre_worker_retry(lease=lease2)
        assert result2["status"] == "awaiting_teaching_approval"

        release.set()
        with pytest.raises(LeaseLostError):
            await task1

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_teaching_approval"
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        plan = dict(page.get("teaching_plan") or {})
        assert plan.get("arc") == "worker-2-arc"
        catalogue = dict(page.get("catalogue") or {})
        assert catalogue.get("teaching_projection_hash") == "hash-w2"


@pytest.mark.asyncio
async def test_f05_stale_worker_cannot_append_success_events() -> None:
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
            worker_id="f05-w1", lease_seconds=30
        )
    assert lease1 is not None
    await _age_heartbeat(gid, seconds_ago=120)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease2 = await repo.claim_pre_worker_retry(
            worker_id="f05-w2", lease_seconds=90
        )
    assert lease2 is not None

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(LeaseLostError):
            await repo.append_event(
                {"event": "teaching_plan_ready", "status": "ready"},
                worker_id=lease1.worker_id,
                lease_token=lease1.lease_token,
            )
        with pytest.raises(LeaseLostError):
            await repo.append_event(
                {"event": "awaiting_teaching_approval", "status": "pending"},
                worker_id=lease1.worker_id,
                lease_token=lease1.lease_token,
            )
        with pytest.raises(LeaseLostError):
            await repo.append_event(
                {
                    "event": "native_retry_items_complete",
                    "status": "planning_teaching",
                },
                worker_id=lease1.worker_id,
                lease_token=lease1.lease_token,
            )


@pytest.mark.asyncio
async def test_f06_healthy_worker_path_still_works() -> None:
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
    await persist_chunked_state(
        gid,
        {
            "item_generation": {
                "attempts": [
                    attempt_record(
                        correlation_id=f"item:{gid}:{card_id}",
                        card_id=card_id,
                        attempt=1,
                        started_at=0.0,
                        outcome_class="TIMEOUT",
                        error="timed out",
                        retryable=True,
                    )
                ],
                "failed_cards": [
                    {
                        "card_id": card_id,
                        "correlation_id": f"item:{gid}:{card_id}",
                        "error": "timed out",
                    }
                ],
            }
        },
    )

    async def _ok_items(card, **_k):
        return ItemGenerationRun(
            result=_valid_result(card.id),
            attempts=[
                attempt_record(
                    correlation_id=f"item:{gid}:{card.id}",
                    card_id=card.id,
                    attempt=2,
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
        lease = await repo.claim_pre_worker_retry(
            worker_id="f06-worker", lease_seconds=90
        )
    assert lease is not None

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=_ok_items,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_teaching_ok,
        ),
    ):
        result = await run_pre_worker_retry(lease=lease)

    assert result["status"] == "awaiting_teaching_approval"
    assert await _count_pack_items(gid) == 5
    state = await load_chunked_state(gid)
    item_gen = dict(state.get("item_generation") or {})
    assert any(row.get("class") == "TIMEOUT" for row in item_gen.get("attempts") or [])
    assert any(row.get("class") == "OK" for row in item_gen.get("attempts") or [])
    assert len(item_gen.get("failed_cards") or []) >= 1


@pytest.mark.asyncio
async def test_f07_current_worker_failure_diagnostics_still_persist() -> None:
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
    await accept_native_retry(gid, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        lease = await repo.claim_pre_worker_retry(
            worker_id="f07-worker", lease_seconds=90
        )
    assert lease is not None

    async def _timeout_items(card, **_k):
        exc = TimeoutError("provider timed out")
        setattr(
            exc,
            "item_attempts",
            [
                attempt_record(
                    correlation_id=f"item:{gid}:{card.id}",
                    card_id=card.id,
                    attempt=1,
                    started_at=0.0,
                    outcome_class="TIMEOUT",
                    error="provider timed out",
                    retryable=True,
                )
            ],
        )
        setattr(exc, "item_correlation_id", f"item:{gid}:{card.id}")
        raise exc

    with patch(
        "v3_execution.executors.item_executor.execute_items_with_diagnostics",
        new=_timeout_items,
    ):
        with pytest.raises(TimeoutError):
            await run_pre_worker_retry(lease=lease)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        assert generation.error is not None
        assert generation.error_type is not None
        assert generation.error_code is not None
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        last_error = dict((page.get("execution") or {}).get("last_error") or {})
        assert last_error.get("stage") == "item_generation"
        item_gen = dict(
            (generation.chunked_state_json or {}).get("item_generation") or {}
        )
        assert any(
            row.get("class") == "TIMEOUT" for row in (item_gen.get("attempts") or [])
        )
        assert any(
            row.get("card_id") == card_id for row in (item_gen.get("failed_cards") or [])
        )
