"""Final Component Lectio exact-contract gates (A–T)."""

from __future__ import annotations

import uuid
import json
from typing import Any, get_args

import pytest
from sqlalchemy import select

from contracts.lesson_document import validate_lesson_document
from contracts.section_content import ReflectionType
from core.database.models import EditableLessonModel, GenerationModel, UserModel
from core.database.session import async_session_factory
from learn.generation.component_lectio.coverage_audit import (
    coverage_gaps,
    production_selectable_components,
)
from learn.generation.component_lectio.errors import AnswerKeyMappingError, WorkOrderIdentityError
from learn.generation.component_lectio.fixtures import valid_content_for
from learn.generation.component_lectio.payload_strategies import (
    SCHEMA_SUMMARIES,
    assemble_answer_key_content,
    assemble_items_content,
    assemble_visual_content,
)
from learn.generation.component_lectio.payload_validation import (
    ExactPayloadValidationError,
    validate_exact_payload,
)
from learn.generation.component_lectio.service import (
    FAILED_STEP,
    READY_STEP,
    _persist_component_lectio_success,
    reconstruct_checkpoint_store,
    run_component_lectio_execution,
)
from learn.generation.contracts import GenerationInputForm as V3InputForm
from tests.v3_blueprint.planning.test_intent_plan import SUBJECT_FIXTURES, _intent_plan_for_subject
from v3_blueprint.planning.canonical_plan import (
    CanonicalExecutionPlan,
    SelectedComponent,
    SelectorChoice,
)
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from v3_blueprint.planning.persistence import load_chunked_state, load_steps, persist_chunked_state
from v3_blueprint.planning.work_orders import ExactWorkOrder
from v3_execution.runtime.lesson_document import assemble_lesson_document
from v3_execution.models import (
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
)


INTEGRATION_PICKS = {
    "orient": ("hook-hero",),
    "build": ("explanation-block",),
    "model": ("worked-example-card", "diagram-block"),
    "practice": ("practice-stack", "quiz-check"),
    "close": ("summary-block",),
}

COMPARE_PICKS = {
    "orient": ("hook-hero",),
    "build": ("diagram-compare",),
    "model": ("worked-example-card",),
    "practice": ("practice-stack",),
    "close": ("summary-block",),
}

SERIES_PICKS = {
    "orient": ("hook-hero",),
    "build": ("explanation-block",),
    "model": ("diagram-series",),
    "practice": ("practice-stack",),
    "close": ("summary-block",),
}


def _forced_selector(picks: dict[str, tuple[str, ...]]):
    def select(context: dict) -> SelectorChoice:
        allowed = {card["component_id"] for card in context.get("allowed_components") or []}
        role = str(context.get("role") or context.get("slot_id") or "")
        wanted = [slug for slug in picks.get(role, ()) if slug in allowed]
        if not wanted:
            first = next(iter(allowed), None)
            wanted = [first] if first else []
        return SelectorChoice(
            components=[
                SelectedComponent(slug=slug, purpose=f"teach via {slug}", reason="forced")
                for slug in wanted
            ]
        )

    return select


def _order_stub(
    *,
    component_id: str,
    lane: str,
    block_id: str = "b1",
    section_id: str = "s1",
) -> ExactWorkOrder:
    from contracts.lectio import get_component_card

    card = get_component_card(component_id) or {}
    field = card.get("section_field") or card.get("sectionField") or ""
    return ExactWorkOrder(
        work_order_id=f"wo::{block_id}",
        block_id=block_id,
        section_id=section_id,
        component_id=component_id,
        purpose="test",
        lane=lane,
        plan_revision=1,
        plan_hash="hash",
        component_card={
            "component_id": component_id,
            "section_field": field,
            "cognitive_job": card.get("cognitive_job"),
            "capabilities": card.get("capabilities") or {},
            "writer_excluded": bool(card.get("writer_excluded")),
            "field_contracts": card.get("field_contracts") or {},
        },
        locked_component_id=component_id,
    )


async def _seed_generation(generation_id: str) -> None:
    from core.database.session import async_session_factory

    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=f"user-{generation_id}",
                email=f"{generation_id}@example.com",
                name="FinalContract",
            )
        )
        session.add(
            GenerationModel(
                id=generation_id,
                user_id=f"user-{generation_id}",
                subject="Math",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="running",
            )
        )
        await session.commit()
    await persist_chunked_state(
        generation_id,
        {
            "stage": "awaiting_review",
            "control": {"pipeline": "component_lectio"},
        },
    )


