"""Required lesson_mode: planner -> storage -> API -> shape, logging, stale overrides."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select
from tests.planning.path_helpers import four_lesson_draft, unit_create_from_fixture

from application.unit_lesson import prepare as prepare_module
from core.database.models import PathLessonModel, UserModel
from core.prompts import loader
from curriculum.models import PathPlanDraft, PrepareLessonRequest
from curriculum.routes import _path_payload
from curriculum.service import approve_path, create_unit, persist_path_plan
from curriculum.shapes import lesson_shape_payload
from curriculum.validation import normalize_path_plan_draft

FIXTURE = "grade4-photosynthesis-path.json"


def _mixed_mode_plan():
    payload = four_lesson_draft().model_dump()
    modes = ["first_exposure", "first_exposure", "consolidation", "transfer"]
    for lesson, mode in zip(payload["lessons"], modes, strict=True):
        lesson["lesson_mode"] = mode
        lesson["lesson_mode_reason"] = f"reason for {mode}"
    return normalize_path_plan_draft(PathPlanDraft.model_validate(payload))


async def _persisted(db_session, *, plan, owner_id: str):
    db_session.add(UserModel(id=owner_id, email=f"{owner_id}@example.invalid", name=owner_id))
    unit = await create_unit(
        db_session, owner_id=owner_id, request=unit_create_from_fixture(FIXTURE)
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    lessons = list(
        await db_session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
    )
    return unit, version, lessons


async def test_planner_modes_reach_storage_and_api(db_session) -> None:
    plan = _mixed_mode_plan()
    _unit, version, lessons = await _persisted(db_session, plan=plan, owner_id="rlm-store")

    assert [lesson.lesson_mode for lesson in lessons] == [
        "first_exposure",
        "first_exposure",
        "consolidation",
        "transfer",
    ]
    assert lessons[2].lesson_mode_reason == "reason for consolidation"
    assert {lesson.lesson_mode_source for lesson in lessons} == {"path_planner"}

    payload = await _path_payload(db_session, version)
    api = payload["lessons"]
    assert [item["lesson_mode"] for item in api] == [lesson.lesson_mode for lesson in lessons]
    assert api[2]["lesson_mode_reason"] == "reason for consolidation"
    assert api[2]["lesson_mode_source"] == "path_planner"


async def test_api_returns_null_mode_for_legacy_lessons(db_session) -> None:
    plan = _mixed_mode_plan()
    for lesson in plan.lessons:  # legacy path: planned before modes existed
        lesson.lesson_mode = None
        lesson.lesson_mode_reason = None
    _unit, version, _lessons = await _persisted(db_session, plan=plan, owner_id="rlm-legacy")

    api = (await _path_payload(db_session, version))["lessons"]
    assert all(item["lesson_mode"] is None for item in api)
    assert all(item["lesson_mode_reason"] is None for item in api)
    assert all(item["lesson_mode_source"] is None for item in api)


async def test_stored_consolidation_mode_drives_factual_shape(db_session) -> None:
    plan = _mixed_mode_plan()
    _unit, _version, lessons = await _persisted(db_session, plan=plan, owner_id="rlm-shape")
    lesson = next(item for item in lessons if item.primary_knowledge_type == "factual")
    lesson.lesson_mode = "consolidation"

    payload = await lesson_shape_payload(db_session, lesson=lesson, misconception_count=1)

    assert payload["lesson_mode"] == "consolidation"
    assert payload["skeleton_id"] == "factual.consolidation"
    assert [slot["slot_id"] for slot in payload["canonical"]["slots"]] == [
        "recall",
        "organise",
        "independent",
        "check",
    ]

    explicit = await lesson_shape_payload(
        db_session, lesson=lesson, lesson_mode="first_exposure", misconception_count=1
    )
    assert explicit["skeleton_id"] == "factual.first_exposure"


async def test_null_stored_mode_falls_back_to_first_exposure(db_session) -> None:
    plan = _mixed_mode_plan()
    _unit, _version, lessons = await _persisted(db_session, plan=plan, owner_id="rlm-null")
    lesson = lessons[0]
    lesson.lesson_mode = None

    payload = await lesson_shape_payload(db_session, lesson=lesson, misconception_count=1)

    assert payload["lesson_mode"] == "first_exposure"


async def test_prepare_defaults_request_mode_to_stored_mode(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _mixed_mode_plan()
    unit, version, lessons = await _persisted(db_session, plan=plan, owner_id="rlm-prepare")
    await approve_path(db_session, version)
    lesson = next(item for item in lessons if item.primary_knowledge_type == "factual")
    lesson.lesson_mode = "consolidation"
    seen: list[str] = []

    class _Stop(Exception):
        pass

    class _Catalog:
        def skeleton_for(self, knowledge_type: str, mode: str):
            seen.append(mode)
            raise _Stop

    monkeypatch.setattr(prepare_module, "load_skeleton_catalog", lambda: _Catalog())

    for requested, expected in ((None, "consolidation"), ("transfer", "transfer")):
        with pytest.raises(_Stop):
            await prepare_module.prepare_path_lesson(
                db_session,
                unit=unit,
                version=version,
                lesson=lesson,
                request=PrepareLessonRequest(lesson_mode=requested),
            )
        assert seen[-1] == expected


def _events(caplog: pytest.LogCaptureFixture, event: str):
    return [r for r in caplog.records if getattr(r, "event", None) == event]


async def test_persist_logs_lesson_mode_counts(
    db_session, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="curriculum.planner_diagnostics"):
        await _persisted(db_session, plan=_mixed_mode_plan(), owner_id="rlm-log")

    [record] = _events(caplog, "path_lesson_modes")
    assert record.total_lessons == 4
    assert record.lessons_with_mode == 4
    assert [item["lesson_mode"] for item in record.lessons] == [
        "first_exposure",
        "first_exposure",
        "consolidation",
        "transfer",
    ]
    assert all(item["has_reason"] for item in record.lessons)
    assert set(record.lessons[0]) == {"key", "lesson_mode", "has_reason"}
    assert not _events(caplog, "path_lesson_mode_missing")


async def test_persist_warns_when_a_lesson_lacks_a_mode(
    db_session, caplog: pytest.LogCaptureFixture
) -> None:
    plan = _mixed_mode_plan()
    plan.lessons[1].lesson_mode = None
    plan.lessons[1].lesson_mode_reason = None
    with caplog.at_level(logging.INFO, logger="curriculum.planner_diagnostics"):
        await _persisted(db_session, plan=plan, owner_id="rlm-miss")

    [summary] = _events(caplog, "path_lesson_modes")
    assert summary.lessons_with_mode == 3
    [warning] = _events(caplog, "path_lesson_mode_missing")
    assert warning.levelno == logging.WARNING
    assert warning.missing_count == 1
    assert warning.missing_keys == ["L2"]


async def test_stale_path_planner_overrides_flags_only_prompts_without_lesson_mode(
    db_session_factory, caplog: pytest.LogCaptureFixture
) -> None:
    async with db_session_factory() as session:
        await loader.save_override("path-planner", "stale-user", "Old planner prompt.", session)
        await loader.save_override(
            "path-planner", "fresh-user", "New prompt. Set lesson_mode for each lesson.", session
        )
        await loader.save_override("section-writer", "other-user", "Unrelated override.", session)

        assert await loader.stale_path_planner_overrides(session) == ["stale-user"]

        with caplog.at_level(logging.WARNING, logger="core.prompts.loader"):
            assert await loader.warn_stale_path_planner_overrides(session) == 1
        [record] = _events(caplog, "path_planner_override_missing_lesson_mode")
        assert record.count == 1
        assert "Old planner prompt" not in caplog.text

        with caplog.at_level(logging.WARNING, logger="core.prompts.loader"):
            await loader.resolve_prompt("path-planner", "stale-user", session)
            await loader.resolve_prompt("path-planner", "fresh-user", session)
        resolved = [
            r
            for r in _events(caplog, "path_planner_override_missing_lesson_mode")
            if hasattr(r, "user_id")
        ]
        assert [r.user_id for r in resolved] == ["stale-user"]
