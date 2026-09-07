"""Component Lectio pre-live patch gates (selector, identity, lanes, document, repair)."""

from __future__ import annotations

import uuid

import pytest

from contracts.lesson_document import LessonDocumentValidationError, validate_lesson_document
from core.database.models import GenerationModel, UserModel
from generation.component_lectio.errors import WorkOrderIdentityError
from generation.component_lectio.fixtures import valid_content_for
from generation.component_lectio.lane_dispatch import resolve_exact_order
from generation.component_lectio.service import (
    DEFAULT_PRODUCTION_SELECTOR,
    READY_STEP,
    run_component_lectio_execution,
)
from generation.pipeline_dispatch import build_control_patch
from generation.contracts import GenerationInputForm as V3InputForm
from resource_specs.component_candidates import resolve_role_candidates
from tests.v3_blueprint.planning.test_intent_plan import SUBJECT_FIXTURES, _intent_plan_for_subject
from v3_blueprint.planning.canonical_plan import (
    SelectedComponent,
    SelectionValidationError,
    SelectorChoice,
    build_canonical_execution_plan,
    build_selector_prompt_context,
    heuristic_select_components,
)
from v3_blueprint.planning.component_selector import (
    run_lectio_semantic_selector,
    select_with_validation_and_repair,
)
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from v3_blueprint.planning.persistence import insert_step, persist_chunked_state
from v3_blueprint.planning.work_orders import compile_exact_work_orders
from v3_execution.models import (
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
)
from v3_execution.runtime.lesson_document import lesson_is_partial


INTEGRATION_PICKS = {
    "orient": ("hook-hero", "diagram-block"),
    "build": ("definition-card", "explanation-block"),
    "model": ("worked-example-card", "diagram-block"),
    "practice": ("practice-stack",),
    "close": ("summary-block", "quiz-check"),
}


def _forced_selector(picks: dict[str, tuple[str, ...]] = INTEGRATION_PICKS):
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


async def _fake_section_executor(work_order, emit, **kwargs):
    from contracts.lectio import get_section_field_for_component

    blocks = []
    for idx, component in enumerate(work_order.section.components):
        field = get_section_field_for_component(component.component_id) or component.component_id
        blocks.append(
            GeneratedComponentBlock(
                block_id=work_order.work_order_id,
                section_id=work_order.section.id,
                component_id=component.component_id,
                section_field=field,
                position=idx,
                data=valid_content_for(component.component_id, purpose="ok"),
                source_work_order_id=work_order.work_order_id,
            )
        )
    return blocks


async def _fake_question_executor(work_order, emit, **kwargs):
    component_id = work_order.component_id or "practice-stack"
    content = valid_content_for(component_id, purpose=work_order.purpose or "ok")
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
    if component_id in {"diagram-compare", "diagram-series"} and not frames:
        frames = [None, None]
    if frames:
        return [
            GeneratedVisualBlock(
                visual_id=work_order.visual.id,
                attaches_to=work_order.visual.attaches_to,
                mode=work_order.visual.mode,
                frame_index=idx,
                image_url=f"https://example.test/{component_id}-{idx}.png",
                caption=work_order.visual.purpose or "diagram",
                alt_text=work_order.visual.purpose or "diagram",
                source_work_order_id=work_order.work_order_id,
                component_id=component_id,
                parent_visual_id=work_order.visual.id,
            )
            for idx, _frame in enumerate(frames)
        ]
    return [
        GeneratedVisualBlock(
            visual_id=work_order.visual.id,
            attaches_to=work_order.visual.attaches_to,
            mode=work_order.visual.mode,
            image_url="https://example.test/diagram.png",
            caption=work_order.visual.purpose or "diagram",
            alt_text=work_order.visual.purpose or "diagram",
            source_work_order_id=work_order.work_order_id,
            component_id=component_id,
        )
    ]


async def _fake_answer_key_executor(work_order, emit, **kwargs):
    if work_order is None:
        return None
    return GeneratedAnswerKeyBlock(
        answer_key_id="ak-1",
        style=work_order.answer_key_plan.style,
        entries=[
            {
                "question_id": q.id,
                "question": q.purpose or q.id,
                "correct_answer": q.expected_answer or "4",
                "student_answer": q.expected_answer,
                "explanation": "",
            }
            for q in work_order.questions
        ],
        source_work_order_id=work_order.work_order_id,
    )


def _exec_kwargs(**overrides):
    return {
        "selector": _forced_selector(),
        "section_executor": _fake_section_executor,
        "question_executor": _fake_question_executor,
        "visual_executor": _fake_visual_executor,
        "answer_key_executor": _fake_answer_key_executor,
        **overrides,
    }


