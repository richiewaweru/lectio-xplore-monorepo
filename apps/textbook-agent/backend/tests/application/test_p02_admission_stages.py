"""P02 stage registry + admission/effect idempotency gates (G05–G08)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture

from application.unit_lesson.effect_keys import (
    EffectPayloadConflictError,
    payload_digest,
    remember_effect,
)
from application.unit_lesson.realizations import (
    RealizationPayloadConflictError,
    admit_realization,
)
from application.unit_lesson.stage_registry import (
    IllegalStageTransitionError,
    UnknownStageError,
    active_entrypoint_map,
    assert_transition,
    get_stage,
    is_approval_wait,
    is_worker_claimable,
)
from core.database.models import (
    GenerationModel,
    NativeRealizationModel,
    PathLessonModel,
    UserModel,
)
from curriculum.service import approve_path, create_unit, persist_path_plan


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _prepared_lesson(db_session: AsyncSession, *, user_id: str) -> PathLessonModel:
    user = UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id)
    db_session.add(user)
    plan = load_canonical_plan("grade4-photosynthesis-path.json")
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None
    prep_id = f"prep-{user_id}"
    db_session.add(
        GenerationModel(
            id=prep_id,
            user_id=user.id,
            subject="science",
            context="shared prep",
            status="awaiting_review",
            requested_template_id="lesson",
            requested_preset_id="standard",
            created_at=_utcnow(),
            chunked_state_json={
                "shared_preparation": True,
                "stage": "awaiting_teaching_approval",
                "teaching_plan_id": f"tp-{user_id}",
                "teaching_review": {"approved_revision": 1, "status": "approved"},
                "teaching_plan": {
                    "teaching_plan_id": f"tp-{user_id}",
                    "revision": 1,
                    "preparation_hash": "hash-rev-1",
                    "arc": "build",
                    "sections": [],
                },
            },
        )
    )
    lesson.pack_id = prep_id
    await db_session.flush()
    return lesson


@pytest.mark.asyncio
async def test_g05_stage_registry_rejects_unknown_and_illegal() -> None:
    assert is_approval_wait("print", "awaiting_teaching_approval")
    assert not is_worker_claimable("print", "awaiting_teaching_approval")
    assert is_worker_claimable("print", "queued")
    assert get_stage("learn", "queued").worker_claimable
    with pytest.raises(UnknownStageError):
        get_stage("learn", "not-a-stage")
    with pytest.raises(IllegalStageTransitionError):
        assert_transition("learn", "queued", "ready")
    assert_transition("learn", "queued", "running")
    mapping = active_entrypoint_map()
    assert "realize_learn_from_preparation" in mapping
    assert "queued" in mapping["realize_print_from_preparation"]


@pytest.mark.asyncio
async def test_g07_admission_request_key_idempotent_and_conflict(
    db_session: AsyncSession,
) -> None:
    lesson = await _prepared_lesson(db_session, user_id="p02-g07")
    key = "admit-key-1"
    first, created1 = await admit_realization(
        db_session,
        path_lesson_id=lesson.id,
        path="learn",
        teaching_plan_id="tp-p02-g07",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-a",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
        output_id="learn-out-a",
        admission_request_key=key,
        admission_payload_hash="hash-a",
    )
    assert created1 is True
    second, created2 = await admit_realization(
        db_session,
        path_lesson_id=lesson.id,
        path="learn",
        teaching_plan_id="tp-p02-g07",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-a",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
        output_id="learn-out-b",
        admission_request_key=key,
        admission_payload_hash="hash-a",
    )
    assert created2 is False
    assert first.id == second.id
    with pytest.raises(RealizationPayloadConflictError):
        await admit_realization(
            db_session,
            path_lesson_id=lesson.id,
            path="learn",
            teaching_plan_id="tp-p02-g07",
            teaching_plan_revision=1,
            teaching_plan_hash="hash-b",
            preparation_generation_id=lesson.pack_id,
            pack_id=lesson.pack_id,
            output_id="learn-out-c",
            admission_request_key=key,
            admission_payload_hash="hash-b",
        )


@pytest.mark.asyncio
async def test_g07_concurrent_identical_admissions_one_row(
    db_session: AsyncSession,
) -> None:
    from core.database.session import async_session_factory

    lesson = await _prepared_lesson(db_session, user_id="p02-g07c")
    await db_session.commit()
    lesson_id = lesson.id
    pack_id = lesson.pack_id
    key = "concurrent-admit"

    async def _admit() -> str:
        async with async_session_factory() as session:
            row, _ = await admit_realization(
                session,
                path_lesson_id=lesson_id,
                path="print",
                teaching_plan_id="tp-p02-g07c",
                teaching_plan_revision=1,
                teaching_plan_hash="hash-print",
                preparation_generation_id=pack_id,
                pack_id=pack_id,
                output_id=pack_id,
                admission_request_key=key,
                admission_payload_hash="hash-print",
            )
            await session.commit()
            return row.id

    ids = await asyncio.gather(_admit(), _admit(), _admit())
    assert len(set(ids)) == 1
    async with async_session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(NativeRealizationModel)
            .where(
                NativeRealizationModel.path_lesson_id == lesson_id,
                NativeRealizationModel.path == "print",
                NativeRealizationModel.admission_request_key == key,
            )
        )
    assert count == 1


@pytest.mark.asyncio
async def test_g08_effect_key_replay_and_conflict(db_session: AsyncSession) -> None:
    user_id = "p02-g08"
    db_session.add(UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id))
    await db_session.flush()
    resource = str(uuid.uuid4())
    digest = payload_digest({"doc": 1})
    first, created = await remember_effect(
        db_session,
        owner_user_id=user_id,
        kind="builder_save",
        resource_id=resource,
        request_key="save-1",
        payload_hash=digest,
        outcome_json={"ok": True},
    )
    assert created is True
    second, created2 = await remember_effect(
        db_session,
        owner_user_id=user_id,
        kind="builder_save",
        resource_id=resource,
        request_key="save-1",
        payload_hash=digest,
    )
    assert created2 is False
    assert first.id == second.id
    with pytest.raises(EffectPayloadConflictError):
        await remember_effect(
            db_session,
            owner_user_id=user_id,
            kind="builder_save",
            resource_id=resource,
            request_key="save-1",
            payload_hash=payload_digest({"doc": 2}),
        )
