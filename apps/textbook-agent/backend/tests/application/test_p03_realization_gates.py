"""P03 native realization identity gates."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.unit_lesson.realization_contracts import (
    DEFAULT_VARIANT_ID,
    LEGACY_AMBIGUOUS_VARIANT,
    canonical_hash,
    package_contract_for,
    policy_for,
)
from application.unit_lesson.realizations import (
    RealizationReadOnlyError,
    backfill_legacy_realization,
    classify_legacy_chunked,
    list_realizations_for_lesson,
    mark_stale_for_policy_change,
    mark_stale_for_teaching_change,
    persisted_path_is_stable,
    request_outputs,
    resolve_by_path,
    retry_realization,
    to_identity,
)
from core.database.models import (
    GenerationModel,
    NativeRealizationModel,
    PathLessonModel,
    UserModel,
)
from curriculum.service import approve_path, create_unit, persist_path_plan
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    # Shared preparation link (legacy pack_id) — not a path discriminator.
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
                "stage": "awaiting_review",
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
async def test_p03_r01_dual_outputs_idempotent(db_session: AsyncSession) -> None:
    """P03-R01: one lesson creates both outputs; duplicates reuse rows."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r01")
    first = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r01",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    assert len(first) == 2
    assert all(created for _, created in first)
    print_row, learn_row = first[0][0], first[1][0]
    assert print_row.path == "print"
    assert learn_row.path == "learn"
    assert print_row.id != learn_row.id
    assert print_row.teaching_plan_revision == learn_row.teaching_plan_revision == 1

    second = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r01",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    assert all(not created for _, created in second)
    assert second[0][0].id == print_row.id
    assert second[1][0].id == learn_row.id
    count = await db_session.scalar(
        select(func.count()).select_from(NativeRealizationModel).where(
            NativeRealizationModel.path_lesson_id == lesson.id,
            NativeRealizationModel.variant_id == DEFAULT_VARIANT_ID,
        )
    )
    assert count == 2


@pytest.mark.asyncio
async def test_p03_r02_print_retry_leaves_learn_and_plan(db_session: AsyncSession) -> None:
    """P03-R02: Print retry does not change Learn output or shared plan pins."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r02")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r02",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    print_row, learn_row = rows[0][0], rows[1][0]
    print_row.output_id = "print-out-1"
    print_row.status = "ready"
    learn_row.output_id = "learn-out-1"
    learn_row.status = "ready"
    await db_session.flush()

    learn_before = (
        learn_row.id,
        learn_row.output_id,
        learn_row.realization_revision,
        learn_row.teaching_plan_id,
        learn_row.teaching_plan_revision,
        learn_row.teaching_plan_hash,
        learn_row.status,
    )
    shared_before = (
        print_row.teaching_plan_id,
        print_row.teaching_plan_revision,
        print_row.teaching_plan_hash,
    )

    retried = await retry_realization(db_session, realization_id=print_row.id, new_output_id="print-out-2")
    await db_session.refresh(learn_row)

    assert retried.output_id == "print-out-2"
    assert retried.realization_revision == 2
    assert retried.path == "print"
    assert (
        retried.teaching_plan_id,
        retried.teaching_plan_revision,
        retried.teaching_plan_hash,
    ) == shared_before
    assert (
        learn_row.id,
        learn_row.output_id,
        learn_row.realization_revision,
        learn_row.teaching_plan_id,
        learn_row.teaching_plan_revision,
        learn_row.teaching_plan_hash,
        learn_row.status,
    ) == learn_before

    # Inverse: Learn retry leaves Print untouched.
    print_snapshot = (
        retried.output_id,
        retried.realization_revision,
        retried.teaching_plan_hash,
    )
    learn_retried = await retry_realization(
        db_session, realization_id=learn_row.id, new_output_id="learn-out-2"
    )
    await db_session.refresh(retried)
    assert learn_retried.output_id == "learn-out-2"
    assert (
        retried.output_id,
        retried.realization_revision,
        retried.teaching_plan_hash,
    ) == print_snapshot


@pytest.mark.asyncio
async def test_p03_r03_persisted_path_survives_default_change(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P03-R03: restart / changed default config cannot switch a persisted path."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r03")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id="tp-p03-r03",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    row = rows[0][0]
    assert row.path == "print"
    realization_id = row.id

    # Simulate process restart + flipped environment default toward Learn.
    monkeypatch.setenv("GENERATION_PIPELINE_DEFAULT", "component_lectio")
    from infra.config import settings

    monkeypatch.setattr(settings, "generation_pipeline_default", "component_lectio", raising=False)

    reloaded = await db_session.get(NativeRealizationModel, realization_id)
    assert reloaded is not None
    assert persisted_path_is_stable(reloaded, "print")
    assert reloaded.path == "print"
    # Re-resolve by path still finds Print; defaults never rewrite the row.
    resolved = await resolve_by_path(db_session, path_lesson_id=lesson.id, path="print")
    assert resolved is not None and resolved.id == realization_id
    assert resolved.path == "print"


@pytest.mark.asyncio
async def test_p03_r04_shared_revision_marks_stale_keeps_snapshots(
    db_session: AsyncSession,
) -> None:
    """P03-R04: shared revision change marks outputs stale; snapshots intact."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r04")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r04",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    print_row, learn_row = rows[0][0], rows[1][0]
    print_row.output_id = "print-snap-1"
    print_row.status = "ready"
    learn_row.output_id = "learn-snap-1"
    learn_row.status = "ready"
    await db_session.flush()

    stale_rows = await mark_stale_for_teaching_change(
        db_session,
        path_lesson_id=lesson.id,
        teaching_plan_id="tp-p03-r04",
        previous_revision=1,
    )
    assert len(stale_rows) == 2
    assert {row.output_id for row in stale_rows} == {"print-snap-1", "learn-snap-1"}
    assert all(row.status == "stale" for row in stale_rows)

    # Independent path regeneration under the new revision.
    refreshed = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id="tp-p03-r04",
        teaching_plan_revision=2,
        teaching_plan_hash="hash-rev-2",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    new_print = refreshed[0][0]
    assert refreshed[0][1] is True
    assert new_print.teaching_plan_revision == 2
    assert new_print.id != print_row.id
    # Old Print snapshot row remains readable.
    await db_session.refresh(print_row)
    assert print_row.output_id == "print-snap-1"
    assert print_row.status == "stale"

    # Policy change invalidates only that path.
    policy_version, policy_hash = policy_for("learn")
    await mark_stale_for_policy_change(
        db_session,
        path="learn",
        previous_policy_hash=policy_hash,
        path_lesson_id=lesson.id,
    )
    await db_session.refresh(learn_row)
    assert learn_row.status == "stale"
    await db_session.refresh(new_print)
    assert new_print.status == "queued"
    assert new_print.path == "print"