async def _seed_generation(generation_id: str) -> None:
    from core.database.session import async_session_factory

    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=f"user-{generation_id}",
                email=f"{generation_id}@example.com",
                name="Prelive",
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
            **build_control_patch("component_lectio"),
        },
    )


def test_s1_production_default_is_semantic_selector() -> None:
    assert DEFAULT_PRODUCTION_SELECTOR is run_lectio_semantic_selector
    assert DEFAULT_PRODUCTION_SELECTOR is not heuristic_select_components


@pytest.mark.asyncio
async def test_s1_production_invokes_injected_selector() -> None:
    gen_id = f"s1-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    calls: list[dict] = []

    def spy(context: dict) -> SelectorChoice:
        calls.append(context)
        return _forced_selector()(context)

    await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="S1",
        form=V3InputForm(
            grade_level="Grade 7",
            subject="Math",
            duration_minutes=45,
            topic="ratios",
            outcome="compare ratios",
        ),
        **_exec_kwargs(selector=spy),
    )
    assert calls
    assert all(section.components == [] for section in plan.sections)


def test_s2_selector_sees_only_narrowed_candidates() -> None:
    from v3_blueprint.planning.models import SectionPlan

    candidates = resolve_role_candidates("orient")
    section = SectionPlan(
        id="orient",
        title="Open",
        role="orient",
        purpose="hook",
        must_establish=["need"],
        visual_required=False,
        components=[],
    )
    context = build_selector_prompt_context(section=section, candidates=candidates)
    ids = {item["component_id"] for item in context["allowed_components"]}
    assert ids == set(candidates.candidates)
    assert "timeline-block" not in ids
    assert "prose" not in ids
    assert all("capabilities" in item for item in context["allowed_components"])


def test_s4_invalid_component_cannot_escape_validator() -> None:
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    def bad(_context):
        return SelectorChoice(
            components=[SelectedComponent(slug="timeline-block", purpose="nope", reason="x")]
        )

    with pytest.raises(SelectionValidationError):
        build_canonical_execution_plan(plan, selector=bad)


def test_s5_context_changes_selection() -> None:
    from v3_blueprint.planning.models import SectionPlan

    def contextual(context: dict) -> SelectorChoice:
        allowed = [c["component_id"] for c in context.get("allowed_components") or []]
        slug = allowed[0]
        if context.get("misconception_focus") and "pitfall-alert" in allowed:
            slug = "pitfall-alert"
        elif context.get("visual_required") and "diagram-block" in allowed:
            slug = "diagram-block"
        return SelectorChoice(
            components=[SelectedComponent(slug=slug, purpose="ctx", reason="ctx")]
        )

    pitfall_section = SectionPlan(
        id="model",
        title="Model",
        role="model",
        purpose="show method",
        misconception_focus=["M1"],
        visual_required=False,
        components=[],
    )
    visual_section = SectionPlan(
        id="orient",
        title="Orient",
        role="orient",
        purpose="open",
        misconception_focus=[],
        visual_required=True,
        components=[],
    )
    pitfall_ctx = build_selector_prompt_context(
        section=pitfall_section,
        candidates=resolve_role_candidates("model"),
    )
    visual_ctx = build_selector_prompt_context(
        section=visual_section,
        candidates=resolve_role_candidates("orient"),
    )
    assert contextual(pitfall_ctx).components[0].slug == "pitfall-alert"
    assert contextual(visual_ctx).components[0].slug == "diagram-block"
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    canonical, _ = build_canonical_execution_plan(plan, selector=contextual, lesson_context={"subject": "Math"})
    assert canonical.blocks


@pytest.mark.asyncio
async def test_selector_repair_then_still_invalid_raises() -> None:
    candidates = resolve_role_candidates("orient")

    async def always_bad(_payload):
        return SelectorChoice(
            components=[SelectedComponent(slug="timeline-block", purpose="x", reason="x")]
        )

    with pytest.raises(SelectionValidationError):
        await select_with_validation_and_repair(
            {"role": "orient", "allowed_components": [], "component_budget": {}},
            choose=always_bad,
            candidates=candidates,
        )


@pytest.mark.asyncio
async def test_i1_repeated_component_across_sections() -> None:
    gen_id = f"i1-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    document = await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="Dup diagram",
        form=V3InputForm(
            grade_level="Grade 7",
            subject="Math",
            duration_minutes=45,
            topic="ratios",
            outcome="compare",
        ),
        **_exec_kwargs(),
    )
    diagram_blocks = [
        (block_id, block)
        for block_id, block in document["blocks"].items()
        if block["component_id"] == "diagram-block"
    ]
    assert len(diagram_blocks) == 2
    ids = {block_id for block_id, _ in diagram_blocks}
    assert len(ids) == 2
    sections = {
        section["id"]
        for section in document["sections"]
        if any(bid in ids for bid in section["block_ids"])
    }
    assert "orient" in sections and "model" in sections


