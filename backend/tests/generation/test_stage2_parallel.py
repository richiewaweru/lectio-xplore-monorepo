from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    SectionBrief,
    SectionPlan,
    StructuralPlan,
)
from v3_blueprint.planning.persistence import resume_stage2
from v3_blueprint.planning.retry import run_stage2
from v3_blueprint.planning.section_expander import build_stage2_user_message


def _plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(goal="Learn fractions.", structure_rationale="Concrete first."),
        anchor=AnchorSpec(example="fraction strips", reuse_scope="all sections"),
        prior_knowledge=[],
        sections=[
            SectionPlan(
                id=section_id,
                title=section_id.title(),
                role="explain",
                visual_required=False,
                transition_note=(
                    None if section_id == "one" else f"Build after {section_id} prior work."
                ),
                components=[ComponentSlot(slug="hook-hero", purpose="Teach the concept")],
            )
            for section_id in ("one", "two", "three")
        ],
        question_plan=[],
        answer_key_style="brief_explanations",
    )


def _signals() -> V3SignalSummary:
    return V3SignalSummary(
        topic="Fractions",
        subtopic="Equivalent fractions",
        prior_knowledge=[],
        learner_needs=[],
        teacher_goal="Build confidence",
        inferred_lesson_mode="first_exposure",
        lesson_mode_confidence="high",
    )


def _form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 6",
        subject="Math",
        duration_minutes=45,
        resource_type="lesson",
        topic="Equivalent fractions",
        subtopics=[],
        prior_knowledge="",
        outcome="Identify equivalent fractions.",
        struggle="",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
        free_text="",
    )


