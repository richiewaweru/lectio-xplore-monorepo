"""Append-only generation_steps: fold + simultaneous inserts."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from core.database.models import GenerationModel, GenerationStepModel, UserModel
from v3_blueprint.planning.persistence import (
    fold,
    insert_step,
    load_chunked_state,
    persist_chunked_state,
    persist_section_brief,
)
from v3_blueprint.planning.models import ComponentBrief, SectionBrief


async def _seed_generation(session, generation_id: str) -> None:
    user_id = f"user-{generation_id}"
    session.add(
        UserModel(
            id=user_id,
            email=f"{user_id}@example.com",
            name="Test",
        )
    )
    session.add(
        GenerationModel(
            id=generation_id,
            user_id=user_id,
            subject="Science",
            requested_template_id="guided-concept-path",
            requested_preset_id="default",
            status="running",
        )
    )
    await session.commit()
    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage2_running",
            "section_briefs": {"orient": None, "explain": None},
            "failed_sections": [],
            "structural_plan": {"sections": []},
            "context": {},
        },
        session=session,
    )
    await session.commit()


@pytest.mark.asyncio
async def test_fold_builds_section_briefs_from_rows() -> None:
    rows = [
        GenerationStepModel(
            id="1",
            generation_id="g",
            part_id="orient",
            variant_id="everyone",
            step="brief",
            kind="lesson",
            payload={"section_id": "orient", "components": []},
        ),
        GenerationStepModel(
            id="2",
            generation_id="g",
            part_id="orient",
            variant_id="everyone",
            step="prose",
            kind="lesson",
            payload={"blocks": [{"type": "paragraph"}]},
        ),
    ]
    folded = fold(rows)
    assert folded["section_briefs"]["orient"]["section_id"] == "orient"
    assert folded["part_prose"]["orient"]["blocks"][0]["type"] == "paragraph"
    assert folded["part_questions"] == {}


@pytest.mark.asyncio
async def test_simultaneous_inserts_both_survive(db_session_factory) -> None:
    generation_id = f"gen-{uuid.uuid4()}"
    async with db_session_factory() as session:
        await _seed_generation(session, generation_id)

    async def _write(part_id: str) -> None:
        async with db_session_factory() as session:
            await insert_step(
                generation_id,
                part_id=part_id,
                step="brief",
                payload={"section_id": part_id, "components": []},
                session=session,
            )
            await session.commit()

    await asyncio.gather(_write("orient"), _write("explain"))

    async with db_session_factory() as session:
        result = await session.execute(
            select(GenerationStepModel).where(
                GenerationStepModel.generation_id == generation_id
            )
        )
        rows = list(result.scalars().all())
    assert len(rows) == 2
    parts = {row.part_id for row in rows}
    assert parts == {"orient", "explain"}


@pytest.mark.asyncio
async def test_persist_section_brief_inserts_step_and_fold_loads(
    db_session,
) -> None:
    generation_id = f"gen-{uuid.uuid4()}"
    await _seed_generation(db_session, generation_id)

    brief = SectionBrief(
        section_id="orient",
        components=[
            ComponentBrief(component_id="hook-hero", content_intent="Hook learners")
        ],
        visual_strategy=None,
    )
    await persist_section_brief(generation_id, brief, session=db_session)
    await db_session.commit()

    state = await load_chunked_state(generation_id, session=db_session)
    assert state["section_briefs"]["orient"]["section_id"] == "orient"
    assert state["section_briefs"]["orient"]["components"][0]["component_id"] == "hook-hero"
    assert state["stage"] == "section_orient_complete"

@pytest.mark.asyncio
async def test_resume_rebuilds_only_missing_brief_steps(db_session) -> None:
    from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
    from v3_blueprint.planning.models import (
        AnchorSpec,
        ComponentSlot,
        LessonIntent,
        SectionPlan,
        StructuralPlan,
    )
    from v3_blueprint.planning.persistence import resume_stage2
    from unittest.mock import AsyncMock, patch

    generation_id = f"gen-{uuid.uuid4()}"
    await _seed_generation(db_session, generation_id)
    plan = StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(goal="Learn.", structure_rationale="Concrete."),
        anchor=AnchorSpec(example="e", reuse_scope="all sections"),
        prior_knowledge=[],
        sections=[
            SectionPlan(
                id="orient",
                title="Orient",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="hook")],
            ),
            SectionPlan(
                id="explain",
                title="Explain",
                role="explain",
                visual_required=False,
                transition_note="Build after orient.",
                components=[ComponentSlot(slug="definition-card", purpose="define")],
            ),
        ],
        question_plan=[],
        answer_key_style="brief_explanations",
    )
    signals = V3SignalSummary(
        topic="T",
        subtopic="S",
        prior_knowledge=[],
        learner_needs=[],
        teacher_goal="g",
        inferred_lesson_mode="first_exposure",
        lesson_mode_confidence="high",
    )
    form = V3InputForm(
        grade_level="Grade 7",
        subject="Science",
        duration_minutes=45,
        resource_type="lesson",
        topic="T",
        subtopics=[],
        prior_knowledge="",
        outcome="o",
        struggle="",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
        free_text="",
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage2_running",
            "structural_plan": plan.model_dump(mode="json"),
            "section_briefs": {"orient": None, "explain": None},
            "failed_sections": [],
            "context": {
                "signals": signals.model_dump(mode="json"),
                "form": form.model_dump(mode="json"),
                "resource_spec": {},
            },
        },
        session=db_session,
    )
    await persist_section_brief(
        generation_id,
        SectionBrief(
            section_id="orient",
            components=[
                ComponentBrief(component_id="hook-hero", content_intent="hook")
            ],
        ),
        session=db_session,
    )
    await db_session.commit()

    called: list[str] = []

    async def fake_run(**kwargs):  # noqa: ANN003
        section = kwargs["section"]
        called.append(section.id)
        return SectionBrief(
            section_id=section.id,
            components=[ComponentBrief(component_id="x", content_intent="y")],
        )

    with patch(
        "v3_blueprint.planning.retry._run_section_with_retry",
        new=AsyncMock(side_effect=fake_run),
    ):
        briefs = await resume_stage2(generation_id, session=db_session)

    assert called == ["explain"]
    assert {b.section_id for b in briefs} == {"orient", "explain"}