@pytest.mark.asyncio
async def test_i2_repeated_component_resume() -> None:
    gen_id = f"i2-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    canonical, _ = build_canonical_execution_plan(plan, selector=_forced_selector())
    orders = compile_exact_work_orders(canonical, include_visual=True)
    orient_diagram = next(
        o for o in orders if o.component_id == "diagram-block" and o.section_id == "orient"
    )
    model_diagram = next(
        o for o in orders if o.component_id == "diagram-block" and o.section_id == "model"
    )
    await insert_step(
        gen_id,
        part_id=orient_diagram.block_id,
        step=READY_STEP,
        payload={
            "block_id": orient_diagram.block_id,
            "plan_revision": canonical.plan_revision,
            "plan_hash": canonical.plan_hash,
            "payload": {"content": {"pre": True}, "component_id": "diagram-block"},
        },
    )
    visual_calls: list[str] = []

    async def visual_spy(work_order, emit, **kwargs):
        visual_calls.append(work_order.visual.id)
        return await _fake_visual_executor(work_order, emit, **kwargs)

    await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="resume diagrams",
        **_exec_kwargs(visual_executor=visual_spy),
    )
    assert orient_diagram.block_id not in visual_calls
    assert model_diagram.block_id in visual_calls


def test_i3_output_cannot_change_identity() -> None:
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    canonical, _ = build_canonical_execution_plan(plan, selector=_forced_selector())
    orders = compile_exact_work_orders(canonical, include_visual=True)
    first, second = orders[0], orders[1]
    spoofed = GeneratedComponentBlock(
        block_id=second.block_id,
        section_id=second.section_id,
        component_id=second.component_id,
        section_field="x",
        position=0,
        data={},
        source_work_order_id=second.work_order_id,
    )
    with pytest.raises(WorkOrderIdentityError):
        resolve_exact_order(spoofed, scoped_orders=[first])


@pytest.mark.asyncio
async def test_l1_lane_dispatcher_spies() -> None:
    gen_id = f"l1-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    lanes = {"content": 0, "items": 0, "visual": 0, "answer_key": 0}

    async def content(work_order, emit, **kwargs):
        lanes["content"] += 1
        return await _fake_section_executor(work_order, emit, **kwargs)

    async def items(work_order, emit, **kwargs):
        lanes["items"] += 1
        return await _fake_question_executor(work_order, emit, **kwargs)

    async def visual(work_order, emit, **kwargs):
        lanes["visual"] += 1
        return await _fake_visual_executor(work_order, emit, **kwargs)

    async def answers(work_order, emit, **kwargs):
        lanes["answer_key"] += 1
        return await _fake_answer_key_executor(work_order, emit, **kwargs)

    await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="lanes",
        **_exec_kwargs(
            section_executor=content,
            question_executor=items,
            visual_executor=visual,
            answer_key_executor=answers,
        ),
    )
    assert lanes["content"] >= 1
    assert lanes["items"] >= 1
    assert lanes["visual"] >= 1


@pytest.mark.asyncio
async def test_l2_item_never_reaches_generic_prose_writer() -> None:
    gen_id = f"l2-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    prose_components: list[str] = []

    async def content(work_order, emit, **kwargs):
        for component in work_order.section.components:
            prose_components.append(component.component_id)
            assert component.component_id != "practice-stack"
        return await _fake_section_executor(work_order, emit, **kwargs)

    await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="items",
        **_exec_kwargs(section_executor=content),
    )
    assert "practice-stack" not in prose_components


@pytest.mark.asyncio
async def test_l5_one_lane_failure_does_not_erase_siblings() -> None:
    gen_id = f"l5-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    attempts: dict[str, int] = {}

    async def visual(work_order, emit, **kwargs):
        vid = work_order.visual.id
        attempts[vid] = attempts.get(vid, 0) + 1
        if "model" in vid and attempts[vid] == 1:
            raise RuntimeError("visual render failed")
        return await _fake_visual_executor(work_order, emit, **kwargs)

    document = await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="siblings",
        form=V3InputForm(
            grade_level="Grade 7",
            subject="Math",
            duration_minutes=45,
            topic="ratios",
            outcome="compare",
        ),
        **_exec_kwargs(visual_executor=visual),
    )
    assert any(b["component_id"] == "explanation-block" for b in document["blocks"].values())
    assert any(b["component_id"] == "practice-stack" for b in document["blocks"].values())
    assert any(b["component_id"] == "diagram-block" for b in document["blocks"].values())