def _brief(section_id: str, *, failed: bool = False) -> SectionBrief:
    brief = SectionBrief(
        section_id=section_id,
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    if failed:
        brief._failed = True
        brief._errors = ["retry exhausted"]
    return brief


async def _run(plan: StructuralPlan) -> list[SectionBrief]:
    return await run_stage2(
        plan,
        _signals(),
        _form(),
        {},
        generation_id="generation-1",
    )


@pytest.mark.asyncio
async def test_parallel_stage2_returns_briefs_in_plan_order_when_tasks_finish_out_of_order() -> None:
    plan = _plan()

    async def fake_run(**kwargs):  # noqa: ANN003
        await asyncio.sleep({"one": 0, "two": 0.02, "three": 0.01}[kwargs["section"].id])
        return _brief(kwargs["section"].id)

    with (
        patch("v3_blueprint.planning.retry._run_section_with_retry", new=AsyncMock(side_effect=fake_run)),
        patch("v3_blueprint.planning.retry.persist_section_brief", new=AsyncMock()),
    ):
        briefs = await _run(plan)

    assert [brief.section_id for brief in briefs] == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_parallel_stage2_dispatches_all_sections_in_one_wave_without_prior_briefs() -> None:
    plan = _plan()
    received_prior_briefs: dict[str, list[SectionBrief]] = {}
    started = asyncio.Event()
    release = asyncio.Event()
    in_flight = 0
    max_in_flight = 0

    async def fake_run(**kwargs):  # noqa: ANN003
        nonlocal in_flight, max_in_flight
        received_prior_briefs[kwargs["section"].id] = kwargs["prior_briefs"]
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        if in_flight == 3:
            started.set()
        await release.wait()
        in_flight -= 1
        return _brief(kwargs["section"].id)

    with (
        patch("v3_blueprint.planning.retry._run_section_with_retry", new=AsyncMock(side_effect=fake_run)),
        patch("v3_blueprint.planning.retry.persist_section_brief", new=AsyncMock()),
    ):
        task = asyncio.create_task(_run(plan))
        await asyncio.wait_for(started.wait(), timeout=1.0)
        assert max_in_flight == 3
        release.set()
        await task

    assert received_prior_briefs == {"one": [], "two": [], "three": []}


@pytest.mark.asyncio
async def test_parallel_stage2_user_message_uses_plan_derived_continuity() -> None:
    plan = _plan()
    message = build_stage2_user_message(
        plan,
        plan.sections[1],
        prior_briefs=[],
        component_cards={},
        form=_form(),
    )
    assert "PLAN CONTINUITY" in message
    assert "fraction strips" in message
    assert "Build after two prior work." in message
    assert "PRIOR SECTION BRIEFS" not in message


@pytest.mark.asyncio
async def test_parallel_stage2_isolates_section_exception_including_first() -> None:
    plan = _plan()
    events: list[tuple[str, dict]] = []
    persist_brief = AsyncMock()

    async def fake_run(**kwargs):  # noqa: ANN003
        section_id = kwargs["section"].id
        if section_id == "one":
            raise RuntimeError("first boom")
        if section_id == "two":
            raise RuntimeError("boom")
        return _brief(section_id)

    async def emit_event(name: str, payload: dict) -> None:
        events.append((name, payload))

    with (
        patch("v3_blueprint.planning.retry._run_section_with_retry", new=AsyncMock(side_effect=fake_run)),
        patch("v3_blueprint.planning.retry.persist_section_brief", new=persist_brief),
    ):
        briefs = await run_stage2(
            plan,
            _signals(),
            _form(),
            {},
            generation_id="generation-1",
            emit_event=emit_event,
        )

    assert [brief.section_id for brief in briefs] == ["one", "two", "three"]
    assert briefs[0]._failed is True
    assert "RuntimeError" in briefs[0]._errors[0]
    assert briefs[1]._failed is True
    assert not getattr(briefs[2], "_failed", False)
    failed_ids = {
        payload["section_id"]
        for name, payload in events
        if name == "stage2_section_failed"
    }
    assert failed_ids == {"one", "two"}
    complete = next(payload for name, payload in events if name == "stage2_complete")
    assert set(complete["failed_sections"]) == {"one", "two"}


@pytest.mark.asyncio
async def test_stage2_uses_serial_invocation_order_when_parallel_flag_is_false(monkeypatch) -> None:  # noqa: ANN001
    plan = _plan()
    call_order: list[str] = []
    monkeypatch.setenv("V3_STAGE2_PARALLEL", "false")

    async def fake_run(**kwargs):  # noqa: ANN003
        call_order.append(kwargs["section"].id)
        return _brief(kwargs["section"].id)

    with (
        patch("v3_blueprint.planning.retry._run_section_with_retry", new=AsyncMock(side_effect=fake_run)),
        patch("v3_blueprint.planning.retry.persist_section_brief", new=AsyncMock()),
    ):
        await _run(plan)

    assert call_order == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_parallel_stage2_persists_each_brief_once() -> None:
    plan = _plan()
    persist_brief = AsyncMock()

    async def fake_run(**kwargs):  # noqa: ANN003
        await asyncio.sleep({"one": 0, "two": 0.02, "three": 0.01}[kwargs["section"].id])
        return _brief(kwargs["section"].id)

    with (
        patch("v3_blueprint.planning.retry._run_section_with_retry", new=AsyncMock(side_effect=fake_run)),
        patch("v3_blueprint.planning.retry.persist_section_brief", new=persist_brief),
    ):
        await _run(plan)

    assert persist_brief.await_count == 3
    assert {call.args[1].section_id for call in persist_brief.await_args_list} == {"one", "two", "three"}


@pytest.mark.asyncio
async def test_resume_stage2_isolates_fan_out_exception() -> None:
    plan = _plan()
    persisted_anchor = _brief("one")
    state = {
        "structural_plan": plan.model_dump(mode="json"),
        "section_briefs": {
            "one": persisted_anchor.model_dump(mode="json"),
            "two": None,
            "three": None,
        },
        "context": {
            "signals": _signals().model_dump(mode="json"),
            "form": _form().model_dump(mode="json"),
            "resource_spec": {},
        },
    }
    events: list[tuple[str, dict]] = []
    persist_brief = AsyncMock()

    async def fake_run(**kwargs):  # noqa: ANN003
        section_id = kwargs["section"].id
        assert kwargs["prior_briefs"] == []
        if section_id == "two":
            raise RuntimeError("boom")
        return _brief(section_id)

    async def emit_event(name: str, payload: dict) -> None:
        events.append((name, payload))

    with (
        patch("v3_blueprint.planning.persistence.load_chunked_state", new=AsyncMock(return_value=state)),
        patch("v3_blueprint.planning.persistence.persist_section_brief", new=persist_brief),
        patch("v3_blueprint.planning.retry._run_section_with_retry", new=AsyncMock(side_effect=fake_run)),
    ):
        briefs = await resume_stage2(
            "generation-1",
            session=AsyncMock(),
            emit_event=emit_event,
        )

    assert [brief.section_id for brief in briefs] == ["one", "two", "three"]
    assert briefs[1]._failed is True
    assert "RuntimeError" in briefs[1]._errors[0]
    assert not getattr(briefs[2], "_failed", False)
    failed = next(payload for name, payload in events if name == "stage2_section_failed")
    assert failed["section_id"] == "two"
    complete = next(payload for name, payload in events if name == "stage2_complete")
    assert complete["failed_sections"] == ["two"]
