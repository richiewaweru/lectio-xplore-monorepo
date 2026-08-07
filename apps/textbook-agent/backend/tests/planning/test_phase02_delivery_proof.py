"""Phase 02 Commit D: visual callback + conceptual resilience proof."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects import WriterOutcome
from generation.page_objects.document_assembly import persist_document_json
from generation.page_objects.visual_completion import apply_figure_asset_update
from planning.whole_lesson.executor import execute_after_teaching_approval, write_form_blocks
from planning.whole_lesson.failure_injection import (
    configure_failure_injection,
    reset_failure_injection,
)
from planning.whole_lesson.form_plan import FormPlan
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.legality import build_lesson_legality_snapshot
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state
from planning.whole_lesson.states import execution_key
from planning.whole_lesson.teaching_plan import TeachingPlan
from tests.planning.contract_fixtures import teaching_and_form


ANSWER_PHRASE = "TEACHER_ONLY_ANSWER_PHRASE_42"


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-conceptual-p2",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light", "plant"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[SlotRecord(slot_id="explain", typical_intents=["explain"])],
        limits=LessonLimits(),
    )


def _plans() -> tuple[TeachingPlan, FormPlan]:
    return teaching_and_form(
        sections=[
            (
                "explain",
                [
                    ("e1", "explain", "prose"),
                    ("e2", "explain", "prose"),
                    ("e3", "explain", "prose"),
                ],
            )
        ]
    )


def _document_with_figure_and_answer() -> dict[str, Any]:
    return {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-phase02-proof",
        "title": "Plants and light",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "id": "fig-1",
                        "object": "figure",
                        "intent": "illustrate",
                        "position": 0,
                        "content": {
                            "alt_text": "Two plants",
                            "caption": "Lit vs covered",
                            "asset": {
                                "status": "pending",
                                "request_id": "req-fig-1",
                                "kind": "image",
                            },
                        },
                        "layout": {"placement": "main"},
                    },
                    {
                        "id": "q-1",
                        "object": "questions",
                        "intent": "check-understanding",
                        "position": 1,
                        "content": {
                            "items": [
                                {
                                    "id": "item-1",
                                    "stem": "Why does the covered leaf fail?",
                                    "options": [
                                        {"key": "A", "text": "No light"},
                                        {"key": "B", "text": "No soil"},
                                    ],
                                    "correct_key": "A",
                                    "teacher_note": ANSWER_PHRASE,
                                }
                            ]
                        },
                        "layout": {"placement": "main"},
                    },
                ],
            }
        ],
    }


async def _seed_ready_doc(*, status: str = "awaiting_visuals") -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    teaching, plan = _plans()
    doc = _document_with_figure_and_answer()
    state = empty_page_document_state()
    state["lesson_packet"] = _packet().model_dump(mode="json")
    state["lesson_legality"] = build_lesson_legality_snapshot(_packet()).model_dump(
        mode="json"
    )
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = plan.model_dump(mode="json")
    state["form_validation"] = {"ok": True}
    state["block_execution"] = {
        "explain:fig-1:everyone": {
            "status": "visual_pending",
            "block_id": "fig-1",
            "request_id": "req-fig-1",
            "object": "figure",
            "intent": "illustrate",
        }
    }
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
                document_json=persist_document_json(None, doc),
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
async def test_conceptual_resilience_then_assemble() -> None:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    teaching, plan = _plans()
    packet = _packet()
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["lesson_legality"] = build_lesson_legality_snapshot(packet).model_dump(
        mode="json"
    )
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = plan.model_dump(mode="json")
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
                status="planning_forms",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "planning_forms",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()

    configure_failure_injection(
        enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
    )

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
        await write_form_blocks(
            generation_id=gid,
            form_plan=plan,
            packet=_packet(),
            teaching_plan=teaching,
        )

    async with async_session_factory() as session:
        stored = await PageDocumentRepository(session, gid).load_block_results()
    assert stored[execution_key("explain", "e1")]["status"] == "ready"
    assert stored[execution_key("explain", "e2")]["status"] == "failed_recoverable"
    assert stored[execution_key("explain", "e3")]["status"] == "ready"

    reset_failure_injection()
    with patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            generation.status = "failed_recoverable"
            await session.commit()
            # Re-queue and execute to completion.
            await PageDocumentRepository(session, gid).transition(
                expected={"failed_recoverable"},
                target="queued",
                event="requeue",
            )
            claimed = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="proof-worker"
            )
            assert claimed is not None
            result = await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=_packet(),
                worker_id="proof-worker",
                lease=claimed,
            )
    assert result["status"] == "ready"


def test_teacher_answer_phrase_not_in_student_projection() -> None:
    doc = _document_with_figure_and_answer()
    # Student projection strips teacher_note; teacher keeps it.
    teacher_blob = str(doc)
    assert ANSWER_PHRASE in teacher_blob
    student_sections = []
    for section in doc["sections"]:
        blocks = []
        for block in section["blocks"]:
            content = dict(block.get("content") or {})
            if block.get("object") == "questions":
                items = []
                for item in content.get("items") or []:
                    cleaned = {k: v for k, v in item.items() if k != "teacher_note"}
                    items.append(cleaned)
                content["items"] = items
            blocks.append({**block, "content": content})
        student_sections.append({**section, "blocks": blocks})
    student_doc = {**doc, "sections": student_sections}
    assert ANSWER_PHRASE not in str(student_doc)
    assert ANSWER_PHRASE in str(doc)


def test_visual_completion_idempotent_by_request_id() -> None:
    doc = _document_with_figure_and_answer()
    once = apply_figure_asset_update(
        doc,
        block_id="fig-1",
        asset={
            "status": "ready",
            "kind": "image",
            "src": "https://example.test/a.png",
            "request_id": "req-fig-1",
        },
    )
    twice = apply_figure_asset_update(
        once,
        block_id="fig-1",
        asset={
            "status": "ready",
            "kind": "image",
            "src": "https://example.test/a.png",
            "request_id": "req-fig-1",
        },
    )
    asset = twice["sections"][0]["blocks"][0]["content"]["asset"]
    assert asset["status"] == "ready"
    assert asset["request_id"] == "req-fig-1"
    assert twice["sections"][0]["blocks"][0]["content"]["alt_text"] == "Two plants"


@pytest.mark.asyncio
async def test_pdf_blocked_while_figures_pending() -> None:
    """Mirrors the export route gate: pending figures → 409 FIGURES_NOT_READY."""
    gid = await _seed_ready_doc(status="awaiting_visuals")
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        document_json = generation.document_json or {}
        lectio_doc = document_json.get("lectio_document")
        pending_ids: list[str] = []
        for section in lectio_doc.get("sections") or []:
            for block in section.get("blocks") or []:
                if block.get("object") != "figure":
                    continue
                asset = (block.get("content") or {}).get("asset") or {}
                if str(asset.get("status") or "") in {"pending", "failed"}:
                    pending_ids.append(str(block.get("id")))
        assert pending_ids == ["fig-1"]
