from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from core.database.models import PathLessonModel, UserModel
from planning.models import ShapeDeviationCreateRequest
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture
from planning.service import approve_path, create_unit, persist_path_plan
from planning.shapes import (
    decide_shape_deviation,
    lesson_shape_payload,
    request_shape_deviation,
)


FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "handoff"
    / "fixtures"
    / "grade4-photosynthesis-path.json"
)


async def _conceptual_lesson(db_session):
    db_session.add(UserModel(id="shape-owner", email="shape@example.invalid", name="Shape"))
    plan = load_canonical_plan("grade4-photosynthesis-path.json")
    unit = await create_unit(
        db_session,
        owner_id="shape-owner",
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(
            PathLessonModel.path_version_id == version.id,
            PathLessonModel.primary_knowledge_type == "conceptual",
        )
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None
    return unit, version, lesson


async def test_shape_preview_surfaces_overflow_as_a_blocking_issue(db_session) -> None:
    _unit, _version, lesson = await _conceptual_lesson(db_session)

    payload = await lesson_shape_payload(
        db_session,
        lesson=lesson,
        lesson_mode="first_exposure",
        misconception_count=2,
    )

    assert payload["can_prepare"] is False
    assert {issue["code"] for issue in payload["blocking_issues"]} == {
        "variant_slot_overflow"
    }
    support = next(item for item in payload["variants"] if item["group_profile"] == "support")
    assert any(
        diff["toggle_id"] == "misconception.confront_per_belief"
        and diff["operation"] == "repeat"
        for diff in support["structural_diff"]
    )


async def test_deviation_requires_decision_and_persists_in_shape(db_session) -> None:
    _unit, version, lesson = await _conceptual_lesson(db_session)
    original_revision = lesson.revision
    deviation = await request_shape_deviation(
        db_session,
        lesson=lesson,
        request=ShapeDeviationCreateRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            lesson_revision=lesson.revision,
            lesson_mode="first_exposure",
            operation="remove",
            target_slot="orient",
            reason="This group already completed the orientation activity.",
        ),
    )
    pending = await lesson_shape_payload(
        db_session,
        lesson=lesson,
        lesson_mode="first_exposure",
        misconception_count=2,
    )
    assert pending["can_prepare"] is False
    assert pending["deviations"][0]["status"] == "pending_teacher"
    assert lesson.revision == original_revision

    await decide_shape_deviation(
        db_session,
        lesson=lesson,
        deviation_id=deviation.id,
        approved=True,
        decided_by="shape-owner",
    )
    approved = await lesson_shape_payload(
        db_session,
        lesson=lesson,
        lesson_mode="first_exposure",
        misconception_count=2,
    )
    assert approved["can_prepare"] is True
    assert approved["deviations"][0]["status"] == "approved"
    assert lesson.revision == original_revision + 1
    assert approved["canonical"]["slots"][0]["slot_id"] != "orient"
    assert all(
        variant["slots"][0]["slot_id"] != "orient"
        for variant in approved["variants"]
    )
