from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    PathLessonModel,
    PathVersionModel,
    TeachingPeriodLessonModel,
    TeachingPeriodModel,
    UnitGroupModel,
    UnitModel,
)
from planning.models import (
    ScheduleSuggestRequest,
    ScheduleWriteRequest,
    TeachingPeriodInput,
    UnitGroupsWriteRequest,
)
from planning.service import StalePathMutationError


GROUP_TOGGLE_PROFILES: dict[str, dict[str, Any]] = {
    "support": {
        "support_level": "high",
        "declared_toggles": [
            "support.high.extra_modelling",
            "support.high.drop_independent",
            "support.high.extra_contrast",
        ],
    },
    "core": {"support_level": "medium", "declared_toggles": []},
    "extension": {
        "support_level": "low",
        "declared_toggles": [
            "support.low.add_transfer",
            "support.low.drop_orient",
        ],
    },
}

_ESTIMATED_MINUTES = {
    "factual": 25,
    "conceptual": 40,
    "procedural": 45,
    "evaluative": 45,
}


def _estimated_lesson_minutes(lesson: PathLessonModel) -> int:
    baseline = _ESTIMATED_MINUTES.get(lesson.primary_knowledge_type, 40)
    extra_capabilities = max(0, len(lesson.must_establish or []) - 1)
    return baseline + min(extra_capabilities * 5, 15)


async def _active_lessons(
    session: AsyncSession,
    *,
    version_id: str,
) -> list[PathLessonModel]:
    return list(
        await session.scalars(
            select(PathLessonModel)
            .where(
                PathLessonModel.path_version_id == version_id,
                PathLessonModel.skipped.is_(False),
            )
            .order_by(PathLessonModel.position)
        )
    )


def _period_feasibility(
    period: TeachingPeriodInput | TeachingPeriodModel,
    lessons: Sequence[PathLessonModel],
) -> dict[str, Any]:
    estimated = sum(_estimated_lesson_minutes(lesson) for lesson in lessons)
    planned = period.planned_minutes
    if planned is None:
        status = "unplanned"
        delta = None
    else:
        delta = planned - estimated
        status = "comfortable" if planned >= estimated * 1.15 else (
            "tight" if planned >= estimated else "overloaded"
        )
    return {
        "estimated_minutes": estimated,
        "planned_minutes": planned,
        "delta_minutes": delta,
        "status": status,
    }


def _schedule_feasibility(periods: list[dict[str, Any]]) -> dict[str, Any]:
    estimated = sum(period["feasibility"]["estimated_minutes"] for period in periods)
    planned_values = [period["planned_minutes"] for period in periods]
    if any(value is None for value in planned_values):
        planned = None
        status = "unplanned"
        delta = None
    else:
        planned = sum(int(value) for value in planned_values)
        delta = planned - estimated
        status = "comfortable" if planned >= estimated * 1.15 else (
            "tight" if planned >= estimated else "overloaded"
        )
    return {
        "estimated_minutes": estimated,
        "planned_minutes": planned,
        "delta_minutes": delta,
        "status": status,
    }


async def schedule_payload(
    session: AsyncSession,
    *,
    version: PathVersionModel,
) -> dict[str, Any]:
    lessons = await _active_lessons(session, version_id=version.id)
    lesson_by_id = {lesson.id: lesson for lesson in lessons}
    periods = list(
        await session.scalars(
            select(TeachingPeriodModel)
            .where(TeachingPeriodModel.path_version_id == version.id)
            .order_by(TeachingPeriodModel.position)
        )
    )
    period_ids = [period.id for period in periods]
    links = (
        list(
            await session.scalars(
                select(TeachingPeriodLessonModel)
                .where(TeachingPeriodLessonModel.teaching_period_id.in_(period_ids))
                .order_by(
                    TeachingPeriodLessonModel.teaching_period_id,
                    TeachingPeriodLessonModel.position,
                )
            )
        )
        if period_ids
        else []
    )
    links_by_period: dict[str, list[TeachingPeriodLessonModel]] = {
        period_id: [] for period_id in period_ids
    }
    for link in links:
        links_by_period[link.teaching_period_id].append(link)

    payload_periods: list[dict[str, Any]] = []
    for period in periods:
        period_lessons = [
            lesson_by_id[link.path_lesson_id]
            for link in links_by_period[period.id]
            if link.path_lesson_id in lesson_by_id
        ]
        payload_periods.append(
            {
                "id": period.id,
                "title": period.title,
                "position": period.position,
                "planned_minutes": period.planned_minutes,
                "teacher_note": period.teacher_note,
                "lesson_ids": [lesson.id for lesson in period_lessons],
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "concept_id": lesson.concept_id,
                        "objective": lesson.objective,
                        "path_position": lesson.position,
                        "estimated_minutes": _estimated_lesson_minutes(lesson),
                    }
                    for lesson in period_lessons
                ],
                "feasibility": _period_feasibility(period, period_lessons),
            }
        )
    return {
        "path_version_id": version.id,
        "path_revision": version.revision,
        "schedule_revision": version.schedule_revision,
        "periods": payload_periods,
        "feasibility": _schedule_feasibility(payload_periods),
    }


