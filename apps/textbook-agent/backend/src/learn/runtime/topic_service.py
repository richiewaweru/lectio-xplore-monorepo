"""Topic path for a learner: unit path lessons joined to released, assigned lessons (doc 38 3.2/3.3).

``compute_topic_lessons`` is a pure state function. ``build_topics_payload`` does the
read-only database assembly and calls it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    LearnReleaseModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UnitModel,
)
from learn.runtime.runtime_models import (
    LearnAssignmentModel,
    LearnAssignmentTargetModel,
    LearnClassMembershipModel,
    LearnerAttemptModel,
    LearnerIdentityModel,
    LearningInstanceModel,
    LessonProgressModel,
)


@dataclass(frozen=True)
class LessonInput:
    """Everything the state rule needs for one non-skipped path lesson."""

    path_lesson_id: str
    position: int
    title: str
    release_id: str | None = None  # None -> no published release assigned to the class
    instance_id: str | None = None
    instance_status: str | None = None  # "active" | "completed" | None
    touched: bool = False  # completed sections, any attempt, or current_section_id set
    sections_done: int = 0
    sections_total: int = 0
    prerequisite_ids: tuple[str, ...] = field(default_factory=tuple)


def is_touched(
    *, completed_section_ids: list[Any] | None, has_attempt: bool, current_section_id: str | None
) -> bool:
    return bool(completed_section_ids) or has_attempt or bool(current_section_id)


def _base_state(lesson: LessonInput) -> str:
    if lesson.release_id is None:
        return "pending"
    if lesson.instance_status == "completed":
        return "done"
    if lesson.instance_status == "active" and lesson.touched:
        return "current"
    return "ready"


def compute_topic_lessons(lessons: list[LessonInput]) -> dict[str, Any]:
    """Apply the 3.2 rule. Returns ``{lessons, lessons_total, lessons_done, next_lesson_id}``.

    Exactly one lesson is ``current``: the in-progress lesson with the highest position.
    Other in-progress lessons stay openable as ``ready`` (their ``sections_done`` shows
    the progress). ``next_lesson_id`` is the current lesson, otherwise the first ready
    lesson after the last done one (falling back to the first ready lesson).
    """
    ordered = sorted(lessons, key=lambda lesson: lesson.position)
    states = {lesson.path_lesson_id: _base_state(lesson) for lesson in ordered}
    position_of = {lesson.path_lesson_id: lesson.position for lesson in ordered}

    in_progress = [lesson for lesson in ordered if states[lesson.path_lesson_id] == "current"]
    current_id: str | None = None
    if in_progress:
        current_id = in_progress[-1].path_lesson_id
        for lesson in in_progress[:-1]:
            states[lesson.path_lesson_id] = "ready"

    last_done_position = max(
        (position_of[i] for i, state in states.items() if state == "done"), default=None
    )
    next_id = current_id
    if next_id is None:
        ready = [lesson for lesson in ordered if states[lesson.path_lesson_id] == "ready"]
        after = [
            lesson
            for lesson in ready
            if last_done_position is None or lesson.position > last_done_position
        ]
        pick = after[0] if after else (ready[0] if ready else None)
        next_id = pick.path_lesson_id if pick else None

    out: list[dict[str, Any]] = []
    for lesson in ordered:
        state = states[lesson.path_lesson_id]
        best_after: int | None = None
        if state in {"ready", "pending"}:
            unmet = [
                position_of[pid]
                for pid in lesson.prerequisite_ids
                if pid in states and states[pid] != "done"
            ]
            best_after = min(unmet) if unmet else None
        if state == "done":
            sections_done = lesson.sections_total
        else:
            sections_done = min(lesson.sections_done, lesson.sections_total)
        out.append(
            {
                "path_lesson_id": lesson.path_lesson_id,
                "position": lesson.position,
                "title": lesson.title,
                "state": state,
                "instance_id": lesson.instance_id,
                "release_id": lesson.release_id,
                "best_after_position": best_after,
                "sections_done": sections_done,
                "sections_total": lesson.sections_total,
            }
        )
    return {
        "lessons": out,
        "lessons_total": len(out),
        "lessons_done": sum(1 for row in out if row["state"] == "done"),
        "next_lesson_id": next_id,
    }


def _section_ids(document: Any) -> list[str]:
    sections = document.get("sections") if isinstance(document, dict) else None
    if not isinstance(sections, list):
        return []
    return [str(s["id"]) for s in sections if isinstance(s, dict) and s.get("id") is not None]


def _other_state(instance: LearningInstanceModel, touched: bool) -> str:
    if instance.status == "completed":
        return "done"
    return "current" if touched else "ready"


async def build_topics_payload(
    session: AsyncSession, learner: LearnerIdentityModel
) -> dict[str, Any]:
    learner_id = learner.id
    base: dict[str, Any] = {
        "learner_id": learner_id,
        "display_name": learner.display_name,
        "code": learner.invite_code,
        "topics": [],
        "other_lessons": [],
    }

    class_ids = list(
        (
            await session.execute(
                select(LearnClassMembershipModel.class_id).where(
                    LearnClassMembershipModel.learner_id == learner_id,
                    LearnClassMembershipModel.status == "active",
                )
            )
        ).scalars()
    )
    if not class_ids:
        return base

    # release_id -> class_id for active assignments targeting a class the learner is in.
    release_class: dict[str, str] = {}
    direct = (
        await session.execute(
            select(LearnAssignmentModel.learn_release_id, LearnAssignmentModel.class_id).where(
                LearnAssignmentModel.active.is_(True),
                LearnAssignmentModel.class_id.in_(class_ids),
            )
        )
    ).all()
    targeted = (
        await session.execute(
            select(LearnAssignmentModel.learn_release_id, LearnAssignmentTargetModel.class_id)
            .join(
                LearnAssignmentTargetModel,
                LearnAssignmentTargetModel.assignment_id == LearnAssignmentModel.id,
            )
            .where(
                LearnAssignmentModel.active.is_(True),
                LearnAssignmentTargetModel.class_id.in_(class_ids),
            )
        )
    ).all()
    for release_id, class_id in [*direct, *targeted]:
        release_class.setdefault(release_id, class_id)

    releases = []
    if release_class:
        releases = list(
            (
                await session.execute(
                    select(LearnReleaseModel).where(
                        LearnReleaseModel.id.in_(list(release_class)),
                        LearnReleaseModel.status == "published",
                    )
                )
            ).scalars()
        )

    # Latest published release per path lesson.
    latest: dict[str, LearnReleaseModel] = {}
    for release in releases:
        if not release.path_lesson_id:
            continue
        current = latest.get(release.path_lesson_id)
        if current is None or (release.published_at, release.release_number) > (
            current.published_at,
            current.release_number,
        ):
            latest[release.path_lesson_id] = release

    # Learner instances, progress and attempt flags.
    instances = list(
        (
            await session.execute(
                select(LearningInstanceModel)
                .where(LearningInstanceModel.learner_id == learner_id)
                .order_by(LearningInstanceModel.updated_at.desc())
            )
        ).scalars()
    )
    instance_by_release: dict[str, LearningInstanceModel] = {}
    for instance in instances:  # newest first: keep the most recently updated per release
        instance_by_release.setdefault(instance.learn_release_id, instance)
    instance_ids = [i.id for i in instances]
    progress_by_instance: dict[str, LessonProgressModel] = {}
    attempted: set[str] = set()
    if instance_ids:
        for row in (
            await session.execute(
                select(LessonProgressModel).where(
                    LessonProgressModel.learning_instance_id.in_(instance_ids)
                )
            )
        ).scalars():
            progress_by_instance[row.learning_instance_id] = row
        attempted = set(
            (
                await session.execute(
                    select(LearnerAttemptModel.learning_instance_id)
                    .where(LearnerAttemptModel.learning_instance_id.in_(instance_ids))
                    .distinct()
                )
            ).scalars()
        )

    def touched(instance: LearningInstanceModel) -> bool:
        progress = progress_by_instance.get(instance.id)
        return is_touched(
            completed_section_ids=list(progress.completed_section_ids or []) if progress else [],
            has_attempt=instance.id in attempted,
            current_section_id=instance.current_section_id,
        )

    # Units that have at least one linked release.
    linked_path_lesson_ids = list(latest)
    unit_ids: list[str] = []
    if linked_path_lesson_ids:
        unit_ids = list(
            dict.fromkeys(
                (
                    await session.execute(
                        select(PathVersionModel.unit_id)
                        .join(
                            PathLessonModel,
                            PathLessonModel.path_version_id == PathVersionModel.id,
                        )
                        .where(PathLessonModel.id.in_(linked_path_lesson_ids))
                    )
                ).scalars()
            )
        )

    shown_instance_ids: set[str] = set()
    shown_path_lesson_ids: set[str] = set()
    topics: list[dict[str, Any]] = []
    units = (
        list(
            (
                await session.execute(select(UnitModel).where(UnitModel.id.in_(unit_ids)))
            ).scalars()
        )
        if unit_ids
        else []
    )
    for unit in sorted(units, key=lambda u: (u.title or "", u.id)):
        if not unit.active_path_version_id:
            continue
        path_lessons = list(
            (
                await session.execute(
                    select(PathLessonModel)
                    .where(
                        PathLessonModel.path_version_id == unit.active_path_version_id,
                        PathLessonModel.skipped.is_(False),
                    )
                    .order_by(PathLessonModel.position)
                )
            ).scalars()
        )
        if not path_lessons:
            continue
        prereqs: dict[str, list[str]] = {}
        for row in (
            await session.execute(
                select(PathLessonPrerequisiteModel).where(
                    PathLessonPrerequisiteModel.path_lesson_id.in_([p.id for p in path_lessons])
                )
            )
        ).scalars():
            prereqs.setdefault(row.path_lesson_id, []).append(row.prerequisite_lesson_id)

        inputs: list[LessonInput] = []
        topic_class_id: str | None = None
        for path_lesson in path_lessons:
            release = latest.get(path_lesson.id)
            instance = instance_by_release.get(release.id) if release else None
            doc_sections = _section_ids(release.document_json) if release else []
            sections_done = 0
            if instance is not None:
                progress = progress_by_instance.get(instance.id)
                done_ids = set(progress.completed_section_ids or []) if progress else set()
                sections_done = len(done_ids & set(doc_sections)) if doc_sections else 0
                shown_instance_ids.add(instance.id)
            if release is not None and topic_class_id is None:
                topic_class_id = release_class.get(release.id)
            inputs.append(
                LessonInput(
                    path_lesson_id=path_lesson.id,
                    position=path_lesson.position,
                    title=path_lesson.title,
                    release_id=release.id if release else None,
                    instance_id=instance.id if instance else None,
                    instance_status=instance.status if instance else None,
                    touched=touched(instance) if instance else False,
                    sections_done=sections_done,
                    sections_total=len(doc_sections),
                    prerequisite_ids=tuple(prereqs.get(path_lesson.id, [])),
                )
            )
        if topic_class_id is None:
            continue  # no lesson of the active path is released to this learner
        shown_path_lesson_ids.update(i.path_lesson_id for i in inputs)
        computed = compute_topic_lessons(inputs)
        topics.append(
            {
                "unit_id": unit.id,
                "title": unit.title,
                "summary": unit.destination_objective or unit.topic,
                "class_id": topic_class_id,
                **computed,
            }
        )

    # Anything assigned but not shown on a topic path (no link, or linked outside the
    # active path) goes under "Other lessons".
    other: list[dict[str, Any]] = []
    instance_release_ids = list({i.learn_release_id for i in instances})
    owned = {}
    if instance_release_ids:
        owned = {
            r.id: r
            for r in (
                await session.execute(
                    select(LearnReleaseModel).where(
                        LearnReleaseModel.id.in_(instance_release_ids),
                        LearnReleaseModel.status == "published",
                    )
                )
            ).scalars()
        }
    for instance in instances:
        release = owned.get(instance.learn_release_id)
        if release is None or instance.id in shown_instance_ids:
            continue
        if instance_by_release.get(instance.learn_release_id) is not instance:
            continue
        if release.path_lesson_id and release.path_lesson_id in shown_path_lesson_ids:
            continue  # superseded release of a lesson already on a topic path
        other.append(
            {
                "instance_id": instance.id,
                "title": release.title or "Lesson",
                "state": _other_state(instance, touched(instance)),
            }
        )

    base["topics"] = topics
    base["other_lessons"] = other
    return base


async def build_instance_topic(
    session: AsyncSession, instance: LearningInstanceModel
) -> dict[str, Any] | None:
    """Topic context for one learner instance: ``None`` for unlinked releases.

    Reuses ``build_topics_payload`` so the lesson state rule is not duplicated.
    ``next_lesson`` is the lesson at the next position of the topic path, with state
    ``ready`` (openable, ``instance_id`` set), ``pending`` (not released yet) or ``None``.
    """
    release = await session.get(LearnReleaseModel, instance.learn_release_id)
    if release is None or not release.path_lesson_id:
        return None
    learner = await session.get(LearnerIdentityModel, instance.learner_id)
    if learner is None:
        return None
    payload = await build_topics_payload(session, learner)
    for topic in payload["topics"]:
        lessons = topic["lessons"]
        index = next(
            (i for i, row in enumerate(lessons) if row["path_lesson_id"] == release.path_lesson_id),
            None,
        )
        if index is None:
            continue
        nxt = lessons[index + 1] if index + 1 < len(lessons) else None
        next_lesson: dict[str, Any] = {"state": None, "title": None, "instance_id": None}
        if nxt is not None:
            if nxt["state"] == "pending" or not nxt["instance_id"]:
                next_lesson = {"state": "pending", "title": nxt["title"], "instance_id": None}
            else:
                next_lesson = {
                    "state": "ready",
                    "title": nxt["title"],
                    "instance_id": nxt["instance_id"],
                }
        return {
            "unit_id": topic["unit_id"],
            "title": topic["title"],
            "lesson_position": index + 1,
            "lessons_total": topic["lessons_total"],
            "next_lesson": next_lesson,
        }
    return None
