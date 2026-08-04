from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LessonActualModel,
    MarksEntryModel,
    PackItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitGroupModel,
    UnitModel,
)
from planning.models import LessonActualWriteRequest, MarksWriteRequest


class OutcomeValidationError(ValueError):
    pass


class StaleOutcomeError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def actual_payload(actual: LessonActualModel) -> dict[str, Any]:
    return {
        "id": actual.id,
        "unit_id": actual.unit_id,
        "path_version_id": actual.path_version_id,
        "path_lesson_id": actual.path_lesson_id,
        "revision": actual.revision,
        "lesson_revision": actual.lesson_revision,
        "objective_hash": actual.objective_hash,
        "status": actual.status,
        "taught": actual.taught,
        "pace": actual.pace,
        "established_concepts": list(actual.established_concepts or []),
        "unresolved_misconceptions": list(actual.unresolved_misconceptions or []),
        "anchor_used": actual.anchor_used,
        "teacher_note": actual.teacher_note,
        "supersedes_actual_id": actual.supersedes_actual_id,
        "recorded_by": actual.recorded_by,
        "recorded_at": actual.recorded_at,
    }


async def latest_actual(
    session: AsyncSession, *, path_lesson_id: str
) -> LessonActualModel | None:
    return await session.scalar(
        select(LessonActualModel)
        .where(LessonActualModel.path_lesson_id == path_lesson_id)
        .order_by(LessonActualModel.revision.desc())
        .limit(1)
    )


async def record_lesson_actual(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
    request: LessonActualWriteRequest,
    user_id: str,
) -> LessonActualModel:
    current = await latest_actual(session, path_lesson_id=lesson.id)
    current_revision = current.revision if current else 0
    if request.actual_revision != current_revision:
        raise StaleOutcomeError(
            f"Lesson actual revision is stale; expected {current_revision}"
        )
    established = list(dict.fromkeys(item.strip() for item in request.established_concepts if item.strip()))
    unresolved = list(dict.fromkeys(item.strip() for item in request.unresolved_misconceptions if item.strip()))
    if request.status == "not_taught" and established:
        raise OutcomeValidationError("A not-taught lesson cannot establish concepts")
    actual = LessonActualModel(
        unit_id=unit.id,
        path_version_id=version.id,
        path_lesson_id=lesson.id,
        owner_id=user_id,
        revision=current_revision + 1,
        lesson_revision=lesson.revision,
        objective_hash=lesson.objective_hash,
        status=request.status,
        taught=request.status != "not_taught",
        pace=request.pace,
        established_concepts=established,
        unresolved_misconceptions=unresolved,
        anchor_used=(request.anchor_used or "").strip() or None,
        teacher_note=(request.teacher_note or "").strip() or None,
        supersedes_actual_id=current.id if current else None,
        recorded_by=user_id,
        recorded_at=_utcnow(),
    )
    session.add(actual)
    await session.flush()
    return actual


async def actual_context_for_lessons(
    session: AsyncSession, *, path_lesson_ids: list[str]
) -> list[dict[str, Any]]:
    if not path_lesson_ids:
        return []
    rows = list(
        await session.scalars(
            select(LessonActualModel)
            .where(LessonActualModel.path_lesson_id.in_(path_lesson_ids))
            .order_by(LessonActualModel.path_lesson_id, LessonActualModel.revision.desc())
        )
    )
    latest: dict[str, LessonActualModel] = {}
    for row in rows:
        latest.setdefault(row.path_lesson_id, row)
    return [
        {
            "path_lesson_id": lesson_id,
            "status": row.status,
            "taught": row.taught,
            "pace": row.pace,
            "established_concepts": list(row.established_concepts or []),
            "unresolved_misconceptions": list(row.unresolved_misconceptions or []),
            "anchor_used": row.anchor_used,
            "teacher_note": row.teacher_note,
            "recorded_at": row.recorded_at.isoformat(),
            "advisory": True,
        }
        for lesson_id in path_lesson_ids
        if (row := latest.get(lesson_id)) is not None
    ]


def _option_map(item: PackItemModel) -> dict[str, dict[str, Any]]:
    return {
        str(option.get("key")): option
        for option in (item.options or [])
        if isinstance(option, dict) and option.get("key") is not None
    }


def _diagnosis(item: PackItemModel, option_id: str, option: dict[str, Any]) -> str | None:
    diagnoses = item.diagnoses if isinstance(item.diagnoses, dict) else {}
    value = diagnoses.get(option_id, option.get("diagnoses"))
    return str(value) if value not in {None, ""} else None


async def _lesson_pack_id(session: AsyncSession, lesson: PathLessonModel) -> str:
    if not lesson.pack_id:
        raise OutcomeValidationError("Marks require a prepared lesson with pack-owned items")
    coordinator = await session.get(GenerationModel, lesson.pack_id)
    if coordinator is None or not coordinator.pack_id:
        raise OutcomeValidationError("Prepared lesson pack linkage is incomplete")
    return coordinator.pack_id