def _validate_period_order(
    periods: Sequence[TeachingPeriodInput],
    lessons: Sequence[PathLessonModel],
) -> None:
    expected = [lesson.id for lesson in lessons]
    actual = [lesson_id for period in periods for lesson_id in period.lesson_ids]
    if actual != expected:
        raise ValueError(
            "A schedule must contain every active path lesson exactly once and preserve path order"
        )


async def write_schedule(
    session: AsyncSession,
    *,
    version: PathVersionModel,
    request: ScheduleWriteRequest,
) -> dict[str, Any]:
    if version.status != "approved":
        raise ValueError("Only an approved path can be scheduled")
    if request.schedule_revision != version.schedule_revision:
        raise StalePathMutationError(
            "This schedule changed after it was loaded; refresh before saving"
        )
    lessons = await _active_lessons(session, version_id=version.id)
    if not lessons:
        raise ValueError("The active path has no schedulable lessons")
    _validate_period_order(request.periods, lessons)

    existing_ids = list(
        await session.scalars(
            select(TeachingPeriodModel.id).where(
                TeachingPeriodModel.path_version_id == version.id
            )
        )
    )
    if existing_ids:
        await session.execute(
            delete(TeachingPeriodLessonModel).where(
                TeachingPeriodLessonModel.teaching_period_id.in_(existing_ids)
            )
        )
        await session.execute(
            delete(TeachingPeriodModel).where(TeachingPeriodModel.id.in_(existing_ids))
        )
        await session.flush()

    for period_position, requested in enumerate(request.periods, start=1):
        period = TeachingPeriodModel(
            id=str(uuid.uuid4()),
            path_version_id=version.id,
            title=requested.title.strip(),
            position=period_position,
            planned_minutes=requested.planned_minutes,
            teacher_note=(requested.teacher_note or "").strip() or None,
        )
        session.add(period)
        for lesson_position, lesson_id in enumerate(requested.lesson_ids, start=1):
            session.add(
                TeachingPeriodLessonModel(
                    teaching_period_id=period.id,
                    path_lesson_id=lesson_id,
                    position=lesson_position,
                )
            )
    version.schedule_revision += 1
    await session.flush()
    return await schedule_payload(session, version=version)


async def suggest_schedule(
    session: AsyncSession,
    *,
    version: PathVersionModel,
    request: ScheduleSuggestRequest,
) -> dict[str, Any]:
    if version.status != "approved":
        raise ValueError("Only an approved path can be scheduled")
    lessons = await _active_lessons(session, version_id=version.id)
    if request.period_count > len(lessons):
        raise ValueError("A schedule cannot have more periods than active path lessons")

    total = sum(_estimated_lesson_minutes(lesson) for lesson in lessons)
    target = total / request.period_count
    groups: list[list[PathLessonModel]] = []
    current: list[PathLessonModel] = []
    current_minutes = 0
    for index, lesson in enumerate(lessons):
        current.append(lesson)
        current_minutes += _estimated_lesson_minutes(lesson)
        remaining_lessons = len(lessons) - index - 1
        remaining_groups = request.period_count - len(groups) - 1
        if remaining_groups > 0 and (
            current_minutes >= target or remaining_lessons == remaining_groups
        ):
            groups.append(current)
            current = []
            current_minutes = 0
    if current:
        groups.append(current)

    suggested = [
        TeachingPeriodInput(
            title=f"Period {index}",
            lesson_ids=[lesson.id for lesson in group],
            planned_minutes=request.minutes_per_period,
        )
        for index, group in enumerate(groups, start=1)
    ]
    lesson_by_id = {lesson.id: lesson for lesson in lessons}
    payload_periods = [
        {
            "id": None,
            "title": period.title,
            "position": index,
            "planned_minutes": period.planned_minutes,
            "teacher_note": None,
            "lesson_ids": period.lesson_ids,
            "lessons": [
                {
                    "id": lesson_by_id[lesson_id].id,
                    "title": lesson_by_id[lesson_id].title,
                    "concept_id": lesson_by_id[lesson_id].concept_id,
                    "objective": lesson_by_id[lesson_id].objective,
                    "path_position": lesson_by_id[lesson_id].position,
                    "estimated_minutes": _estimated_lesson_minutes(lesson_by_id[lesson_id]),
                }
                for lesson_id in period.lesson_ids
            ],
            "feasibility": _period_feasibility(
                period,
                [lesson_by_id[lesson_id] for lesson_id in period.lesson_ids],
            ),
        }
        for index, period in enumerate(suggested, start=1)
    ]
    return {
        "path_version_id": version.id,
        "path_revision": version.revision,
        "schedule_revision": version.schedule_revision,
        "periods": payload_periods,
        "feasibility": _schedule_feasibility(payload_periods),
        "suggestion": {
            "period_count": request.period_count,
            "minutes_per_period": request.minutes_per_period,
            "method": "ordered deterministic workload partition",
        },
    }