def _form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 7",
        subject="Math",
        duration_minutes=45,
        topic="Fractions",
        outcome="compare ratios",
    )


async def _fake_section_executor(work_order, emit, **kwargs):
    from contracts.lectio import get_section_field_for_component

    return [
        GeneratedComponentBlock(
            block_id=work_order.work_order_id,
            section_id=work_order.section.id,
            component_id=component.component_id,
            section_field=get_section_field_for_component(component.component_id)
            or component.component_id,
            position=idx,
            data=valid_content_for(component.component_id),
            source_work_order_id=work_order.work_order_id,
        )
        for idx, component in enumerate(work_order.section.components)
    ]


async def _fake_question_executor(work_order, emit, **kwargs):
    component_id = work_order.component_id or "practice-stack"
    content = valid_content_for(component_id)
    return [
        GeneratedQuestionBlock(
            question_id=item.id,
            section_id=work_order.section_id,
            difficulty=item.difficulty,
            data=content,
            expected_answer="4",
            source_work_order_id=work_order.work_order_id,
        )
        for item in work_order.questions
    ]


async def _fake_visual_executor(work_order, emit, **kwargs):
    component_id = work_order.visual.component_id or "diagram-block"
    frames = list(work_order.visual.frames or [])
    if component_id in {"diagram-compare", "diagram-series"} and len(frames) < 2:
        frames = [object(), object(), object()][: 3 if component_id == "diagram-series" else 2]
    count = max(1, len(frames))
    return [
        GeneratedVisualBlock(
            visual_id=work_order.visual.id,
            attaches_to=work_order.visual.attaches_to,
            mode=work_order.visual.mode,
            frame_index=idx if count > 1 else None,
            image_url=f"https://example.test/{component_id}-{idx}.png",
            caption=work_order.visual.purpose or "diagram",
            alt_text=work_order.visual.purpose or "diagram",
            source_work_order_id=work_order.work_order_id,
            component_id=component_id,
            parent_visual_id=work_order.visual.id if count > 1 else None,
        )
        for idx in range(count)
    ]


def _exec_kwargs(**overrides):
    return {
        "selector": _forced_selector(INTEGRATION_PICKS),
        "section_executor": _fake_section_executor,
        "question_executor": _fake_question_executor,
        "visual_executor": _fake_visual_executor,
        **overrides,
    }


# --- Gate A / unit validators ---


def test_gate_a_validator_rejects_identity_and_generic_items():
    order = _order_stub(component_id="practice-stack", lane="items")
    with pytest.raises(WorkOrderIdentityError):
        validate_exact_payload(
            order,
            {
                "content": valid_content_for("practice-stack"),
                "component_id": "quiz-check",
                "block_id": order.block_id,
            },
        )


def test_gate_b_invalid_generic_practice_payload_rejected():
    order = _order_stub(component_id="practice-stack", lane="items")
    with pytest.raises(ExactPayloadValidationError) as exc:
        validate_exact_payload(
            order,
            {
                "content": {"items": []},
                "component_id": "practice-stack",
                "block_id": order.block_id,
            },
        )
    assert any("problems" in err or "Field required" in err for err in exc.value.errors)


def test_gate_c_valid_practice_stack_passes():
    order = _order_stub(component_id="practice-stack", lane="items")
    payload = validate_exact_payload(
        order,
        {
            "content": valid_content_for("practice-stack"),
            "component_id": "practice-stack",
            "block_id": order.block_id,
        },
    )
    assert "problems" in payload["content"]


def test_gate_e_short_answer():
    order = _order_stub(component_id="short-answer", lane="items")
    payload = validate_exact_payload(
        order,
        {
            "content": valid_content_for("short-answer"),
            "component_id": "short-answer",
            "block_id": order.block_id,
        },
    )
    assert payload["content"]["question"]


def test_gate_f_fill_in_blank():
    order = _order_stub(component_id="fill-in-blank", lane="items")
    payload = validate_exact_payload(
        order,
        {
            "content": valid_content_for("fill-in-blank"),
            "component_id": "fill-in-blank",
            "block_id": order.block_id,
        },
    )
    assert payload["content"]["segments"]