async def record_marks(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
    request: MarksWriteRequest,
    user_id: str,
) -> dict[str, Any]:
    pack_id = await _lesson_pack_id(session, lesson)
    if request.group_id is not None:
        group = await session.get(UnitGroupModel, request.group_id)
        if group is None or group.unit_id != unit.id:
            raise OutcomeValidationError("Marks group is not owned by this unit")
    current_revision = int(
        await session.scalar(
            select(func.max(MarksEntryModel.revision)).where(
                MarksEntryModel.path_lesson_id == lesson.id,
                MarksEntryModel.group_id == request.group_id,
            )
        )
        or 0
    )
    if request.marks_revision != current_revision:
        raise StaleOutcomeError(f"Marks revision is stale; expected {current_revision}")
    if len({item.item_id for item in request.items}) != len(request.items):
        raise OutcomeValidationError("Each marks item may appear only once")
    item_ids = [item.item_id for item in request.items]
    owned = {
        item.id: item
        for item in await session.scalars(
            select(PackItemModel).where(
                PackItemModel.id.in_(item_ids),
                PackItemModel.pack_id == pack_id,
                PackItemModel.stale.is_(False),
            )
        )
    }
    if set(owned) != set(item_ids):
        raise OutcomeValidationError("Every marks item must be a current item owned by this lesson pack")
    submission_id = str(uuid.uuid4())
    revision = current_revision + 1
    recorded_at = _utcnow()
    for requested in request.items:
        item = owned[requested.item_id]
        options = _option_map(item)
        if set(requested.option_counts) != set(options):
            raise OutcomeValidationError(
                f"Counts for item {item.id!r} must include every answer option exactly once"
            )
        for option_id, count in requested.option_counts.items():
            if count < 0:
                raise OutcomeValidationError("Answer-option counts cannot be negative")
            session.add(
                MarksEntryModel(
                    submission_id=submission_id,
                    unit_id=unit.id,
                    path_version_id=version.id,
                    path_lesson_id=lesson.id,
                    owner_id=user_id,
                    revision=revision,
                    lesson_revision=lesson.revision,
                    objective_hash=lesson.objective_hash,
                    pack_id=pack_id,
                    group_id=request.group_id,
                    item_id=item.id,
                    option_id=option_id,
                    count=count,
                    misconception_id=_diagnosis(item, option_id, options[option_id]),
                    recorded_by=user_id,
                    recorded_at=recorded_at,
                )
            )
    await session.flush()
    return await marks_summary(
        session, lesson=lesson, group_id=request.group_id, revision=revision
    )


async def marks_summary(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    group_id: str | None,
    revision: int | None = None,
) -> dict[str, Any]:
    if revision is None:
        revision = int(
            await session.scalar(
                select(func.max(MarksEntryModel.revision)).where(
                    MarksEntryModel.path_lesson_id == lesson.id,
                    MarksEntryModel.group_id == group_id,
                )
            )
            or 0
        )
    if revision == 0:
        pack_id = await _lesson_pack_id(session, lesson)
        available_items = list(
            await session.scalars(
                select(PackItemModel)
                .where(PackItemModel.pack_id == pack_id, PackItemModel.stale.is_(False))
                .order_by(PackItemModel.created_at, PackItemModel.id)
            )
        )
        return {
            "path_lesson_id": lesson.id,
            "group_id": group_id,
            "revision": 0,
            "items": [
                {
                    "item_id": item.id,
                    "stem": item.stem,
                    "total_count": 0,
                    "option_counts": [
                        {
                            "option_id": option_id,
                            "text": str(option.get("text") or option_id),
                            "count": 0,
                            "correct": bool(option.get("correct")),
                            "misconception_id": _diagnosis(item, option_id, option),
                        }
                        for option_id, option in _option_map(item).items()
                    ],
                }
                for item in available_items
            ],
            "misconceptions": [],
            "unclaimed_distractor_count": 0,
            "advisory": True,
            "advisory_note": "Aggregate counts suggest teaching follow-up; they do not diagnose individual learners.",
        }
    entries = list(
        await session.scalars(
            select(MarksEntryModel).where(
                MarksEntryModel.path_lesson_id == lesson.id,
                MarksEntryModel.group_id == group_id,
                MarksEntryModel.revision == revision,
            )
        )
    )
    item_ids = list(dict.fromkeys(entry.item_id for entry in entries))
    items = {item.id: item for item in await session.scalars(select(PackItemModel).where(PackItemModel.id.in_(item_ids)))}
    card_ids = list({item.card_id for item in items.values()})
    cards = {card.id: card for card in await session.scalars(select(ConceptCardModel).where(ConceptCardModel.id.in_(card_ids)))}
    labels = {
        str(misconception.get("id")): str(misconception.get("description") or misconception.get("id"))
        for card in cards.values()
        for misconception in (card.misconceptions or [])
        if isinstance(misconception, dict) and misconception.get("id")
    }
    entries_by_item: dict[str, list[MarksEntryModel]] = defaultdict(list)
    misconception_counts: dict[str, int] = defaultdict(int)
    unclaimed = 0
    for entry in entries:
        entries_by_item[entry.item_id].append(entry)
        item = items[entry.item_id]
        option = _option_map(item).get(entry.option_id, {})
        if not bool(option.get("correct")):
            if entry.misconception_id:
                misconception_counts[entry.misconception_id] += entry.count
            else:
                unclaimed += entry.count
    item_payloads = []
    for item_id in item_ids:
        item = items[item_id]
        options = _option_map(item)
        rows = sorted(entries_by_item[item_id], key=lambda row: row.option_id)
        item_payloads.append(
            {
                "item_id": item.id,
                "stem": item.stem,
                "total_count": sum(row.count for row in rows),
                "option_counts": [
                    {
                        "option_id": row.option_id,
                        "text": str(options[row.option_id].get("text") or row.option_id),
                        "count": row.count,
                        "correct": bool(options[row.option_id].get("correct")),
                        "misconception_id": row.misconception_id,
                    }
                    for row in rows
                ],
            }
        )
    return {
        "path_lesson_id": lesson.id,
        "group_id": group_id,
        "revision": revision,
        "items": item_payloads,
        "misconceptions": [
            {"misconception_id": key, "label": labels.get(key, key), "count": count}
            for key, count in sorted(misconception_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "unclaimed_distractor_count": unclaimed,
        "advisory": True,
        "advisory_note": "Aggregate counts suggest teaching follow-up; they do not diagnose individual learners.",
    }
