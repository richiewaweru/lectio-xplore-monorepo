from __future__ import annotations

import uuid
from typing import Any

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from infra.authoring import (
    AuthoringEngineError,
    AuthoringProviderCall,
    AuthoringTransportError,
)
from print.generation.whole_lesson.executor import assemble_from_db, write_form_blocks
from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from print.generation.whole_lesson.repository import (
    PageDocumentRepository,
    empty_page_document_state,
)
from print.generation.whole_lesson.states import execution_key
from print.generation.work_orders import build_print_work_order_from_planned_block
from print.rendering.page_objects import (
    ContentValidationError,
    WriterContext,
    WriterOutcome,
    dispatch_writer,
    dispatch_writer_async,
)
from tests.planning.contract_fixtures import teaching_and_form
from v3_blueprint.planning.models import PlannedBlock


class CapturingProvider:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        if not self.responses:
            raise AssertionError("provider called more often than scripted")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _planned(
    object_id: str,
    *,
    block_id: str | None = None,
    source_question_ids: list[str] | None = None,
) -> PlannedBlock:
    return PlannedBlock.model_validate(
        {
            "id": block_id or f"b-{object_id}",
            "position": 0,
            "intent": "explain",
            "object": object_id,
            "evidence": f"Evidence for {object_id}",
            "brief": f"Write the {object_id} block from package instructions.",
            "source_question_ids": source_question_ids or [],
        }
    )


def _ctx(object_id: str, *, response_ids: list[str] | None = None) -> WriterContext:
    planned = _planned(object_id, source_question_ids=response_ids)
    return WriterContext(
        planned=planned,
        use_llm=True,
        section_id="s-a03",
        generation_id="gen-a03",
        terminology=("photosynthesis", "light"),
        lesson_context={
            "objective": "Explain why plants need light.",
            "grade_level": "Grade 4",
            "subject": "Science",
            "allowed_facts": ["Plants use light energy to make food."],
        },
        print_work_order=build_print_work_order_from_planned_block(
            planned,
            section_id="s-a03",
            teaching_plan_id="tp-a03",
            teaching_plan_revision=7,
            teaching_plan_hash="teaching-hash-a03",
        ),
    )


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-a03",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["photosynthesis", "light"]),
        anchor=AnchorRecord(id="anchor-1", description="A plant by a window."),
        approved_items=[
            ApprovedItemRef(
                id="q-open-1",
                card_id="card-open",
                stem="Why does a covered leaf make less food?",
                correct_key="It receives less light.",
            ),
            ApprovedItemRef(
                id="q-mcq-1",
                card_id="card-mcq",
                stem="Which leaf can make the most food?",
                options=[
                    {"key": "A", "text": "A leaf in sunlight"},
                    {"key": "B", "text": "A covered leaf"},
                ],
                correct_key="A",
            ),
        ],
        slots=[SlotRecord(slot_id="s-a03", typical_intents=["explain"])],
        limits=LessonLimits(),
    )


@pytest.mark.asyncio
async def test_a03_g01_dispatch_writer_uses_package_instructions_and_schema() -> None:
    ctx = _ctx("prose")
    provider = CapturingProvider({"paragraphs": ["Light powers photosynthesis."]})

    result = await dispatch_writer_async(ctx, provider=provider)

    assert result.content == {"paragraphs": ["Light powers photosynthesis."]}
    assert provider.calls[0].work_order_id == ctx.print_work_order.work_order_id
    assert provider.calls[0].output_schema == ctx.print_work_order.expected_output_schema
    instruction_text = ctx.print_work_order.instructions["text"]
    assert instruction_text[:80] in provider.calls[0].prompt
    assert "You author one already-selected educational capability" in provider.calls[0].prompt


@pytest.mark.asyncio
async def test_a03_g02_table_failure_is_typed_and_never_returns_leaf_stub() -> None:
    invalid_table = {
        "columns": [{"id": "fraction", "label": "Fraction"}],
        "rows": [],
    }
    provider = CapturingProvider(invalid_table, invalid_table)

    with pytest.raises(ContentValidationError) as caught:
        await dispatch_writer_async(_ctx("table"), provider=provider)

    assert len(provider.calls) == 2
    assert "Lit leaf" not in str(caught.value)
    assert "Covered leaf" not in str(caught.value)


def test_a03_g03_approved_question_and_choice_conversion_is_exact() -> None:
    question_ctx = WriterContext(
        planned=_planned("questions", source_question_ids=["q-open-1"]),
        item_records=(
            {
                "id": "q-open-1",
                "stem": "Why does a covered leaf make less food?",
                "answer": "It receives less light.",
                "marks": 2,
                "answer_lines": 3,
            },
        ),
    )
    question_result = dispatch_writer(question_ctx)
    assert question_result.content["items"][0]["id"] == "q-open-1"
    assert "answer" not in question_result.content["items"][0]
    assert question_result.answer_entries == (
        {"question_id": "q-open-1", "answer": "It receives less light."},
    )

    choice_ctx = WriterContext(
        planned=_planned("choices", block_id="q-mcq-1", source_question_ids=["q-mcq-1"]),
        item_records=(
            {
                "id": "q-mcq-1",
                "stem": "Which leaf can make the most food?",
                "options": [
                    {"key": "A", "text": "A leaf in sunlight"},
                    {"key": "B", "text": "A covered leaf"},
                ],
                "correct_key": "A",
            },
        ),
    )
    choice_result = dispatch_writer(choice_ctx)
    assert choice_result.content["options"] == [
        {"letter": "A", "text": "A leaf in sunlight"},
        {"letter": "B", "text": "A covered leaf"},
    ]
    assert "correct_key" not in choice_result.content
    assert choice_result.answer_entries == ({"question_id": "q-mcq-1", "answer": "A"},)