def test_gate_g_reflection_and_student_textbox():
    for component_id in ("reflection-prompt", "student-textbox"):
        order = _order_stub(component_id=component_id, lane="items")
        payload = validate_exact_payload(
            order,
            {
                "content": valid_content_for(component_id),
                "component_id": component_id,
                "block_id": order.block_id,
            },
        )
        assert "prompt" in payload["content"]


def test_reflection_schema_guidance_matches_lectio_enum():
    allowed = "|".join(get_args(ReflectionType))
    assert f"type({allowed})" in SCHEMA_SUMMARIES["reflection-prompt"]
    assert "value" not in SCHEMA_SUMMARIES["reflection-prompt"]


def test_gate_h_answer_key_deterministic_mapping():
    order = _order_stub(component_id="answer-key", lane="answer_key")
    payload = assemble_answer_key_content(
        order,
        question_refs=[
            {"id": "q1", "question": "What is 2+2?", "expected_answer": "4"},
        ],
    )
    validated = validate_exact_payload(order, payload)
    entry = validated["content"]["entries"][0]
    assert entry["question_number"] == 1.0
    assert entry["question"] == "What is 2+2?"
    assert entry["correct_answer"] == "4"


def test_gate_o_deterministic_answer_key_defects_are_terminal():
    order = _order_stub(component_id="answer-key", lane="answer_key")
    with pytest.raises(AnswerKeyMappingError):
        assemble_answer_key_content(
            order,
            question_refs=[{"id": "q1", "question": "Missing answer", "expected_answer": ""}],
        )


def test_gate_i_diagram_block():
    order = _order_stub(component_id="diagram-block", lane="visual")
    blocks = [
        GeneratedVisualBlock(
            visual_id=order.block_id,
            attaches_to=order.section_id,
            mode="diagram",
            image_url="https://example.test/d.png",
            caption="c",
            alt_text="a",
            source_work_order_id=order.work_order_id,
            component_id="diagram-block",
        )
    ]
    payload = assemble_visual_content(order, blocks)
    validate_exact_payload(order, payload)


@pytest.mark.parametrize("status", ["failed", "omitted_quality"])
def test_diagram_block_rejects_unusable_status(status: str):
    order = _order_stub(component_id="diagram-block", lane="visual")
    block = GeneratedVisualBlock(
        visual_id=order.block_id,
        attaches_to=order.section_id,
        mode="diagram",
        image_url="https://example.test/d.png",
        source_work_order_id=order.work_order_id,
        component_id="diagram-block",
        status=status,
    )
    with pytest.raises(ValueError, match=status):
        assemble_visual_content(order, [block])


@pytest.mark.parametrize("status", ["ready", "flagged_quality"])
def test_diagram_block_rejects_empty_visual_source(status: str):
    order = _order_stub(component_id="diagram-block", lane="visual")
    block = GeneratedVisualBlock(
        visual_id=order.block_id,
        attaches_to=order.section_id,
        mode="diagram",
        image_url="  ",
        html_content="",
        source_work_order_id=order.work_order_id,
        component_id="diagram-block",
        status=status,
    )
    with pytest.raises(ValueError, match="usable visual source"):
        assemble_visual_content(order, [block])


def test_flagged_diagram_preserves_quality_metadata_outside_content():
    order = _order_stub(component_id="diagram-block", lane="visual")
    block = GeneratedVisualBlock(
        visual_id=order.block_id,
        attaches_to=order.section_id,
        mode="diagram",
        image_url="https://example.test/d.png",
        source_work_order_id=order.work_order_id,
        component_id="diagram-block",
        status="flagged_quality",
        qc_reasons=["labels are crowded"],
        qc_correction_hint="increase label spacing",
    )

    payload = assemble_visual_content(order, [block])

    assert payload["visual_quality"] == {
        "status": "flagged_quality",
        "reasons": ["labels are crowded"],
        "correction_hint": "increase label spacing",
    }
    assert "visual_quality" not in payload["content"]