async def groups_payload(
    session: AsyncSession,
    *,
    unit: UnitModel,
) -> dict[str, Any]:
    groups = list(
        await session.scalars(
            select(UnitGroupModel)
            .where(UnitGroupModel.unit_id == unit.id, UnitGroupModel.active.is_(True))
            .order_by(UnitGroupModel.position)
        )
    )
    return {
        "unit_id": unit.id,
        "groups_revision": unit.groups_revision,
        "groups": [
            {
                "id": group.id,
                "label": group.label,
                "profile": group.profile,
                "description": group.description,
                "toggle_profile": group.toggle_profile,
                "voice": group.voice,
                "position": group.position,
                "revision": group.revision,
            }
            for group in groups
        ],
    }


async def write_groups(
    session: AsyncSession,
    *,
    unit: UnitModel,
    request: UnitGroupsWriteRequest,
) -> dict[str, Any]:
    if request.groups_revision != unit.groups_revision:
        raise StalePathMutationError(
            "These unit groups changed after they were loaded; refresh before saving"
        )
    labels = [group.label.strip().casefold() for group in request.groups]
    profiles = [group.profile for group in request.groups]
    if len(labels) != len(set(labels)):
        raise ValueError("Unit group labels must be unique")
    if len(profiles) != len(set(profiles)):
        raise ValueError("A unit may define at most one group for each structural profile")

    existing = list(
        await session.scalars(
            select(UnitGroupModel).where(UnitGroupModel.unit_id == unit.id)
        )
    )
    by_profile = {group.profile: group for group in existing}
    for group in existing:
        group.active = False
    for position, requested in enumerate(request.groups, start=1):
        model = by_profile.get(requested.profile)
        if requested.id is not None and (model is None or model.id != requested.id):
            raise ValueError("A unit group ID cannot be reassigned to another profile")
        if model is None:
            model = UnitGroupModel(
                id=str(uuid.uuid4()),
                unit_id=unit.id,
                profile=requested.profile,
                label=requested.label.strip(),
                description=requested.description.strip(),
                toggle_profile=GROUP_TOGGLE_PROFILES[requested.profile],
                voice=requested.voice.model_dump(mode="json"),
                position=position,
                active=True,
                revision=1,
            )
            session.add(model)
        else:
            model.label = requested.label.strip()
            model.description = requested.description.strip()
            model.toggle_profile = GROUP_TOGGLE_PROFILES[requested.profile]
            model.voice = requested.voice.model_dump(mode="json")
            model.position = position
            model.active = True
            model.revision += 1
    unit.groups_revision += 1
    await session.flush()
    return await groups_payload(session, unit=unit)


async def selected_unit_groups(
    session: AsyncSession,
    *,
    unit_id: str,
    group_ids: Sequence[str],
) -> list[UnitGroupModel]:
    if not group_ids:
        return []
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("Selected unit groups must be unique")
    groups = list(
        await session.scalars(
            select(UnitGroupModel)
            .where(
                UnitGroupModel.unit_id == unit_id,
                UnitGroupModel.id.in_(group_ids),
                UnitGroupModel.active.is_(True),
            )
            .order_by(UnitGroupModel.position)
        )
    )
    if {group.id for group in groups} != set(group_ids):
        raise ValueError("Every selected group must be active and owned by this unit")
    return groups
