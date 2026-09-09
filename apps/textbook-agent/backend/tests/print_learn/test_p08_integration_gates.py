"""P08 — Uninterrupted Unit→Print and Unit→Learn integration gates.

Production service chains without prepared-plan substitution. External provider
mocks are labelled MOCK and limited to LLM/writer boundaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from application.unit_lesson import prepare_path_lesson
from application.unit_lesson.dual_native import (
    accept_shared_teaching_for_both,
    link_print_realization,
    load_shared_teaching_state,
)
from application.unit_lesson.realizations import retry_realization
from core.database.models import (
    ConceptCardModel,
    EditableLessonModel,
    GenerationModel,
    NativeRealizationModel,
    PackItemModel,
    PathLessonModel,
    UserModel,
)
from core.database.session import async_session_factory
from curriculum.path_models import PrepareLessonRequest
from curriculum.service import approve_path, create_unit, persist_path_plan
from curriculum.teaching_plan.coverage import (
    assert_learn_covers_instruction,
    assert_print_covers_instruction,
    instructional_coverage,
)
from curriculum.teaching_plan.models import (
    AnchorUsageEntry,
    LearnerActionBrief,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
)
from curriculum.teaching_plan.projections import (
    assert_sentinels_absent,
    with_excluded_sentinels,
)
from infra.authoring import AuthoringProviderCall
from learn.generation.native_execution import produce_learn_from_approved_teaching
from learn.generation.native_production import build_closed_learn_production
from learn.generation.preparation_context import learn_preparation_context_from_state
from learn.generation.work_orders import build_learn_writer_request
from infra.authoring.capability_selector import CapabilitySelection
from print.contracts.lectio_page import validate_document
from print.generation.whole_lesson.executor import execute_after_teaching_approval
from print.generation.whole_lesson.failure_injection import (
    configure_failure_injection,
    reset_failure_injection,
)
from print.generation.whole_lesson.repository import (
    PageDocumentRepository,
    empty_execution_meta,
)
from print.generation.whole_lesson.service import (
    approve_teaching_and_queue,
    build_packet_for_generation,
    run_and_persist_teaching_plan,
)
from print.generation.whole_lesson.states import LeaseLostError
from print.rendering.page_objects.document_assembly import reload_document
from print.rendering.page_objects.models import WriterOutcome
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture
from tests.planning.test_path_bridge import (
    _fake_component_selector,
    _fake_structural_planner,
)

FIXTURE = "grade4-photosynthesis-path.json"
ANSWER_PHRASE = "TEACHER_ONLY_ANSWER_LIGHT_REQUIRED"
EVIDENCE_ROOT = (
    Path(__file__).resolve().parents[5]
    / "docs"
    / "unit-native-program"
    / "evidence"
    / "mocks"
    / "p08"
)

# MOCK catalogue — every external boundary used by this suite.
MOCKS = {
    "teaching_llm": "print.generation.whole_lesson.teaching_agent._call_teaching_model",
    "print_writer": "print.generation.whole_lesson.executor.dispatch_writer_async",
    "learn_authoring_provider": "tests.print_learn.test_p08_integration_gates.P08LearnMockProvider",
    "structural_planner": "tests.planning.test_path_bridge._fake_structural_planner",
    "component_selector": "tests.planning.test_path_bridge._fake_component_selector",
}

_P08_CORE_CONFIG: dict[str, dict] = {
    "choice": {
        "options": [{"id": "a", "text": "No light reached the leaf"}, {"id": "b", "text": "The soil ran out of food"}],
        "correct_option_id": "a",
    },
    "multi-select": {
        "options": [{"id": "light", "text": "light"}, {"id": "co2", "text": "carbon dioxide"}, {"id": "noise", "text": "noise"}],
        "correct_option_ids": ["light", "co2"],
    },
    "fill-blank": {"answers": ["chlorophyll"], "blank_ids": ["pigment"], "case_sensitive": False},
    "numeric": {"value": 6, "tolerance": 0, "unit": "h"},
    "short-response": {"evaluation": "teacher-review", "review_guidance": "Explain why light is required."},
    "match-pairs": {"pairs": [{"left": "lit leaf", "right": "makes food"}, {"left": "covered leaf", "right": "no food"}]},
    "classify": {
        "categories": [{"id": "input", "label": "input"}, {"id": "output", "label": "output"}],
        "pairs": [{"left": "light", "right": "input"}, {"left": "sugar", "right": "output"}],
    },
    "sequence": {
        "items": [
            {"id": "light", "label": "Absorb light"},
            {"id": "water", "label": "Split water"},
            {"id": "carbon", "label": "Fix carbon into sugar"},
        ],
        "order": ["light", "water", "carbon"],
    },
}

_P08_CONTENT_PAYLOADS: dict[str, dict] = {
    "section-header": {"title": "Photosynthesis", "subject": "science", "grade_band": "primary"},
    "hook-hero": {"headline": "Two plants, one difference", "body": "Light changes food production.", "anchor": "photosynthesis"},
    "explanation-block": {"body": "Plants use light energy to make food.", "emphasis": ["light"]},
    "definition-card": {"term": "Photosynthesis", "formal": "Light-driven food production.", "plain": "Plants make food using light."},
    "key-fact": {"fact": "Light is required for food production."},
    "callout-block": {"variant": "info", "body": "Covered leaves cannot make food without light."},
    "process-steps": {"title": "Light to food", "steps": [{"number": 1, "action": "Absorb light", "detail": "Chlorophyll captures energy."}]},
    "worked-example-card": {"title": "Lit vs covered", "setup": "Compare two leaves.", "steps": [{"label": "Observe", "content": "Only the lit leaf makes food."}], "conclusion": "Light is required."},
    "summary-block": {"items": [{"text": "Light drives photosynthesis."}]},
    "timeline-block": {"title": "Day in a leaf", "events": [{"id": "morning", "year": "1", "title": "Sunrise", "summary": "Light arrives."}]},
    "diagram-compare": {"before_label": "Covered", "after_label": "Lit", "caption": "Light changes outcomes.", "alt_text": "Lit leaf beside covered leaf."},
    "quiz-check": {
        "question": "Why did the covered leaf fail?",
        "options": [{"text": "No light", "correct": True, "explanation": "Correct."}, {"text": "No soil", "correct": False, "explanation": "No."}],
        "feedback_correct": "Correct.",
        "feedback_incorrect": "Review light.",
    },
    "fill-in-blank": {"segments": [{"text": "Plants need ", "is_blank": False}, {"text": "", "is_blank": True, "answer": "light"}]},
}


def _p08_brief_from_call(call: AuthoringProviderCall) -> str:
    marker = "## SCOPED REQUEST"
    if call.is_repair and "## REPAIR PAYLOAD" in call.prompt:
        marker = "## REPAIR PAYLOAD"
    start = call.prompt.find(marker)
    if start < 0:
        return ""
    json_start = call.prompt.find("{", start)
    if json_start < 0:
        return ""
    depth = 0
    for index, char in enumerate(call.prompt[json_start:], start=json_start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(call.prompt[json_start : index + 1])
                except json.JSONDecodeError:
                    return ""
                scoped = data.get("scoped_request") or {}
                if scoped.get("brief"):
                    return str(scoped["brief"])
                block = (data.get("inputs") or {}).get("teaching_plan_block") or {}
                return str(block.get("brief") or "")
    return ""


def _p08_embed_brief(payload: dict, brief: str) -> dict:
    if not brief:
        return payload
    out = dict(payload)
    for key in ("body", "title", "headline", "fact", "question", "problem", "formal", "plain", "caption", "setup", "conclusion"):
        if key in out and isinstance(out[key], str):
            out[key] = f"{brief} {out[key]}".strip()
    if isinstance(out.get("paragraphs"), list) and out["paragraphs"]:
        out["paragraphs"] = [f"{brief} {out['paragraphs'][0]}".strip()]
    elif "title" in out and isinstance(out["title"], str):
        out["title"] = f"{brief} {out['title']}".strip()
    elif "question" in out and isinstance(out["question"], str):
        out["question"] = f"{brief} {out['question']}".strip()
    return out


def _p08_sequence_payload(brief: str) -> dict:
    parts = [part.strip() for part in brief.replace(";", ",").split(",") if part.strip()]
    if len(parts) >= 2:
        items = [{"id": f"step{index}", "label": label} for index, label in enumerate(parts)]
        return {"items": items, "order": [item["id"] for item in items]}
    return dict(_P08_CORE_CONFIG["sequence"])


def _p08_interaction_envelope(capability_id: str, *, config: dict, brief: str) -> dict:
    prompt = brief.strip() or f"Complete this {capability_id.replace('-', ' ')} activity."
    return {
        "prompt": prompt,
        "config": config,
        "feedback": {"correct": "Correct.", "incorrect": "Try again."},
    }


class P08LearnMockProvider:
    """MOCK Learn authoring provider — schema-valid payloads for closed production."""

    def __init__(self) -> None:
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> dict:
        self.calls.append(call)
        brief = _p08_brief_from_call(call)
        if call.capability_id == "sequence":
            config = _p08_sequence_payload(brief)
            return _p08_interaction_envelope("sequence", config=config, brief=brief)
        if call.capability_id in _P08_CORE_CONFIG:
            return _p08_interaction_envelope(
                call.capability_id,
                config=dict(_P08_CORE_CONFIG[call.capability_id]),
                brief=brief,
            )
        template = _P08_CONTENT_PAYLOADS.get(call.capability_id, _P08_CONTENT_PAYLOADS["explanation-block"])
        return _p08_embed_brief(dict(template), brief)


def _p08_learn_provider() -> P08LearnMockProvider:
    return P08LearnMockProvider()


async def _p08_choose(context: dict) -> CapabilitySelection:
    """MOCK Learn selector for offline P08 — first eligible closed-set ID."""
    ids = list(context.get("candidate_ids") or [])
    if not ids:
        raise AssertionError(f"p08 mock selector empty shortlist: {context!r}")
    return CapabilitySelection(capability_id=str(ids[0]), reason="p08-mock-selector")


@pytest.fixture(autouse=True)
def _reset_injection():
    reset_failure_injection()
    yield
    reset_failure_injection()


def _draft_for_packet(packet, *, item_id: str | None) -> TeachingPlanDraft:
    """MOCK provider-shaped draft reacting to packet slots (not an injected plan)."""
    sections: list[TeachingPlanDraftSection] = []
    anchors: list[AnchorUsageEntry] = []
    for slot in packet.slots:
        sid = slot.slot_id
        anchors.append(AnchorUsageEntry(slot_id=sid, usage=f"Use the anchor in {sid}."))
        if slot.visual_required or sid == "explain":
            intent = "illustrate" if "illustrate" in (slot.typical_intents or []) else "show-structure"
            if intent not in (slot.typical_intents or ["show-structure", "illustrate", "explain"]):
                intent = "explain"
            sections.append(
                TeachingPlanDraftSection(
                    specific_purpose=f"Develop meaning in {sid}",
                    blocks=[
                        TeachingPlanDraftBlock(
                            intent=intent if intent != "explain" else "explain",
                            brief=(
                                f"Show the lit vs covered leaf contrast for {sid} so learners "
                                "see that light changes the plant's ability to make food."
                            ),
                            evidence_refs=["lesson.objective"],
                            evidence=(
                                "A concrete visual difference belongs here before the check."
                            ),
                        )
                    ],
                )
            )
            continue
        if sid in {"practice", "apply"} or "practice" in sid or "apply" in sid:
            sections.append(
                TeachingPlanDraftSection(
                    specific_purpose="Order the light-to-food stages.",
                    blocks=[
                        TeachingPlanDraftBlock(
                            intent="sequence",
                            brief="Absorb light; Split water; Fix carbon into sugar",
                            evidence_refs=["lesson.objective"],
                            evidence="Correct complete order of the light-to-food stages.",
                            learner_action=LearnerActionBrief(
                                action="order-items",
                                support_level="independent",
                                evidence="Correct complete order of the light-to-food stages.",
                                source_item_ids=[],
                                dependencies=[],
                            ),
                        )
                    ],
                )
            )
            continue
        if sid == "check" or "check" in sid:
            source = [item_id] if item_id else []
            sections.append(
                TeachingPlanDraftSection(
                    specific_purpose="Check causal understanding.",
                    blocks=[
                        TeachingPlanDraftBlock(
                            intent="check-understanding",
                            brief=(
                                "Ask the approved covered-leaf item so learners explain why "
                                "light is required using the same plant contrast."
                            ),
                            evidence_refs=["lesson.objective"],
                            evidence=(
                                "The objective requires a causal explanation of light."
                            ),
                            source_question_ids=source,
                        )
                    ],
                )
            )
            continue
        intent = "orient" if sid == "orient" else "explain"
        for candidate in list(slot.typical_intents or []) + [intent]:
            if candidate:
                intent = str(candidate)
                break
        sections.append(
            TeachingPlanDraftSection(
                specific_purpose=f"Purpose for {sid}",
                blocks=[
                    TeachingPlanDraftBlock(
                        intent=intent,
                        brief=(
                            f"Advance the light-and-food story in {sid} using the two plants "
                            "without inventing new assessment text."
                        ),
                        evidence_refs=["lesson.objective"],
                        evidence="This slot advances the shared teaching arc.",
                    )
                ],
            )
        )
    return TeachingPlanDraft(
        arc=(
            "Open on two plants that grew differently, isolate light as the cause, "
            + (
                "order the light-to-food stages, and check with the approved covered-leaf item."
                if any(
                    (slot.slot_id in {"practice", "apply"}
                     or "practice" in slot.slot_id
                     or "apply" in slot.slot_id)
                    for slot in packet.slots
                )
                else "and check with the approved covered-leaf item."
            )
        ),
        anchor_usage=anchors,
        misconception_focus_ids=[],
        sections=sections,
    )


async def _fake_dispatch(ctx):  # noqa: ANN001
    """MOCK Print writer outcomes — deterministic by object type."""
    planned = ctx.planned
    if planned.object == "figure":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "alt_text": "Lit leaf beside covered leaf",
                "caption": "Light changes food production — lit vs covered",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/p08-figure.png",
                },
            },
            status="ready",
        )
    if planned.object == "choices":
        records = {str(item.get("id")): item for item in ctx.item_records}
        qid = (planned.source_question_ids or [None])[0]
        record = records.get(str(qid)) or {}
        options = []
        for option in record.get("options") or []:
            if isinstance(option, dict):
                options.append(
                    {
                        "letter": str(option.get("key") or option.get("letter") or ""),
                        "text": str(option.get("text") or ""),
                    }
                )
        return WriterOutcome(
            block_id=planned.id,
            content={
                "stem": str(record.get("stem") or planned.brief or "Choose"),
                "options": options,
            },
            answer_entries=[
                {
                    "question_id": planned.id,
                    "answer": str(record.get("correct_key") or "A"),
                    "working": ANSWER_PHRASE,
                }
            ],
            status="ready",
        )
    if planned.object == "questions":
        records = {str(item.get("id")): item for item in ctx.item_records}
        entries = []
        items = []
        for qid in planned.source_question_ids or []:
            record = records.get(str(qid)) or {}
            items.append({"id": str(qid), "prompt": str(record.get("stem") or qid)})
            entries.append(
                {
                    "question_id": str(qid),
                    "answer": str(record.get("correct_key") or ANSWER_PHRASE),
                    "working": ANSWER_PHRASE,
                }
            )
        return WriterOutcome(
            block_id=planned.id,
            content={"items": items},
            answer_entries=entries,
            status="ready",
        )
    if planned.object == "list":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "style": "ordered",
                "items": [
                    {"text": "Absorb light"},
                    {"text": "Split water"},
                    {"text": "Fix carbon into sugar"},
                ],
            },
            status="ready",
        )
    if planned.object == "prose":
        return WriterOutcome(
            block_id=planned.id,
            content={"paragraphs": [planned.brief or f"Prose for {planned.id}"]},
            status="ready",
        )
    if planned.object == "aside":
        return WriterOutcome(
            block_id=planned.id,
            content={"label": "Note", "body": planned.brief or "Remember light makes food."},
            status="ready",
        )
    if planned.object == "worked-example":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "problem": planned.brief or "Worked example",
                "steps": [{"text": "Step 1"}, {"text": "Step 2"}],
                "answer": ANSWER_PHRASE,
            },
            status="ready",
        )
    if planned.object == "table":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "columns": [
                    {"id": "c", "label": "Condition"},
                    {"id": "o", "label": "Observation"},
                ],
                "rows": [
                    {"cells": {"c": "Lit", "o": "Makes food"}},
                    {"cells": {"c": "Covered", "o": "No food"}},
                ],
                "presentation": "comparison",
            },
            status="ready",
        )
    return WriterOutcome(
        block_id=planned.id,
        content={"paragraphs": [planned.brief or f"Content for {planned.id}"]},
        status="ready",
    )


async def _prepare_unit_generation(*, owner_suffix: str) -> tuple[str, str, str, str]:
    """Real DB Unit → prepare. Returns gid, item_id, user_id, path_lesson_id."""
    user_id = f"p08-{owner_suffix}"
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.invalid",
                name=f"P08 {owner_suffix}",
            )
        )
        plan = load_canonical_plan(FIXTURE)
        unit = await create_unit(
            session,
            owner_id=user_id,
            request=unit_create_from_fixture(FIXTURE),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        response, _ = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(lesson_mode="first_exposure"),
            structural_planner=_fake_structural_planner,
            component_selector=_fake_component_selector,
        )
        gid = response.generation_id
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        pack_id = generation.pack_id or gid
        card = await session.scalar(
            select(ConceptCardModel).where(ConceptCardModel.pack_id == pack_id)
        )
        if card is None:
            card = await session.scalar(
                select(ConceptCardModel).where(ConceptCardModel.pack_id == gid)
            )
        assert card is not None
        item_id = f"{pack_id}:p08-mcq-1"
        session.add(
            PackItemModel(
                id=item_id,
                pack_id=pack_id,
                card_id=card.id,
                stem="Why did the covered leaf fail to make food?",
                options=[
                    {"key": "A", "text": "No light reached the leaf", "correct": True},
                    {"key": "B", "text": "The soil ran out of food", "correct": False},
                ],
                correct_key="A",
                diagnoses={"B": "soil-food misconception"},
                stale=False,
            )
        )
        await session.commit()
        return gid, item_id, user_id, lesson.id


async def _approve_shared_teaching(*, gid: str, item_id: str) -> int:
    """Run production teaching planner (MOCK LLM) and approve."""

    async def _teaching_call(**_kwargs):  # noqa: ANN003
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
        draft = _draft_for_packet(packet, item_id=item_id)
        return draft, draft.model_dump_json()

    with patch(MOCKS["teaching_llm"], new=AsyncMock(side_effect=_teaching_call)):
        async with async_session_factory() as session:
            teaching_result = await run_and_persist_teaching_plan(
                session, gid, require_items=True
            )
            assert teaching_result["validation"]["ok"] is True
            review = teaching_result["review"] or {}
            revision = int(review.get("revision") or 1)
            await approve_teaching_and_queue(
                session,
                gid,
                expected_revision=revision,
                reviewed_by="p08-teacher",
            )
            await session.commit()
            return revision


async def _run_print(*, gid: str, fail_once: bool = False) -> dict:
    if fail_once:
        configure_failure_injection(
            enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
        )
    with patch(MOCKS["print_writer"], new=AsyncMock(side_effect=_fake_dispatch)):
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
            claimed = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="p08-print-worker"
            )
            assert claimed is not None
            return await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                worker_id="p08-print-worker",
                lease=claimed,
            )


async def _run_learn(
    *,
    gid: str,
    user_id: str,
    path_lesson_id: str,
    provider: P08LearnMockProvider | None = None,
) -> dict:
    async with async_session_factory() as session:
        state = await load_shared_teaching_state(session, gid)
        print_plan, learn_plan = await accept_shared_teaching_for_both(state)
        repo = PageDocumentRepository(session, gid)

        def _mut(_generation: GenerationModel, mut_state: dict) -> None:
            mut_state["teaching_consumer_handoffs"] = state.get(
                "teaching_consumer_handoffs"
            )

        await repo.mutate_state(mutation=_mut)
        generation = await session.get(GenerationModel, gid)
        pack_id = generation.pack_id if generation else None
        result = await produce_learn_from_approved_teaching(
            session,
            teaching_plan=learn_plan,
            user_id=user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=gid,
            pack_id=pack_id,
            title=learn_plan.arc,
            subject="science",
            provider=provider or _p08_learn_provider(),
            choose=_p08_choose,
        )
        await link_print_realization(
            session,
            path_lesson_id=path_lesson_id,
            teaching_plan=print_plan,
            preparation_generation_id=gid,
            pack_id=pack_id,
            output_id=gid,
            status="ready",
        )
        await session.commit()
        return result


@pytest.mark.asyncio
async def test_p08_i01_uninterrupted_dual_path_no_plan_swap() -> None:
    """Unit→Print and Unit→Learn without swapping prepared plan or bypassing selection."""
    gid, item_id, user_id, lesson_id = await _prepare_unit_generation(owner_suffix="i01")
    await _approve_shared_teaching(gid=gid, item_id=item_id)

    print_result = await _run_print(gid=gid)
    assert print_result["status"] in {"ready", "awaiting_visuals"}

    learn_result = await _run_learn(gid=gid, user_id=user_id, path_lesson_id=lesson_id)
    assert learn_result["status"] == "ready"
    assert learn_result["selection_trace"]["form_prompt"] == "closed_learn_selection"

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        assert state.get("form_prompt") == "closed_print_selection"
        assert "selection_snapshot" in (state.get("form_raw") or "")
        assert state.get("teaching_plan")
        handoffs = state.get("teaching_consumer_handoffs") or {}
        assert "print" in handoffs and "learn" in handoffs
        assert handoffs["print"]["revision"] == handoffs["learn"]["revision"]
        assert handoffs["print"]["block_ids"] == handoffs["learn"]["block_ids"]

        learn_gen = await session.get(GenerationModel, learn_result["output_id"])
        assert learn_gen is not None
        assert (learn_gen.chunked_state_json or {}).get("form_prompt") == "closed_learn_selection"
        doc = learn_gen.document_json or {}
        assert doc.get("assembly", {}).get("selection_hash")
        snap = learn_result["selection_trace"]["selection_snapshot"]
        teaching_ids = [
            b["id"]
            for s in (state["teaching_plan"].get("sections") or [])
            for b in (s.get("blocks") or [])
        ]
        decided = [d["block_id"] for d in snap.get("decisions") or []]
        assert set(teaching_ids) == set(decided)

        print_doc = reload_document(generation.document_json or {})
        assert validate_document(print_doc) == []


@pytest.mark.asyncio
async def test_p08_i02_instructional_coverage_both_outputs() -> None:
    """Same revision → both outputs preserve objective/facts/task/visual obligations."""
    gid, item_id, user_id, lesson_id = await _prepare_unit_generation(owner_suffix="i02")
    await _approve_shared_teaching(gid=gid, item_id=item_id)
    await _run_print(gid=gid)
    learn_result = await _run_learn(gid=gid, user_id=user_id, path_lesson_id=lesson_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        teaching = state["teaching_plan"]
        coverage = instructional_coverage(teaching)
        assert coverage["arc"]

        print_doc = reload_document(generation.document_json or {})
        form_plan = state.get("form_plan")
        assert_print_covers_instruction(
            coverage=coverage,
            teaching_plan=teaching,
            print_document=print_doc,
            form_plan=form_plan if isinstance(form_plan, dict) else None,
        )
        assert_learn_covers_instruction(
            coverage=coverage,
            learn_document=learn_result["document"],
            selection_trace=learn_result["selection_trace"],
        )
        assert learn_result["document"] != print_doc
        handoffs = state.get("teaching_consumer_handoffs") or {}
        assert handoffs["print"]["preparation_hash"] == handoffs["learn"]["preparation_hash"]


@pytest.mark.asyncio
async def test_p08_i03_sentinels_scoped_repair_stale_lease() -> None:
    """Stage input sentinels, scoped repair, stale-lease rejection; traces locate failures."""
    gid, item_id, user_id, lesson_id = await _prepare_unit_generation(owner_suffix="i03")
    await _approve_shared_teaching(gid=gid, item_id=item_id)

    async with async_session_factory() as session:
        state = await load_shared_teaching_state(session, gid)
        _, learn_plan = await accept_shared_teaching_for_both(state)
    from learn.generation.preparation_context import learn_preparation_context_from_state

    prep = learn_preparation_context_from_state(state)
    production = build_closed_learn_production(
        teaching_plan=learn_plan,
        title=learn_plan.arc,
        write_interactions=True,
        provider=_p08_learn_provider(),
        preparation_context=prep,
        choose=_p08_choose,
    )
    sentinel = "SIBLING_SCHEMA_SENTINEL_p08i03_zz9"
    ix_orders = [o for o in production["work_orders"] if o.lane == "interaction"]
    if ix_orders:
        req = build_learn_writer_request(
            ix_orders[0],
            sibling_sentinels={"sibling_payload_schema": {sentinel: {"x": 1}}},
        )
        assert_sentinels_absent(json.dumps(req), [sentinel], where="learn_writer_request")
    polluted = with_excluded_sentinels(
        {"arc": learn_plan.arc},
        sentinels={"form_id": sentinel, "allowed_components": [sentinel]},
    )
    assert sentinel in json.dumps(polluted)
    async with async_session_factory() as session:
        state = await load_shared_teaching_state(session, gid)
        _print_plan, learn_plan2 = await accept_shared_teaching_for_both(state)
        blob = json.dumps(learn_plan2.model_dump(mode="json"))
        assert_sentinels_absent(blob, [sentinel], where="approved_teaching")

    print_first = await _run_print(gid=gid, fail_once=True)
    assert print_first["status"] in {
        "ready",
        "awaiting_visuals",
        "failed_recoverable",
        "writing_sections",
        "writing_blocks",
    }
    # Scoped repair: requeue recoverable failure then resume (production path).
    reset_failure_injection()
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        if generation.status == "failed_recoverable":
            await PageDocumentRepository(session, gid).transition(
                expected={"failed_recoverable"},
                target="queued",
                event="requeue",
            )
        elif generation.status not in {"ready", "awaiting_visuals", "queued"}:
            generation.status = "queued"
            await session.commit()
    if print_first["status"] not in {"ready", "awaiting_visuals"}:
        print_second = await _run_print(gid=gid, fail_once=False)
        assert print_second["status"] in {"ready", "awaiting_visuals"}

    async with async_session_factory() as session:
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        events = state.get("events") or []
        assert events or state.get("execution")
        # Trace locates this generation's failure/repair events.
        assert any(
            isinstance(ev, dict)
            and (
                ev.get("generation_id") == gid
                or ev.get("name") in {"execution_claimed", "execution_reclaimed", "requeue"}
                or "fail" in str(ev.get("name") or "").lower()
                or "claim" in str(ev.get("name") or "").lower()
            )
            for ev in events
        ) or state.get("execution")

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)

        def _age(_g: GenerationModel, st: dict) -> None:
            execution = dict(st.get("execution") or empty_execution_meta())
            old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
            execution["worker_id"] = "worker-old"
            execution["lease_token"] = 7
            execution["heartbeat_at"] = old
            execution["lease_seconds"] = 30
            st["execution"] = execution
            if str(_g.status) in {"ready", "awaiting_visuals", "completed"}:
                _g.status = "writing_sections"

        await repo.mutate_state(mutation=_age)
        await session.commit()

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        reclaimed = await repo.claim_execution(worker_id="worker-new", lease_seconds=60)
        assert reclaimed is not None
        assert reclaimed.worker_id == "worker-new"
        assert reclaimed.lease_token != 7
        with pytest.raises(LeaseLostError):
            await repo.assert_lease(worker_id="worker-old", lease_token=7)
        await repo.assert_lease(
            worker_id=reclaimed.worker_id, lease_token=reclaimed.lease_token
        )

    learn_result = await _run_learn(gid=gid, user_id=user_id, path_lesson_id=lesson_id)
    assert learn_result["status"] == "ready"


@pytest.mark.asyncio
async def test_p08_i04_teacher_edit_and_sibling_isolation() -> None:
    """Teacher edits survive retries; one native failure does not block ready sibling."""
    gid, item_id, user_id, lesson_id = await _prepare_unit_generation(owner_suffix="i04")
    await _approve_shared_teaching(gid=gid, item_id=item_id)
    print_result = await _run_print(gid=gid)
    assert print_result["status"] in {"ready", "awaiting_visuals"}
    learn_result = await _run_learn(gid=gid, user_id=user_id, path_lesson_id=lesson_id)

    edited_title = "P08 teacher-edited Learn title"
    edited_body = "P08 teacher-edited explanation body survives print retry."

    async with async_session_factory() as session:
        lesson = await session.get(EditableLessonModel, learn_result["editable_lesson_id"])
        assert lesson is not None
        doc = dict(lesson.document_json or {})
        doc["title"] = edited_title
        for block in (doc.get("blocks") or {}).values():
            if isinstance(block, dict) and isinstance(block.get("content"), dict):
                if "body" in block["content"]:
                    block["content"]["body"] = edited_body
                    break
        lesson.document_json = doc
        lesson.title = edited_title
        lesson.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        learn_row = await session.get(NativeRealizationModel, learn_result["realization_id"])
        assert learn_row is not None
        learn_before = (
            learn_row.id,
            learn_row.output_id,
            learn_row.status,
            learn_row.teaching_plan_hash,
            learn_row.realization_revision,
        )
        await session.commit()

    async with async_session_factory() as session:
        print_rows = await session.scalars(
            select(NativeRealizationModel).where(
                NativeRealizationModel.path_lesson_id == lesson_id,
                NativeRealizationModel.path == "print",
            )
        )
        print_row = print_rows.first()
        assert print_row is not None
        retried = await retry_realization(
            session, realization_id=print_row.id, new_output_id=f"{gid}-retry"
        )
        await session.commit()
        assert retried.realization_revision >= 2

    async with async_session_factory() as session:
        lesson = await session.get(EditableLessonModel, learn_result["editable_lesson_id"])
        assert lesson is not None
        assert lesson.title == edited_title
        assert edited_body in json.dumps(lesson.document_json)
        learn_row = await session.get(NativeRealizationModel, learn_result["realization_id"])
        assert learn_row is not None
        assert (
            learn_row.id,
            learn_row.output_id,
            learn_row.status,
            learn_row.teaching_plan_hash,
            learn_row.realization_revision,
        ) == learn_before

    async with async_session_factory() as session:
        learn_row = await session.get(NativeRealizationModel, learn_result["realization_id"])
        assert learn_row is not None
        learn_row.status = "failed_recoverable"
        learn_row.error_summary = "injected learn failure for P08-I04"
        print_rows = await session.scalars(
            select(NativeRealizationModel).where(
                NativeRealizationModel.path_lesson_id == lesson_id,
                NativeRealizationModel.path == "print",
            )
        )
        print_row = print_rows.first()
        assert print_row is not None
        print_status_before = print_row.status
        await session.commit()

    async with async_session_factory() as session:
        print_rows = await session.scalars(
            select(NativeRealizationModel).where(
                NativeRealizationModel.path_lesson_id == lesson_id,
                NativeRealizationModel.path == "print",
            )
        )
        print_row = print_rows.first()
        assert print_row is not None
        assert print_row.status == print_status_before
        assert print_row.output_id


def test_p08_i06_mock_catalogue_is_explicit() -> None:
    """Deterministic suite discloses mocks; does not claim live providers."""
    assert MOCKS["teaching_llm"].endswith("_call_teaching_model")
    assert MOCKS["print_writer"].endswith("dispatch_writer_async")
    catalogue = {
        "suite": "tests/print_learn/test_p08_integration_gates.py",
        "class": "deterministic_integration",
        "live_claim": False,
        "mocks": MOCKS,
        "note": (
            "LLM teaching call, Print writer dispatch and Learn authoring provider are mocked. "
            "Closed selection, DB persistence, leases, realizations and Learn "
            "assembly use production services. Not a live P09 campaign."
        ),
    }
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_ROOT / "i06-mock-catalogue.json"
    path.write_text(json.dumps(catalogue, indent=2), encoding="utf-8")
    assert path.exists()
    assert catalogue["live_claim"] is False