def test_gate_j_diagram_compare():
    order = _order_stub(component_id="diagram-compare", lane="visual")
    single = [
        GeneratedVisualBlock(
            visual_id=order.block_id,
            attaches_to=order.section_id,
            mode="diagram",
            image_url="https://example.test/d.png",
            caption="c",
            alt_text="a",
            source_work_order_id=order.work_order_id,
            component_id="diagram-compare",
        )
    ]
    with pytest.raises(ValueError, match="before/after|insufficient"):
        assemble_visual_content(order, single)
    blocks = single + [
        GeneratedVisualBlock(
            visual_id=order.block_id,
            attaches_to=order.section_id,
            mode="diagram",
            frame_index=1,
            image_url="https://example.test/d2.png",
            caption="c2",
            alt_text="a2",
            source_work_order_id=order.work_order_id,
            component_id="diagram-compare",
        )
    ]
    payload = assemble_visual_content(order, blocks)
    validate_exact_payload(order, payload)
    assert "before_label" in payload["content"]
    assert "after_label" in payload["content"]


@pytest.mark.parametrize("missing_index", [0, 1])
def test_diagram_compare_requires_each_side_to_have_a_source(missing_index: int):
    order = _order_stub(component_id="diagram-compare", lane="visual")
    blocks = [
        GeneratedVisualBlock(
            visual_id=order.block_id,
            attaches_to=order.section_id,
            mode="diagram_compare",
            frame_index=idx,
            image_url=None if idx == missing_index else f"https://example.test/{idx}.png",
            html_content=" " if idx == missing_index else None,
            source_work_order_id=order.work_order_id,
            component_id="diagram-compare",
        )
        for idx in range(2)
    ]
    with pytest.raises(ValueError, match="before/after visual source"):
        assemble_visual_content(order, blocks)


def test_gate_k_diagram_series():
    order = _order_stub(component_id="diagram-series", lane="visual")
    with pytest.raises(ValueError, match="diagrams\\[\\]|insufficient"):
        assemble_visual_content(
            order,
            [
                GeneratedVisualBlock(
                    visual_id=order.block_id,
                    attaches_to=order.section_id,
                    mode="diagram_series",
                    image_url="https://example.test/d.png",
                    caption="c",
                    alt_text="a",
                    source_work_order_id=order.work_order_id,
                    component_id="diagram-series",
                )
            ],
        )
    blocks = [
        GeneratedVisualBlock(
            visual_id=order.block_id,
            attaches_to=order.section_id,
            mode="diagram_series",
            frame_index=idx,
            image_url=f"https://example.test/s{idx}.png",
            caption=f"c{idx}",
            alt_text=f"a{idx}",
            source_work_order_id=order.work_order_id,
            component_id="diagram-series",
        )
        for idx in range(3)
    ]
    payload = assemble_visual_content(order, blocks)
    validate_exact_payload(order, payload)
    assert len(payload["content"]["diagrams"]) == 3


@pytest.mark.parametrize("missing_index", [0, 1, 2])
def test_diagram_series_requires_every_frame_to_have_a_source(missing_index: int):
    order = _order_stub(component_id="diagram-series", lane="visual")
    blocks = [
        GeneratedVisualBlock(
            visual_id=order.block_id,
            attaches_to=order.section_id,
            mode="diagram_series",
            frame_index=idx,
            image_url=None if idx == missing_index else f"https://example.test/{idx}.png",
            source_work_order_id=order.work_order_id,
            component_id="diagram-series",
        )
        for idx in range(3)
    ]
    with pytest.raises(ValueError, match=f"frame {missing_index + 1}"):
        assemble_visual_content(order, blocks)


def test_gate_n_no_component_substitution():
    order = _order_stub(component_id="practice-stack", lane="items")
    with pytest.raises(WorkOrderIdentityError):
        validate_exact_payload(
            order,
            {
                "content": valid_content_for("short-answer"),
                "component_id": "short-answer",
                "block_id": order.block_id,
            },
        )


def test_gate_l_selectable_component_coverage_audit():
    rows = production_selectable_components()
    assert rows
    gaps = coverage_gaps()
    assert gaps == [], f"Coverage gaps: {gaps}"


def test_content_lane_exact_validation():
    """Exact-contract marker for content-lane selectable components."""
    for component_id in (
        "section-header",
        "prerequisite-strip",
        "callout-block",
        "what-next-bridge",
        "section-divider",
        "definition-card",
        "definition-family",
        "glossary-rail",
        "insight-strip",
        "key-fact",
        "comparison-grid",
        "process-steps",
        "pitfall-alert",
    ):
        order = _order_stub(component_id=component_id, lane="content")
        validate_exact_payload(
            order,
            {
                "content": valid_content_for(component_id),
                "component_id": component_id,
                "block_id": order.block_id,
            },
        )


