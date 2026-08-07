from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from core.database.models import (
    PathLessonModel,
    TeachingPeriodModel,
    UnitGroupModel,
    UserModel,
)
from planning.models import (
    GroupVoice,
    ScheduleSuggestRequest,
    ScheduleWriteRequest,
    TeachingPeriodInput,
    UnitCreate,
    UnitGroupInput,
    UnitGroupsWriteRequest,
)
from planning.schedule import (
    groups_payload,
    selected_unit_groups,
    suggest_schedule,
    write_groups,
    write_schedule,
)
from planning.service import (
    StalePathMutationError,
    approve_path,
    create_unit,
    persist_path_plan,
)
from tests.planning.path_helpers import load_canonical_plan, load_legacy_path_plan


FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "handoff"
    / "fixtures"
    / "grade4-photosynthesis-path.json"
)


def _period_input(payload: dict) -> TeachingPeriodInput:
    return TeachingPeriodInput(
        title=payload["title"],
        lesson_ids=payload["lesson_ids"],
        planned_minutes=payload["planned_minutes"],
        teacher_note=payload["teacher_note"],
    )


async def _unit_with_approved_path(db_session, *, owner_id: str, email: str):
    db_session.add(UserModel(id=owner_id, email=email, name=owner_id))
    plan = load_canonical_plan("grade4-photosynthesis-path.json")
    legacy = load_legacy_path_plan("grade4-photosynthesis-path.json")
    unit = await create_unit(
        db_session,
        owner_id=owner_id,
        request=UnitCreate(
            title=legacy.unit or "Photosynthesis",
            topic=legacy.unit or "Photosynthesis",
            subject=legacy.subject or "Science",
            grade_level=legacy.grade_level or "Grade 4",
            destination_objective=legacy.destination_objective or "Destination",
            starting_knowledge=legacy.starting_knowledge,
        ),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lessons = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    return unit, version, lessons


async def test_schedule_suggest_and_write_preserve_the_path(db_session) -> None:
    _unit, version, lessons = await _unit_with_approved_path(
        db_session,
        owner_id="schedule-owner",
        email="schedule@example.invalid",
    )
    before = [
        (lesson.id, lesson.concept_id, lesson.objective, lesson.position, lesson.revision)
        for lesson in lessons
    ]
    suggestion = await suggest_schedule(
        db_session,
        version=version,
        request=ScheduleSuggestRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            period_count=3,
            minutes_per_period=55,
        ),
    )

    assert len(suggestion["periods"]) == 3
    assert [
        lesson_id
        for period in suggestion["periods"]
        for lesson_id in period["lesson_ids"]
    ] == [lesson.id for lesson in lessons]
    assert suggestion["suggestion"]["method"] == "ordered deterministic workload partition"
    assert list(await db_session.scalars(select(TeachingPeriodModel))) == []

    saved = await write_schedule(
        db_session,
        version=version,
        request=ScheduleWriteRequest(
            path_version_id=version.id,
            path_revision=version.revision,
            schedule_revision=version.schedule_revision,
            periods=[
                _period_input(period) for period in suggestion["periods"]
            ],
        ),
    )
    assert saved["schedule_revision"] == 2
    assert saved["feasibility"]["status"] in {"comfortable", "tight", "overloaded"}
    assert [
        lesson_id for period in saved["periods"] for lesson_id in period["lesson_ids"]
    ] == [lesson.id for lesson in lessons]

    with pytest.raises(StalePathMutationError, match="refresh"):
        await write_schedule(
            db_session,
            version=version,
            request=ScheduleWriteRequest(
                path_version_id=version.id,
                path_revision=version.revision,
                schedule_revision=1,
                periods=[
                    _period_input(period) for period in suggestion["periods"]
                ],
            ),
        )

    reversed_periods = [
        _period_input(period) for period in suggestion["periods"]
    ]
    reversed_periods[0].lesson_ids.reverse()
    with pytest.raises(ValueError, match="preserve path order"):
        await write_schedule(
            db_session,
            version=version,
            request=ScheduleWriteRequest(
                path_version_id=version.id,
                path_revision=version.revision,
                schedule_revision=version.schedule_revision,
                periods=reversed_periods,
            ),
        )

    refreshed = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    assert [
        (lesson.id, lesson.concept_id, lesson.objective, lesson.position, lesson.revision)
        for lesson in refreshed
    ] == before


async def test_unit_groups_are_server_declared_versioned_and_unit_owned(db_session) -> None:
    unit, _version, _lessons = await _unit_with_approved_path(
        db_session,
        owner_id="groups-owner",
        email="groups@example.invalid",
    )
    first = await write_groups(
        db_session,
        unit=unit,
        request=UnitGroupsWriteRequest(
            groups_revision=1,
            groups=[
                UnitGroupInput(
                    label="Supported",
                    profile="support",
                    description="More modelling and guided practice.",
                    voice=GroupVoice(register_name="simple", tone="encouraging"),
                ),
                UnitGroupInput(
                    label="Core",
                    profile="core",
                    description="The main class route.",
                    voice=GroupVoice(register_name="balanced", tone="neutral"),
                ),
            ],
        ),
    )
    support = first["groups"][0]
    assert support["toggle_profile"]["support_level"] == "high"
    assert "support.high.extra_modelling" in support["toggle_profile"]["declared_toggles"]
    assert first["groups_revision"] == 2

    second = await write_groups(
        db_session,
        unit=unit,
        request=UnitGroupsWriteRequest(
            groups_revision=2,
            groups=[
                UnitGroupInput(
                    id=support["id"],
                    label="Supported readers",
                    profile="support",
                    description="More modelling and accessible language.",
                    voice=GroupVoice(register_name="simple", tone="encouraging"),
                ),
                UnitGroupInput(
                    label="Extension",
                    profile="extension",
                    description="Independent transfer and application.",
                    voice=GroupVoice(register_name="formal", tone="direct"),
                ),
            ],
        ),
    )
    assert second["groups_revision"] == 3
    assert second["groups"][0]["id"] == support["id"]
    assert [group["profile"] for group in second["groups"]] == ["support", "extension"]
    all_groups = list(
        await db_session.scalars(
            select(UnitGroupModel).where(UnitGroupModel.unit_id == unit.id)
        )
    )
    assert len(all_groups) == 3
    assert next(group for group in all_groups if group.profile == "core").active is False

    selected = await selected_unit_groups(
        db_session,
        unit_id=unit.id,
        group_ids=[group["id"] for group in second["groups"]],
    )
    assert [group.profile for group in selected] == ["support", "extension"]
    assert (await groups_payload(db_session, unit=unit))["groups"] == second["groups"]

    with pytest.raises(StalePathMutationError, match="refresh"):
        await write_groups(
            db_session,
            unit=unit,
            request=UnitGroupsWriteRequest(groups_revision=1, groups=[]),
        )
    with pytest.raises(ValueError, match="owned by this unit"):
        await selected_unit_groups(
            db_session,
            unit_id="another-unit",
            group_ids=[support["id"]],
        )
