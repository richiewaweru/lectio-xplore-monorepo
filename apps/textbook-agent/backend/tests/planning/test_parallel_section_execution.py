"""Gate 6: section-parallel execution with concurrency bound and canonical order."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects import WriterResult
from planning.whole_lesson.executor import write_form_blocks
from planning.whole_lesson.form_plan import FormPlan, FormPlanBlock, FormPlanSection
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


def _form_plan(n: int = 4) -> FormPlan:
    sections = []
    for i in range(1, n + 1):
        sections.append(
            FormPlanSection(
                slot_id=f"section-{i}",
                title=f"Section {i}",
                blocks=[
                    FormPlanBlock(
                        id=f"s{i}-b1",
                        position=0,
                        intent="explain",
                        brief=f"Block for section {i}",
                        object="prose",
                    )
                ],
            )
        )
    return FormPlan(sections=sections)


async def _seed(form_plan: FormPlan) -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    packet = _packet([s.slot_id for s in form_plan.sections])
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
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
    plan = _form_plan(4)
    gid = await _seed(plan)
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
            # Count distinct sections currently writing
            active = sum(1 for count in section_active.values() if count > 0)
            peak = max(peak, active)
        await asyncio.sleep(delays[ctx.planned.id])
        finish_order.append(ctx.planned.id)
        async with lock:
            section_active[section_id] -= 1
            active = sum(1 for count in section_active.values() if count > 0)
        return WriterResult(
            block_id=ctx.planned.id,
            object=ctx.planned.object,
            intent=ctx.planned.intent,
            content={"paragraphs": [f"wrote {ctx.planned.id}"]},
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
        )

    assert peak <= MAX_SECTION_CONCURRENCY
    assert set(finish_order) == {"s1-b1", "s2-b1", "s3-b1", "s4-b1"}
    # Faster sections may finish first (out-of-order completion).
    assert finish_order[0] == "s2-b1"

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        stored = await repo.load_block_results()

    # Canonical form-plan order preserved in stored keys / section sequence.
    ordered_keys = [
        execution_key(section.slot_id, block.id)
        for section in plan.sections
        for block in section.blocks
    ]
    assert ordered_keys == [
        "section-1:s1-b1:everyone",
        "section-2:s2-b1:everyone",
        "section-3:s3-b1:everyone",
        "section-4:s4-b1:everyone",
    ]
    for key in ordered_keys:
        assert stored[key]["status"] == "ready"


@pytest.mark.asyncio
async def test_section_concurrency_never_exceeds_four_with_six_sections() -> None:
    plan = _form_plan(6)
    gid = await _seed(plan)
    peak = 0
    active = 0
    lock = asyncio.Lock()

    async def _fake_dispatch(ctx):  # noqa: ANN001
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.03)
        async with lock:
            active -= 1
        return WriterResult(
            block_id=ctx.planned.id,
            object=ctx.planned.object,
            intent=ctx.planned.intent,
            content={"paragraphs": ["ok"]},
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
        )

    assert peak <= MAX_SECTION_CONCURRENCY