@pytest.mark.asyncio
async def test_gate_d_quiz_check_repair_feedback():
    generation_id = f"quiz-repair-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    calls: list[Any] = []

    async def quiz_executor(work_order, emit, **kwargs):
        calls.append(list(work_order.prior_validation_errors or []))
        if len(calls) == 1:
            bad = {"question": "What is 2+2?", "feedback_correct": "ok", "feedback_incorrect": "no"}
            return [
                GeneratedQuestionBlock(
                    question_id=work_order.questions[0].id,
                    section_id=work_order.section_id,
                    difficulty="core",
                    data=bad,
                    expected_answer="4",
                    source_work_order_id=work_order.work_order_id,
                )
            ]
        return [
            GeneratedQuestionBlock(
                question_id=work_order.questions[0].id,
                section_id=work_order.section_id,
                difficulty="core",
                data=valid_content_for("quiz-check"),
                expected_answer="4",
                source_work_order_id=work_order.work_order_id,
            )
        ]

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card",),
        "practice": ("quiz-check",),
        "close": ("summary-block",),
    }
    document = await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(selector=_forced_selector(picks), question_executor=quiz_executor),
    )
    assert document
    assert len(calls) == 2
    assert calls[0] == []
    assert calls[1], "repair must receive exact validation errors"
    assert any("options" in err for err in calls[1])


@pytest.mark.asyncio
async def test_gate_m_exact_repair_feedback_counts():
    # Covered by gate D for quiz; assert sibling content blocks run once via counters.
    generation_id = f"repair-counts-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    section_counts: dict[str, int] = {}
    question_counts: dict[str, int] = {}

    async def counting_section(work_order, emit, **kwargs):
        cid = work_order.section.components[0].component_id
        section_counts[cid] = section_counts.get(cid, 0) + 1
        return await _fake_section_executor(work_order, emit, **kwargs)

    async def counting_question(work_order, emit, **kwargs):
        cid = work_order.component_id or "practice-stack"
        question_counts[cid] = question_counts.get(cid, 0) + 1
        if cid == "quiz-check" and question_counts[cid] == 1:
            return [
                GeneratedQuestionBlock(
                    question_id=work_order.questions[0].id,
                    section_id=work_order.section_id,
                    difficulty="core",
                    data={"question": "broken"},
                    expected_answer="4",
                    source_work_order_id=work_order.work_order_id,
                )
            ]
        return await _fake_question_executor(work_order, emit, **kwargs)

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card",),
        "practice": ("quiz-check",),
        "close": ("summary-block",),
    }
    await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(
            selector=_forced_selector(picks),
            section_executor=counting_section,
            question_executor=counting_question,
        ),
    )
    assert question_counts.get("quiz-check") == 2
    assert section_counts.get("hook-hero") == 1
    assert section_counts.get("explanation-block") == 1


@pytest.mark.asyncio
async def test_gate_p_final_document_round_trip():
    generation_id = f"e2e-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    document = await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(),
    )
    validate_lesson_document(document)
    assert document["preset_id"] == "blue-classroom"
    component_ids = {block["component_id"] for block in document["blocks"].values()}
    for required in (
        "hook-hero",
        "explanation-block",
        "worked-example-card",
        "practice-stack",
        "quiz-check",
        "diagram-block",
        "summary-block",
    ):
        assert required in component_ids


@pytest.mark.asyncio
async def test_gate_p_compare_and_series_fixtures():
    for picks, needed in ((COMPARE_PICKS, "diagram-compare"), (SERIES_PICKS, "diagram-series")):
        generation_id = f"{needed}-{uuid.uuid4().hex[:8]}"
        await _seed_generation(generation_id)
        plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
        document = await run_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            form=_form(),
            **_exec_kwargs(selector=_forced_selector(picks)),
        )
        ids = {block["component_id"] for block in document["blocks"].values()}
        assert needed in ids
        block = next(b for b in document["blocks"].values() if b["component_id"] == needed)
        if needed == "diagram-compare":
            assert "before_label" in block["content"]
        else:
            assert "diagrams" in block["content"]