@pytest.mark.asyncio
async def test_d1_canonical_contract_fixture() -> None:
    gen_id = f"d1-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    document = await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="contract",
        form=V3InputForm(
            grade_level="Grade 7",
            subject="Math",
            duration_minutes=45,
            topic="ratios",
            outcome="compare",
        ),
        **_exec_kwargs(),
    )
    errors = validate_lesson_document(document)
    assert errors == []
    assert document["version"] == 1
    assert "plan_hash" not in document
    assert "pipeline" not in document


def test_d3_malformed_document_rejected() -> None:
    doc = {
        "version": 1,
        "id": "x",
        "title": "t",
        "subject": "Math",
        "preset_id": "default",
        "source": "generated",
        "source_generation_id": "x",
        "sections": [{"id": "orient", "block_ids": [], "title": "o", "position": 0}],
        "blocks": {},
        "media": {},
        "created_at": "t",
        "updated_at": "t",
    }
    errors = validate_lesson_document(doc)
    assert any("template_id" in error for error in errors)
    with pytest.raises(LessonDocumentValidationError):
        from contracts.lesson_document import assert_valid_lesson_document

        assert_valid_lesson_document(doc)


@pytest.mark.asyncio
async def test_r1_one_invalid_block_retries_only_that_block() -> None:
    gen_id = f"r1-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    counts: dict[str, int] = {}

    async def content(work_order, emit, **kwargs):
        cid = work_order.section.components[0].component_id
        counts[cid] = counts.get(cid, 0) + 1
        if cid == "explanation-block" and counts[cid] == 1:
            raise ValueError("lectio validation failed on explanation payload")
        return await _fake_section_executor(work_order, emit, **kwargs)

    await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="repair",
        **_exec_kwargs(section_executor=content),
    )
    assert counts.get("explanation-block") == 2
    assert counts.get("definition-card") == 1
    assert counts.get("hook-hero") == 1


@pytest.mark.asyncio
async def test_r2_component_identity_locked_during_repair() -> None:
    gen_id = f"r2-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    async def content(work_order, emit, **kwargs):
        return [
            GeneratedComponentBlock(
                block_id=work_order.work_order_id,
                section_id=work_order.section.id,
                component_id="callout-block",
                section_field="x",
                position=0,
                data={"headline": "nope"},
                source_work_order_id=work_order.work_order_id,
            )
        ]

    with pytest.raises(Exception):
        await run_component_lectio_execution(
            generation_id=gen_id,
            plan=plan,
            title="lock",
            **_exec_kwargs(section_executor=content),
        )


@pytest.mark.asyncio
async def test_r3_resume_only_failed_block() -> None:
    gen_id = f"r3-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    canonical, _ = build_canonical_execution_plan(plan, selector=_forced_selector())
    orders = compile_exact_work_orders(canonical, include_visual=True)
    content_orders = [o for o in orders if o.lane == "content"]
    assert len(content_orders) >= 3
    b1, b2, b3 = content_orders[0], content_orders[1], content_orders[2]
    for order in content_orders:
        if order is b2:
            await insert_step(
                gen_id,
                part_id=order.block_id,
                step="block_failed",
                payload={"error": {"message": "schema", "class": "component_repairable"}},
            )
        else:
            await insert_step(
                gen_id,
                part_id=order.block_id,
                step=READY_STEP,
                payload={
                    "block_id": order.block_id,
                    "plan_revision": canonical.plan_revision,
                    "plan_hash": canonical.plan_hash,
                    "payload": {"content": {"pre": True}, "component_id": order.component_id},
                },
            )
    executed: list[str] = []

    async def content(work_order, emit, **kwargs):
        executed.append(work_order.work_order_id)
        return await _fake_section_executor(work_order, emit, **kwargs)

    await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="r3",
        **_exec_kwargs(section_executor=content),
    )
    assert b2.work_order_id in executed
    assert b1.work_order_id not in executed
    assert b3.work_order_id not in executed


@pytest.mark.asyncio
async def test_r4_retry_exhaustion_blocks_without_complete() -> None:
    gen_id = f"r4-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    async def always_invalid(work_order, emit, **kwargs):
        raise ValueError("lectio validation failed forever")

    with pytest.raises(RuntimeError, match="lectio validation failed forever"):
        await run_component_lectio_execution(
            generation_id=gen_id,
            plan=plan,
            title="exhaust",
            **_exec_kwargs(section_executor=always_invalid),
        )
    from v3_blueprint.planning.persistence import load_chunked_state

    state = await load_chunked_state(gen_id)
    assert state.get("stage") == "assembly_blocked"