@pytest.mark.asyncio
async def test_p03_r05_legacy_backfill_ambiguous_read_only(db_session: AsyncSession) -> None:
    """P03-R05: migration backfill; ambiguous legacy is read-only, not guessed."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r05")

    unambiguous = await backfill_legacy_realization(
        db_session,
        path_lesson_id=lesson.id,
        pack_id="legacy-print-pack",
        chunked={
            "native_whole_lesson": True,
            "page_document_v2": True,
            "teaching_plan_id": "tp-legacy",
            "teaching_review": {"approved_revision": 1},
            "teaching_plan": {"preparation_hash": "legacy-hash", "revision": 1},
        },
        planning_spec={"document_contract_version": 2},
        generation_status="completed",
    )
    assert unambiguous.path == "print"
    assert unambiguous.status == "ready"
    assert unambiguous.variant_id == DEFAULT_VARIANT_ID

    ambiguous_chunked = {
        "shared_preparation": True,
        "stage": "awaiting_review",
        # Conflicting / incomplete markers — do not invent a path.
    }
    assert classify_legacy_chunked(ambiguous_chunked) is None
    ambiguous = await backfill_legacy_realization(
        db_session,
        path_lesson_id=lesson.id,
        pack_id="legacy-ambiguous-pack",
        chunked=ambiguous_chunked,
        planning_spec={"document_contract_version": 1},
        generation_status="awaiting_review",
    )
    assert ambiguous.status == "read_only"
    assert ambiguous.variant_id == LEGACY_AMBIGUOUS_VARIANT
    assert ambiguous.error_summary and "Ambiguous" in ambiguous.error_summary
    assert ambiguous.output_id == "legacy-ambiguous-pack"

    with pytest.raises(RealizationReadOnlyError):
        await retry_realization(db_session, realization_id=ambiguous.id)

    # Explicit regenerate still allowed under normal variant keys.
    fresh = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["learn"],
        teaching_plan_id="tp-legacy",
        teaching_plan_revision=1,
        teaching_plan_hash="legacy-hash",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    assert fresh[0][1] is True
    assert fresh[0][0].path == "learn"
    assert fresh[0][0].status == "queued"


@pytest.mark.asyncio
async def test_p03_r06_concurrent_uniqueness_and_status_routing(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """P03-R06: concurrent creates unique; status/open identify the correct artifact."""
    async with db_session_factory() as setup:
        lesson = await _prepared_lesson(setup, user_id="p03-r06")
        await setup.commit()
        lesson_id = lesson.id
        pack_id = lesson.pack_id
        user_id = "p03-r06"

    async def _admit_once(label: str) -> str:
        async with db_session_factory() as session:
            results = await request_outputs(
                session,
                path_lesson_id=lesson_id,
                paths=["print"],
                teaching_plan_id="tp-p03-r06",
                teaching_plan_revision=1,
                teaching_plan_hash="hash-rev-1",
                preparation_generation_id=pack_id,
                pack_id=pack_id,
            )
            row, _created = results[0]
            # Attach a path-specific output artifact for open routing.
            if row.output_id is None:
                output_id = f"print-artifact-{label}"
                session.add(
                    GenerationModel(
                        id=output_id,
                        user_id=user_id,
                        subject="science",
                        context="print realization",
                        status="ready",
                        requested_template_id="lesson",
                        requested_preset_id="standard",
                        created_at=_utcnow(),
                        document_json={"sections": [{"id": "s1"}], "path": "print"},
                        chunked_state_json={"stage": "ready", "native_whole_lesson": True},
                    )
                )
                row.output_id = output_id
                row.status = "ready"
            await session.commit()
            return row.id

    ids = await asyncio.gather(*[_admit_once(str(i)) for i in range(8)])
    assert len(set(ids)) == 1

    async with db_session_factory() as session:
        # Admit Learn with a distinct artifact.
        learn_results = await request_outputs(
            session,
            path_lesson_id=lesson_id,
            paths=["learn"],
            teaching_plan_id="tp-p03-r06",
            teaching_plan_revision=1,
            teaching_plan_hash="hash-rev-1",
            preparation_generation_id=pack_id,
            pack_id=pack_id,
        )
        learn_row = learn_results[0][0]
        learn_output = f"learn-artifact-{uuid.uuid4().hex[:8]}"
        session.add(
            GenerationModel(
                id=learn_output,
                user_id=user_id,
                subject="science",
                context="learn realization",
                status="ready",
                requested_template_id="lesson",
                requested_preset_id="standard",
                created_at=_utcnow(),
                document_json={"sections": [{"id": "learn"}], "path": "learn"},
                chunked_state_json={
                    "stage": "ready",
                    "control": {"pipeline": "component_lectio", "pipeline_version": 1},
                },
            )
        )
        learn_row.output_id = learn_output
        learn_row.status = "ready"
        await session.commit()

        print_row = await resolve_by_path(session, path_lesson_id=lesson_id, path="print")
        learn_resolved = await resolve_by_path(session, path_lesson_id=lesson_id, path="learn")
        assert print_row is not None and learn_resolved is not None
        print_id = to_identity(print_row)
        learn_id = to_identity(learn_resolved)
        assert print_id.output_id != learn_id.output_id
        assert print_id.open_href == f"/studio/print/{print_id.output_id}"
        assert learn_id.open_href == f"/studio?generation_id={learn_id.output_id}"
        assert print_id.path == "print"
        assert learn_id.path == "learn"

        all_rows = await list_realizations_for_lesson(session, path_lesson_id=lesson_id)
        assert len([r for r in all_rows if r.variant_id == DEFAULT_VARIANT_ID]) == 2
        # Uniqueness still holds after the concurrent race.
        count = await session.scalar(
            select(func.count()).select_from(NativeRealizationModel).where(
                NativeRealizationModel.path_lesson_id == lesson_id,
                NativeRealizationModel.path == "print",
                NativeRealizationModel.teaching_plan_revision == 1,
                NativeRealizationModel.variant_id == DEFAULT_VARIANT_ID,
                NativeRealizationModel.native_policy_hash == policy_for("print")[1],
                NativeRealizationModel.package_contract_hash == package_contract_for("print")[1],
            )
        )
        assert count == 1


@pytest.mark.asyncio
async def test_p03_policy_hash_helper_stable() -> None:
    """Sanity: policy/package hashes are stable fingerprints used in identity keys."""
    v1, h1 = policy_for("print")
    v2, h2 = policy_for("print")
    assert v1 == v2 and h1 == h2
    assert policy_for("print")[1] != policy_for("learn")[1]
    assert package_contract_for("print")[1] != package_contract_for("learn")[1]
    assert canonical_hash({"a": 1}) == canonical_hash({"a": 1})
