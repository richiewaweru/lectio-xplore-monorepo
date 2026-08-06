"""Gate 6 resume: completed sections/blocks are skipped."""

from __future__ import annotations

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
from planning.whole_lesson.states import execution_key


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-resume",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="section-1", typical_intents=["orient"]),
            SlotRecord(slot_id="section-2", typical_intents=["explain"]),
            SlotRecord(slot_id="section-3", typical_intents=["check"]),
        ],
        limits=LessonLimits(),
    )


def _form_plan() -> FormPlan:
    return FormPlan(
        sections=[
            FormPlanSection(
                slot_id="section-1",
                title="One",
                blocks=[
                    FormPlanBlock(
                        id="s1-b1",
                        position=0,
                        intent="orient",
                        brief="ready",
                        object="prose",
                    )
                ],
            ),
            FormPlanSection(
                slot_id="section-2",
                title="Two",
                blocks=[
                    FormPlanBlock(
                        id="s2-b1",
                        position=0,
                        intent="explain",
                        brief="ready",
                        object="prose",
                    )
                ],
            ),
            FormPlanSection(
                slot_id="section-3",
                title="Three",
                blocks=[
                    FormPlanBlock(
                        id="s3-b1",
                        position=0,
                        intent="check",
                        brief="pending",
                        object="prose",
                    )
                ],
            ),
        ]
    )


async def _seed(block_execution: dict[str, Any]) -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    plan = _form_plan()
    state = empty_page_document_state()
    state["lesson_packet"] = _packet().model_dump(mode="json")
    state["form_plan"] = plan.model_dump(mode="json")
    state["form_validation"] = {"ok": True}
    state["block_execution"] = block_execution
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
async def test_resume_skips_completed_sections() -> None:
    plan = _form_plan()
    ready = {
        execution_key("section-1", "s1-b1"): {
            "status": "ready",
            "block_id": "s1-b1",
            "section_id": "section-1",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "orient",
            "content": {"paragraphs": ["kept section 1"]},
            "attempts": 1,
        },
        execution_key("section-2", "s2-b1"): {
            "status": "visual_pending",
            "block_id": "s2-b1",
            "section_id": "section-2",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "explain",
            "content": {"paragraphs": ["kept section 2"]},
            "attempts": 1,
        },
    }
    gid = await _seed(ready)
    written: list[str] = []

    async def _fake_dispatch(ctx):  # noqa: ANN001
        written.append(ctx.planned.id)
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
        await write_form_blocks(generation_id=gid, form_plan=plan, packet=_packet())

    assert written == ["s3-b1"]
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        stored = await repo.load_block_results()
    assert stored[execution_key("section-1", "s1-b1")]["content"]["paragraphs"] == [
        "kept section 1"
    ]
    assert stored[execution_key("section-2", "s2-b1")]["status"] == "visual_pending"
    assert stored[execution_key("section-3", "s3-b1")]["status"] == "ready"
