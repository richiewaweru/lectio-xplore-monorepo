"""RUN_03 gate: fixture page-block planning without component selector."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from core.database.models import PathLessonModel, UserModel
from planning import page_blocks
from planning.bridge import prepare_path_lesson
from planning.models import PathPlan, PrepareLessonRequest, UnitCreate
from planning.page_blocks import (
    candidates_for_slot,
    page_document_scope_matches,
    plan_conceptual_first_exposure_blocks,
    validate_block_plan_against_candidates,
)
from planning.service import approve_path, create_unit, persist_path_plan
from tests.planning.test_path_bridge import _fake_structural_planner

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "handoff"
    / "fixtures"
    / "grade4-photosynthesis-path.json"
)


@pytest.mark.asyncio
async def test_fixture_plans_all_conceptual_first_exposure_slots() -> None:
    plans = await plan_conceptual_first_exposure_blocks(allow_paid=False)
    assert set(plans) == set(page_blocks.CONCEPTUAL_FIRST_EXPOSURE_SLOTS)
    for slot_id, plan in plans.items():
        assert plan.blocks, slot_id
        candidates = candidates_for_slot(slot_id)
        validate_block_plan_against_candidates(plan, candidates)
        for index, block in enumerate(plan.blocks):
            assert block.position == index
            assert block.object != "heading"
            assert block.evidence.strip()
            assert block.brief.strip()


@pytest.mark.asyncio
async def test_paid_without_planner_raises() -> None:
    with pytest.raises(page_blocks.PageBlockPlanError, match="Paid"):
        await page_blocks.plan_section_blocks(slot_id="orient", allow_paid=True)


def test_scope_matches_first_slice_only() -> None:
    assert page_document_scope_matches(
        knowledge_type="conceptual", lesson_mode="first_exposure"
    )
    assert not page_document_scope_matches(
        knowledge_type="procedural", lesson_mode="first_exposure"
    )


@pytest.mark.asyncio
async def test_prepare_path_lesson_v2_skips_component_selector(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "core.config.settings.xplore_page_documents_enabled",
        True,
    )
    selector = AsyncMock()
    user = UserModel(id="page-bridge-owner", email="page-bridge@example.invalid", name="Page")
    db_session.add(user)
    plan = PathPlan.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=UnitCreate(
            title=plan.unit or "Photosynthesis",
            topic=plan.unit or "Photosynthesis",
            subject=plan.subject or "Science",
            grade_level=plan.grade_level or "Grade 4",
            destination_objective=plan.destination_objective or "Destination",
            starting_knowledge=plan.starting_knowledge,
        ),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lessons = (
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    ).all()
    lesson = next(
        (row for row in lessons if row.primary_knowledge_type == "conceptual"),
        None,
    )
    assert lesson is not None

    _response, structural_plan = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=_fake_structural_planner,
        component_selector=selector,
    )

    selector.assert_not_called()
    assert structural_plan.document_contract_version == 2
    for section in structural_plan.sections:
        if section.role in page_blocks.CONCEPTUAL_FIRST_EXPOSURE_SLOTS:
            assert section.blocks
            assert section.components == []