@pytest.mark.asyncio
async def test_gate_h_answer_key_db_reconstruction():
    generation_id = f"ak-resume-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    # First run practice only path pieces by seeding a ready practice checkpoint then
    # completing via execution that can reconstruct refs from DB.
    document = await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(
            selector=_forced_selector(
                {
                    "orient": ("hook-hero",),
                    "build": ("explanation-block",),
                    "model": ("worked-example-card",),
                    "practice": ("practice-stack",),
                    "close": ("summary-block",),
                }
            )
        ),
    )
    assert document
    rows = await load_steps(generation_id)
    practice_ready = [
        row
        for row in rows
        if row.step == READY_STEP
        and isinstance(row.payload, dict)
        and isinstance(row.payload.get("payload"), dict)
        and row.payload["payload"].get("component_id") == "practice-stack"
    ]
    assert practice_ready
    refs = practice_ready[0].payload["payload"].get("question_refs")
    assert refs and refs[0].get("expected_answer")


@pytest.mark.asyncio
async def test_gate_q_failure_stays_scoped():
    generation_id = f"scoped-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    counts: dict[str, int] = {}

    async def counting_section(work_order, emit, **kwargs):
        cid = work_order.section.components[0].component_id
        counts[cid] = counts.get(cid, 0) + 1
        return await _fake_section_executor(work_order, emit, **kwargs)

    async def flaky_practice(work_order, emit, **kwargs):
        cid = work_order.component_id or "practice-stack"
        counts[cid] = counts.get(cid, 0) + 1
        if cid == "practice-stack" and counts[cid] == 1:
            return [
                GeneratedQuestionBlock(
                    question_id=work_order.questions[0].id,
                    section_id=work_order.section_id,
                    difficulty="core",
                    data={"items": []},
                    expected_answer="4",
                    source_work_order_id=work_order.work_order_id,
                )
            ]
        return await _fake_question_executor(work_order, emit, **kwargs)

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card", "diagram-block"),
        "practice": ("practice-stack",),
        "close": ("summary-block",),
    }
    await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(
            selector=_forced_selector(picks),
            section_executor=counting_section,
            question_executor=flaky_practice,
        ),
    )
    assert counts.get("hook-hero") == 1
    assert counts.get("explanation-block") == 1
    assert counts.get("practice-stack") == 2
    assert counts.get("summary-block") == 1