@pytest.mark.asyncio
async def test_phase7_architecture_integration() -> None:
    gen_id = f"int-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    assert all(not section.components for section in plan.sections)
    selector_calls: list[str] = []

    def spy(context: dict) -> SelectorChoice:
        selector_calls.append(str(context.get("role")))
        allowed = {c["component_id"] for c in context["allowed_components"]}
        choice = _forced_selector()(context)
        assert {item.slug for item in choice.components} <= allowed
        return choice

    document = await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="integration",
        form=V3InputForm(
            grade_level="Grade 7",
            subject="Math",
            duration_minutes=45,
            topic="ratios",
            outcome="compare ratios",
        ),
        **_exec_kwargs(selector=spy),
    )
    assert selector_calls
    errors = validate_lesson_document(document)
    assert errors == []
    diagrams = [b for b in document["blocks"].values() if b["component_id"] == "diagram-block"]
    assert len(diagrams) == 2
    lanes = compile_exact_work_orders(
        build_canonical_execution_plan(plan, selector=_forced_selector())[0],
        include_visual=True,
    )
    kinds = {order.lane for order in lanes}
    assert {"content", "items", "visual"} <= kinds
    from generation.component_lectio.service import reconstruct_checkpoint_store

    canonical, _ = build_canonical_execution_plan(plan, selector=_forced_selector(), generation_id=gen_id)
    store = await reconstruct_checkpoint_store(
        gen_id,
        plan_revision=canonical.plan_revision,
        plan_hash=canonical.plan_hash,
        desired_work=[o.block_id for o in compile_exact_work_orders(canonical, include_visual=True)],
    )
    assert lesson_is_partial(canonical, store) is False


@pytest.mark.asyncio
async def test_phase8_failure_injection_then_unrecoverable() -> None:
    gen_id = f"inj-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    content_attempts: dict[str, int] = {}
    item_attempts = {"n": 0}
    visual_attempts: dict[str, int] = {}

    async def content(work_order, emit, **kwargs):
        cid = work_order.section.components[0].component_id
        content_attempts[cid] = content_attempts.get(cid, 0) + 1
        if cid == "worked-example-card" and content_attempts[cid] == 1:
            raise ValueError("lectio validation failed malformed schema")
        return await _fake_section_executor(work_order, emit, **kwargs)

    async def items(work_order, emit, **kwargs):
        if work_order.section_id == "practice":
            item_attempts["n"] += 1
            if item_attempts["n"] == 1:
                raise TimeoutError("temporarily unavailable")
        return await _fake_question_executor(work_order, emit, **kwargs)

    async def visual(work_order, emit, **kwargs):
        vid = work_order.visual.id
        visual_attempts[vid] = visual_attempts.get(vid, 0) + 1
        if "model" in vid and visual_attempts[vid] == 1:
            raise RuntimeError("visual render failed")
        return await _fake_visual_executor(work_order, emit, **kwargs)

    document = await run_component_lectio_execution(
        generation_id=gen_id,
        plan=plan,
        title="inject",
        form=V3InputForm(
            grade_level="Grade 7",
            subject="Math",
            duration_minutes=45,
            topic="ratios",
            outcome="compare",
        ),
        **_exec_kwargs(
            section_executor=content,
            question_executor=items,
            visual_executor=visual,
        ),
    )
    assert validate_lesson_document(document) == []
    assert content_attempts.get("worked-example-card") == 2
    assert item_attempts["n"] == 2

    gen_fail = f"unrec-{uuid.uuid4().hex[:8]}"
    await _seed_generation(gen_fail)

    async def terminal_content(work_order, emit, **kwargs):
        cid = work_order.section.components[0].component_id
        if cid == "worked-example-card":
            raise TypeError("NoneType identity drift")
        return await _fake_section_executor(work_order, emit, **kwargs)

    with pytest.raises(RuntimeError):
        await run_component_lectio_execution(
            generation_id=gen_fail,
            plan=plan,
            title="unrecoverable",
            **_exec_kwargs(section_executor=terminal_content),
        )
    from generation.pipeline_dispatch import resolve_generation_pipeline
    from v3_blueprint.planning.persistence import load_chunked_state

    state = await load_chunked_state(gen_fail)
    assert state.get("stage") == "assembly_blocked"
    assert resolve_generation_pipeline(state, generation_id=gen_fail) == "component_lectio"
