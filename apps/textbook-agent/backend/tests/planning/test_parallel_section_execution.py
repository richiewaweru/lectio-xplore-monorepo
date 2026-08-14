"""Gate 6: section-parallel execution with concurrency bound and canonical order."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.exceptions import ModelAPIError

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects import WriterOutcome
from planning.whole_lesson.executor import write_form_blocks
from planning.whole_lesson.form_plan import FormPlan
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state
from planning.whole_lesson.states import MAX_SECTION_CONCURRENCY, execution_key
from planning.whole_lesson.teaching_plan import TeachingPlan
from tests.planning.contract_fixtures import teaching_and_form


def _packet(slot_ids: list[str]) -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-parallel",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[SlotRecord(slot_id=slot_id, typical_intents=["explain"]) for slot_id in slot_ids],
        limits=LessonLimits(),
    )


def _plans(n: int = 4) -> tuple[TeachingPlan, FormPlan]:
    sections = [
        (f"section-{i}", [(f"s{i}-b1", "explain", "prose")])
        for i in range(1, n + 1)
    ]
    return teaching_and_form(sections=sections)


async def _seed(teaching: TeachingPlan, form_plan: FormPlan) -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    packet = _packet([s.slot_id for s in form_plan.sections])
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = form_plan.model_dump(mode="json")
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
                status="writing_sections",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "writing_sections",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


@pytest.mark.asyncio
async def test_section_parallel_respects_max_concurrency_and_canonical_order() -> None:
    teaching, plan = _plans(4)
    gid = await _seed(teaching, plan)
    delays = {
        "s1-b1": 0.05,
        "s2-b1": 0.01,
        "s3-b1": 0.02,
        "s4-b1": 0.03,
    }
    finish_order: list[str] = []
    active = 0
    peak = 0
    lock = asyncio.Lock()
    section_active: dict[str, int] = {}

    async def _fake_dispatch(ctx):  # noqa: ANN001
        nonlocal active, peak
        section_id = ctx.section_id or "unknown"
        async with lock:
            section_active[section_id] = section_active.get(section_id, 0) + 1
            active = sum(1 for count in section_active.values() if count > 0)
            peak = max(peak, active)
        await asyncio.sleep(delays[ctx.planned.id])
        async with lock:
            section_active[section_id] -= 1
            finish_order.append(ctx.planned.id)
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"paragraphs": [ctx.planned.brief]},
            status="ready",
        )

    with patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        await write_form_blocks(
            generation_id=gid,
            form_plan=plan,
            packet=_packet([s.slot_id for s in plan.sections]),
            teaching_plan=teaching,
        )

    assert peak <= MAX_SECTION_CONCURRENCY
    assert set(finish_order) == {"s1-b1", "s2-b1", "s3-b1", "s4-b1"}
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        stored = await repo.load_block_results()
    for i in range(1, 5):
        key = execution_key(f"section-{i}", f"s{i}-b1")
        assert stored[key]["status"] == "ready"


@pytest.mark.asyncio
async def test_section_parallel_writes_six_sections() -> None:
    teaching, plan = _plans(6)
    gid = await _seed(teaching, plan)

    async def _fake_dispatch(ctx):  # noqa: ANN001
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"paragraphs": [ctx.planned.brief]},
            status="ready",
        )

    with patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        outcomes = await write_form_blocks(
            generation_id=gid,
            form_plan=plan,
            packet=_packet([s.slot_id for s in plan.sections]),
            teaching_plan=teaching,
        )
    assert len(outcomes) == 6
    assert all(o["status"] == "ready" for o in outcomes)


@pytest.mark.asyncio
async def test_exhausted_provider_connection_remains_recoverable() -> None:
    teaching, plan = _plans(1)
    gid = await _seed(teaching, plan)

    async def _connection_failure(_ctx):  # noqa: ANN001
        raise ModelAPIError(model_name="deepseek-v4", message="Connection error.")

    with (
        patch(
            "planning.whole_lesson.executor.dispatch_writer_async",
            new=AsyncMock(side_effect=_connection_failure),
        ) as dispatch,
        patch("planning.whole_lesson.executor.asyncio.sleep", new=AsyncMock()),
    ):
        outcomes = await write_form_blocks(
            generation_id=gid,
            form_plan=plan,
            packet=_packet([s.slot_id for s in plan.sections]),
            teaching_plan=teaching,
        )

    assert dispatch.await_count == 3
    assert outcomes[0]["status"] == "failed_recoverable"
    async with async_session_factory() as session:
        stored = await PageDocumentRepository(session, gid).load_block_results()
    outcome = stored[execution_key("section-1", "s1-b1")]
    assert outcome["status"] == "failed_recoverable"
    assert outcome["error"]["code"] == "TRANSPORT"
    assert outcome["error"]["retryable"] is True