@pytest.mark.asyncio
async def test_unusable_visual_exhaustion_fails_only_visual_work_item():
    generation_id = f"visual-exhaust-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    visual_calls = 0

    async def always_failed_visual(work_order, emit, **kwargs):
        nonlocal visual_calls
        visual_calls += 1
        return [
            GeneratedVisualBlock(
                visual_id=work_order.visual.id,
                attaches_to=work_order.visual.attaches_to,
                mode=work_order.visual.mode,
                source_work_order_id=work_order.work_order_id,
                component_id=work_order.visual.component_id,
                status="failed",
                error_message="provider returned no usable image",
            )
        ]

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card", "diagram-block"),
        "practice": ("practice-stack",),
        "close": ("summary-block",),
    }
    with pytest.raises(RuntimeError, match="unusable status 'failed'"):
        await run_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            form=_form(),
            **_exec_kwargs(
                selector=_forced_selector(picks),
                visual_executor=always_failed_visual,
            ),
        )

    rows = await load_steps(generation_id)
    failed_visuals = [
        row
        for row in rows
        if row.step == FAILED_STEP
        and isinstance(row.payload, dict)
        and row.payload.get("error", {}).get("component_id") == "diagram-block"
    ]
    ready_components = {
        row.payload["payload"].get("component_id")
        for row in rows
        if row.step == READY_STEP
        and isinstance(row.payload, dict)
        and isinstance(row.payload.get("payload"), dict)
    }
    assert visual_calls == 2
    assert len(failed_visuals) == 1
    assert all(row.part_id != failed_visuals[0].part_id for row in rows if row.step == READY_STEP)
    assert {"hook-hero", "explanation-block", "worked-example-card", "practice-stack"} <= (
        ready_components
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        state = model.chunked_state_json or {}
        assert model.status == "failed"
        assert model.quality_passed is False
        assert model.completed_at is not None
        assert model.document_json is None
        assert state["stage"] == "assembly_blocked"


@pytest.mark.asyncio
async def test_empty_ready_visual_is_blocked_without_dropping_ready_siblings():
    """A completed-looking empty diagram must not produce a LessonDocument."""
    generation_id = f"visual-empty-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    async def empty_ready_visual(work_order, emit, **kwargs):
        return [
            GeneratedVisualBlock(
                visual_id=work_order.visual.id,
                attaches_to=work_order.visual.attaches_to,
                mode=work_order.visual.mode,
                image_url="  ",
                html_content="",
                source_work_order_id=work_order.work_order_id,
                component_id=work_order.visual.component_id,
                status="ready",
            )
        ]

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card", "diagram-block"),
        "practice": ("practice-stack",),
        "close": ("summary-block",),
    }
    with pytest.raises(RuntimeError, match="missing usable visual source"):
        await run_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            form=_form(),
            **_exec_kwargs(
                selector=_forced_selector(picks),
                visual_executor=empty_ready_visual,
            ),
        )

    rows = await load_steps(generation_id)
    failed_visuals = [
        row
        for row in rows
        if row.step == FAILED_STEP
        and isinstance(row.payload, dict)
        and row.payload.get("error", {}).get("component_id") == "diagram-block"
    ]
    ready_components = {
        row.payload["payload"].get("component_id")
        for row in rows
        if row.step == READY_STEP
        and isinstance(row.payload, dict)
        and isinstance(row.payload.get("payload"), dict)
    }
    assert len(failed_visuals) == 1
    assert {"hook-hero", "explanation-block", "worked-example-card", "practice-stack"} <= (
        ready_components
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        assert model.status == "failed"
        assert model.document_json is None
        assert model.quality_passed is False
        assert (model.chunked_state_json or {})["stage"] == "assembly_blocked"


@pytest.mark.asyncio
async def test_flagged_visual_quality_is_checkpoint_metadata_only():
    generation_id = f"visual-flagged-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    async def flagged_visual(work_order, emit, **kwargs):
        return [
            GeneratedVisualBlock(
                visual_id=work_order.visual.id,
                attaches_to=work_order.visual.attaches_to,
                mode=work_order.visual.mode,
                image_url="https://example.test/flagged.png",
                source_work_order_id=work_order.work_order_id,
                component_id=work_order.visual.component_id,
                status="flagged_quality",
                qc_reasons=["labels are crowded"],
                qc_correction_hint="increase label spacing",
            )
        ]

    document = await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(
            selector=_forced_selector(
                {
                    "orient": ("hook-hero",),
                    "build": ("explanation-block",),
                    "model": ("worked-example-card", "diagram-block"),
                    "practice": ("practice-stack",),
                    "close": ("summary-block",),
                }
            ),
            visual_executor=flagged_visual,
        ),
    )

    rows = await load_steps(generation_id)
    visual_rows = [
        row
        for row in rows
        if row.step == READY_STEP
        and isinstance(row.payload, dict)
        and isinstance(row.payload.get("payload"), dict)
        and row.payload["payload"].get("component_id") == "diagram-block"
    ]
    assert len(visual_rows) == 1
    checkpoint_payload = visual_rows[0].payload["payload"]
    assert checkpoint_payload["visual_quality"] == {
        "status": "flagged_quality",
        "reasons": ["labels are crowded"],
        "correction_hint": "increase label spacing",
    }

    state = await load_chunked_state(generation_id)
    canonical = CanonicalExecutionPlan.model_validate(state["canonical_plan"])
    store = await reconstruct_checkpoint_store(
        generation_id,
        plan_revision=canonical.plan_revision,
        plan_hash=canonical.plan_hash,
        desired_work=[block.block_id for block in canonical.blocks],
    )
    reassembled = assemble_lesson_document(
        canonical,
        store,
        title=_form().topic,
        subject=_form().subject,
    )
    assert reassembled["blocks"] == document["blocks"]
    assert reassembled["sections"] == document["sections"]
    serialized_document = json.dumps(reassembled)
    assert "visual_quality" not in serialized_document
    assert "labels are crowded" not in serialized_document
    assert "increase label spacing" not in serialized_document


@pytest.mark.asyncio
async def test_gate_r_retry_exhaustion():
    generation_id = f"exhaust-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    async def always_bad_quiz(work_order, emit, **kwargs):
        return [
            GeneratedQuestionBlock(
                question_id=work_order.questions[0].id,
                section_id=work_order.section_id,
                difficulty="core",
                data={"question": "no options"},
                expected_answer="4",
                source_work_order_id=work_order.work_order_id,
            )
        ]

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card",),
        "practice": ("quiz-check",),
        "close": ("summary-block",),
    }
    with pytest.raises(RuntimeError):
        await run_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            form=_form(),
            **_exec_kwargs(
                selector=_forced_selector(picks),
                question_executor=always_bad_quiz,
            ),
        )
    rows = await load_steps(generation_id)
    failed = [row for row in rows if row.step == FAILED_STEP]
    ready = [row for row in rows if row.step == READY_STEP]
    assert failed
    assert ready
    err = failed[0].payload["error"]
    assert err["class"] == "lectio_contract_validation"
    assert err["section_field"]
    assert err["validation_errors"]
    assert err["attempt"] == 2
    await reconstruct_checkpoint_store(
        generation_id, plan_revision=1, plan_hash="x", desired_work=[]
    )
    # pipeline sticky via chunked state
    from core.database.session import async_session_factory

    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        # document should not be complete
        assert not model.document_json


