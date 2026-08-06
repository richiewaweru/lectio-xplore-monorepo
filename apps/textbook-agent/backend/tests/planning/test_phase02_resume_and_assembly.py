"""Phase 02 Commits B/C: writer isolation, resume, DB-first assembly."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects import WriterResult
from planning.whole_lesson.executor import (
    AssemblyError,
    assemble_from_db,
    execute_after_teaching_approval,
    write_form_blocks,
)
from planning.whole_lesson.failure_injection import (
    configure_failure_injection,
    reset_failure_injection,
)
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
            path_lesson_id="lesson-p2",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light", "plant"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain"]),
        ],
        limits=LessonLimits(),
    )


def _form_plan() -> FormPlan:
    return FormPlan(
        sections=[
            FormPlanSection(
                slot_id="orient",
                blocks=[
                    FormPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="orient",
                        brief="Open with the two plants.",
                        object="prose",
                    )
                ],
            ),
            FormPlanSection(
                slot_id="explain",
                blocks=[
                    FormPlanBlock(
                        id="explain-b1",
                        position=0,
                        intent="explain",
                        brief="Middle block that may fail.",
                        object="prose",
                    ),
                    FormPlanBlock(
                        id="explain-b2",
                        position=1,
                        intent="explain",
                        brief="Later sibling must still finish.",
                        object="prose",
                    ),
                ],
            ),
        ]
    )


async def _seed(
    *,
    status: str = "writing_blocks",
    form_plan: FormPlan | None = None,
    block_execution: dict[str, Any] | None = None,
) -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    packet = _packet()
    plan = form_plan or _form_plan()
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["teaching_plan"] = {"arc": "test", "sections": []}
    state["form_plan"] = plan.model_dump(mode="json")
    state["form_validation"] = {"ok": True}
    if block_execution:
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


@pytest.fixture(autouse=True)
def _reset_injection():
    reset_failure_injection()
    yield
    reset_failure_injection()


@pytest.mark.asyncio
async def test_composite_execution_keys_and_skip_ready() -> None:
    plan = _form_plan()
    key0 = execution_key("orient", "orient-b1", "everyone")
    key1 = execution_key("explain", "explain-b1", "everyone")
    key2 = execution_key("explain", "explain-b2", "everyone")
    assert key0 == "orient:orient-b1:everyone"
    ready = {
        key0: {
            "status": "ready",
            "block_id": "orient-b1",
            "section_id": "orient",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "orient",
            "content": {"paragraphs": ["already ready"]},
            "attempts": 1,
        }
    }
    gid = await _seed(block_execution=ready)
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
        await write_form_blocks(
            generation_id=gid, form_plan=plan, packet=_packet()
        )

    assert "orient-b1" not in written
    assert set(written) == {"explain-b1", "explain-b2"}
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        stored = await repo.load_block_results()
    assert stored[key0]["status"] == "ready"
    assert stored[key0]["content"]["paragraphs"] == ["already ready"]
    assert stored[key1]["status"] == "ready"
    assert stored[key2]["status"] == "ready"


@pytest.mark.asyncio
async def test_middle_block_failure_does_not_stop_siblings() -> None:
    plan = _form_plan()
    gid = await _seed()
    configure_failure_injection(
        enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
    )

    async def _fake_dispatch(ctx):  # noqa: ANN001
        return WriterResult(
            block_id=ctx.planned.id,
            object=ctx.planned.object,
            intent=ctx.planned.intent,
            content={"paragraphs": [f"ok {ctx.planned.id}"]},
            status="ready",
        )

    with patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        await write_form_blocks(
            generation_id=gid, form_plan=plan, packet=_packet()
        )

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        stored = await repo.load_block_results()
    assert stored["orient:orient-b1:everyone"]["status"] == "ready"
    assert stored["explain:explain-b1:everyone"]["status"] == "failed_recoverable"
    assert stored["explain:explain-b2:everyone"]["status"] == "ready"


@pytest.mark.asyncio
async def test_form_plan_reused_when_persisted() -> None:
    gid = await _seed(status="planning_forms")
    form_calls = {"n": 0}

    async def _boom(*_a, **_k):  # noqa: ANN001
        form_calls["n"] += 1
        raise AssertionError("form planner must not run when plan is persisted")

    async def _fake_dispatch(ctx):  # noqa: ANN001
        return WriterResult(
            block_id=ctx.planned.id,
            object=ctx.planned.object,
            intent=ctx.planned.intent,
            content={"paragraphs": [ctx.planned.brief]},
            status="ready",
        )

    with (
        patch("planning.whole_lesson.executor.run_form_planner", new=_boom),
        patch(
            "planning.whole_lesson.executor.dispatch_writer_async",
            new=AsyncMock(side_effect=_fake_dispatch),
        ),
    ):
        async with async_session_factory() as session:
            result = await execute_after_teaching_approval(
                session=session, generation_id=gid, packet=_packet()
            )
    assert form_calls["n"] == 0
    assert result["status"] in {"ready", "awaiting_visuals"}


@pytest.mark.asyncio
async def test_assemble_from_db_rejects_missing_and_completes_when_ready() -> None:
    plan = _form_plan()
    gid = await _seed(status="assembling")
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(AssemblyError, match="missing"):
            await assemble_from_db(
                session=session,
                generation_id=gid,
                packet=_packet(),
                form_plan=plan,
            )

    for section in plan.sections:
        for block in section.blocks:
            key = execution_key(section.slot_id, block.id)
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, gid)
                await repo.save_block_outcome(
                    key,
                    {
                        "status": "ready",
                        "block_id": block.id,
                        "section_id": section.slot_id,
                        "variant_id": "everyone",
                        "object": block.object,
                        "intent": block.intent,
                        "content": {"paragraphs": [block.brief]},
                        "attempts": 1,
                    },
                )

    async with async_session_factory() as session:
        # generation may still be assembling from earlier failure path
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        generation.status = "assembling"
        await session.commit()
        assembled = await assemble_from_db(
            session=session,
            generation_id=gid,
            packet=_packet(),
            form_plan=plan,
        )
        assert assembled["terminal"] == "ready"
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "ready"
        assert isinstance(generation.document_json, dict)
        assert generation.document_json.get("lectio_document")
        assert assembled.get("document_sha256")
        assert assembled["document_sha256"] == assembled["reloaded_sha256"]


@pytest.mark.asyncio
async def test_assemble_rejects_unknown_keys() -> None:
    plan = _form_plan()
    gid = await _seed(status="assembling")
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        for section in plan.sections:
            for block in section.blocks:
                key = execution_key(section.slot_id, block.id)
                await repo.save_block_outcome(
                    key,
                    {
                        "status": "ready",
                        "block_id": block.id,
                        "object": block.object,
                        "intent": block.intent,
                        "content": {"paragraphs": [block.brief]},
                    },
                )
        await repo.save_block_outcome(
            "ghost:ghost-1:everyone",
            {
                "status": "ready",
                "block_id": "ghost-1",
                "object": "prose",
                "intent": "explain",
                "content": {"paragraphs": ["extra"]},
            },
        )
        with pytest.raises(AssemblyError, match="unknown"):
            await assemble_from_db(
                session=session,
                generation_id=gid,
                packet=_packet(),
                form_plan=plan,
            )


@pytest.mark.asyncio
async def test_started_current_token_not_duplicated() -> None:
    plan = _form_plan()
    gid = await _seed(status="writing_blocks")
    key = execution_key("orient", "orient-b1")
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)

        def _lease(_gen, state):
            state["execution"]["worker_id"] = "w"
            state["execution"]["lease_token"] = 5
            state["block_execution"][key] = {
                "status": "started",
                "lease_token": 5,
                "attempts": 1,
                "block_id": "orient-b1",
            }

        await repo.mutate_state(mutation=_lease)

    written: list[str] = []

    async def _fake_dispatch(ctx):  # noqa: ANN001
        written.append(ctx.planned.id)
        return WriterResult(
            block_id=ctx.planned.id,
            object=ctx.planned.object,
            intent=ctx.planned.intent,
            content={"paragraphs": ["x"]},
            status="ready",
        )

    from planning.whole_lesson.states import ExecutionLease

    lease = ExecutionLease(
        generation_id=gid, worker_id="w", lease_token=5, stage="writing_blocks"
    )
    with patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        await write_form_blocks(
            generation_id=gid, form_plan=plan, packet=_packet(), lease=lease
        )
    assert "orient-b1" not in written
    async with async_session_factory() as session:
        stored = await PageDocumentRepository(session, gid).load_block_results()
    assert stored[key]["attempts"] == 1