@pytest.mark.asyncio
async def test_a03_g04_offline_print_forms_and_figure_lifecycle() -> None:
    cases = {
        "prose": {"paragraphs": ["Plants use light energy."]},
        "list": {"style": "unordered", "items": [{"text": "Light"}, {"text": "Leaves"}]},
        "table": {
            "columns": [{"id": "part", "label": "Part"}],
            "rows": [{"cells": {"part": "leaf"}}],
        },
        "aside": {"label": "Remember", "body": "Leaves make food."},
        "worked-example": {
            "problem": "A leaf is covered.",
            "steps": [{"text": "Compare light exposure."}],
            "answer": "The covered leaf makes less food.",
        },
        "figure": {
            "asset": {"kind": "image"},
            "alt_text": "Sunlight reaches a leaf.",
            "caption": "Light and leaves",
        },
    }
    for object_id, payload in cases.items():
        result = await dispatch_writer_async(_ctx(object_id), provider=CapturingProvider(payload))
        assert result.block_id == f"b-{object_id}"
        if object_id == "figure":
            assert result.status == "visual_pending"
            assert result.content["asset"]["status"] == "pending"
            assert result.content["asset"]["request_id"]
        else:
            assert result.status == "ready"

    with pytest.raises(AuthoringEngineError):
        await dispatch_writer_async(
            _ctx("figure"),
            provider=CapturingProvider(
                AuthoringTransportError("brief failed"),
                AuthoringTransportError("brief failed"),
            ),
        )


async def _seed_retry_case() -> tuple[str, Any, Any, ImmutableLessonPacket]:
    teaching, plan = teaching_and_form(
        sections=[
            (
                "s-a03",
                [
                    ("b-ready-1", "explain", "prose"),
                    ("b-retry", "explain", "prose"),
                    ("b-ready-2", "explain", "prose"),
                ],
            )
        ]
    )
    packet = _packet()
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = plan.model_dump(mode="json")
    state["form_validation"] = {"ok": True}
    state["block_execution"] = {
        execution_key("s-a03", "b-ready-1"): {
            "status": "ready",
            "block_id": "b-ready-1",
            "section_id": "s-a03",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "explain",
            "content": {"paragraphs": ["kept first sibling"]},
            "attempts": 1,
        },
        execution_key("s-a03", "b-retry"): {
            "status": "failed_recoverable",
            "block_id": "b-retry",
            "section_id": "s-a03",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "explain",
            "attempts": 1,
        },
        execution_key("s-a03", "b-ready-2"): {
            "status": "ready",
            "block_id": "b-ready-2",
            "section_id": "s-a03",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "explain",
            "content": {"paragraphs": ["kept second sibling"]},
            "attempts": 1,
        },
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
                status="writing_sections",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "writing_sections",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid, teaching, plan, packet


@pytest.mark.asyncio
async def test_a03_g05_retry_one_failed_block_preserves_siblings_and_order(monkeypatch) -> None:
    gid, teaching, plan, packet = await _seed_retry_case()
    written: list[str] = []

    async def fake_dispatch(ctx: WriterContext) -> WriterOutcome:
        assert ctx.print_work_order is not None
        assert ctx.print_work_order.block_id == "b-retry"
        assert len(ctx.print_work_order.capability_contract_hash) == 64
        written.append(ctx.planned.id)
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"paragraphs": ["rewritten retry block"]},
        )

    monkeypatch.setattr(
        "print.generation.whole_lesson.executor.dispatch_writer_async",
        fake_dispatch,
    )

    await write_form_blocks(
        generation_id=gid,
        form_plan=plan,
        packet=packet,
        teaching_plan=teaching,
    )

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        stored = await repo.load_block_results()
        lease = await repo.claim_execution(worker_id="a03-assembly")
        assert lease is not None
        await repo.transition(
            expected={"writing_sections"},
            target="assembling",
            event="document_assembling",
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
        )
        assembled = await assemble_from_db(
            session=session,
            generation_id=gid,
            packet=packet,
            form_plan=plan,
            teaching_plan=teaching,
            lease=lease,
        )

    assert written == ["b-retry"]
    assert stored[execution_key("s-a03", "b-ready-1")]["content"]["paragraphs"] == [
        "kept first sibling"
    ]
    assert stored[execution_key("s-a03", "b-ready-2")]["content"]["paragraphs"] == [
        "kept second sibling"
    ]
    paragraphs = [
        block["content"]["paragraphs"][0]
        for block in assembled["document"]["sections"][0]["blocks"]
    ]
    assert paragraphs == [
        "kept first sibling",
        "rewritten retry block",
        "kept second sibling",
    ]