@pytest.mark.asyncio
async def test_gate_s_process_style_resume():
    generation_id = f"resume-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    # Seed by running once with a failing quiz, then fix executor and resume.
    async def first_pass_quiz(work_order, emit, **kwargs):
        return [
            GeneratedQuestionBlock(
                question_id=work_order.questions[0].id,
                section_id=work_order.section_id,
                difficulty="core",
                data={"question": "broken"},
                expected_answer="4",
                source_work_order_id=work_order.work_order_id,
            )
        ]

    picks = {
        "orient": ("hook-hero",),
        "build": ("explanation-block",),
        "model": ("worked-example-card",),
        "practice": ("quiz-check",),
        "close": ("summary-block",),
    }
    with pytest.raises(RuntimeError):
        await run_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            form=_form(),
            **_exec_kwargs(
                selector=_forced_selector(picks),
                question_executor=first_pass_quiz,
            ),
        )
    ready_before = {
        row.part_id for row in await load_steps(generation_id) if row.step == READY_STEP
    }
    executed: list[str] = []

    async def resume_section(work_order, emit, **kwargs):
        executed.append(work_order.section.components[0].component_id)
        return await _fake_section_executor(work_order, emit, **kwargs)

    async def resume_question(work_order, emit, **kwargs):
        executed.append(work_order.component_id or "items")
        return await _fake_question_executor(work_order, emit, **kwargs)

    async def resume_visual(work_order, emit, **kwargs):
        executed.append(work_order.visual.component_id or "visual")
        return await _fake_visual_executor(work_order, emit, **kwargs)

    document = await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **_exec_kwargs(
            selector=_forced_selector(picks),
            section_executor=resume_section,
            question_executor=resume_question,
            visual_executor=resume_visual,
        ),
    )
    assert document
    # Ready siblings from first pass must not re-execute.
    for cid in ("hook-hero", "explanation-block", "worked-example-card", "summary-block"):
        assert cid not in executed
    assert "quiz-check" in executed
    ready_after = {row.part_id for row in await load_steps(generation_id) if row.step == READY_STEP}
    assert ready_before.issubset(ready_after)

    # Completion owns the Builder handoff and is idempotent across retries.
    builder_id = await _persist_component_lectio_success(
        generation_id,
        document=document,
        plan_revision=1,
        plan_hash="resume-hash",
    )
    async with async_session_factory() as session:
        builder_rows = list(
            await session.scalars(
                select(EditableLessonModel).where(
                    EditableLessonModel.source_generation_id == generation_id,
                    EditableLessonModel.source_type == "component_lectio",
                )
            )
        )
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        assert len(builder_rows) == 1
        assert builder_rows[0].id == builder_id
        assert (model.chunked_state_json or {})["builder_id"] == builder_id

    repeated_builder_id = await _persist_component_lectio_success(
        generation_id,
        document=document,
        plan_revision=1,
        plan_hash="resume-hash",
    )
    assert repeated_builder_id == builder_id
    async with async_session_factory() as session:
        assert (
            await session.scalar(
                select(EditableLessonModel.id).where(
                    EditableLessonModel.source_generation_id == generation_id,
                    EditableLessonModel.source_type == "component_lectio",
                )
            )
            == builder_id
        )


def test_items_assembler_rejects_generic_wrapper():
    order = _order_stub(component_id="practice-stack", lane="items")
    with pytest.raises(ValueError, match="Generic items wrapper"):
        assemble_items_content(
            order,
            [
                GeneratedQuestionBlock(
                    question_id=order.block_id,
                    section_id=order.section_id,
                    difficulty="core",
                    data={"items": []},
                    expected_answer="4",
                    source_work_order_id=order.work_order_id,
                )
            ],
        )
