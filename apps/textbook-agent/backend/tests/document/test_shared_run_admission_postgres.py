from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

pytest_plugins = ("tests.generation_runtime.test_runtime_postgres",)

from test_shared_composer_admission import _source
from test_shared_run_admission import _snapshot

from document.shared_lesson import run_admission
from document.shared_lesson.run_admission import admit_shared_document_run
from infra.database.models import GenerationBuildModel, GenerationRunModel, GenerationWorkItemModel


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_concurrent_duplicate_admission_has_one_build_run_and_item(
    pg_runtime,
    pg_fixture,
    monkeypatch,
) -> None:
    _engine, factory = pg_runtime
    fixture = pg_fixture
    source, _sourcebook = _source()

    async def current_source(**_kwargs):
        return source

    async def current_snapshot(**_kwargs):
        return await _snapshot(source)

    monkeypatch.setattr(run_admission, "load_current_approved_teaching_plan_source", current_source)
    monkeypatch.setattr(run_admission, "load_approved_item_snapshot", current_snapshot)

    owner_id = str(fixture["owner_id"])
    lesson_id = str(fixture["lesson_id"])
    async with factory() as baseline_session:
        baseline_builds = await baseline_session.scalar(
            select(func.count())
            .select_from(GenerationBuildModel)
            .where(GenerationBuildModel.owner_user_id == owner_id)
        )

    async def admit_once() -> tuple[bool, bool, str, str]:
        async with factory() as session:
            result = await admit_shared_document_run(
                session,
                owner_user_id=owner_id,
                path_lesson_id=lesson_id,
                preparation_generation_id="preparation-not-needed-in-loader-mock",
                request_key="postgres-concurrent-request",
            )
            await session.commit()
            return (
                result.run_admission.created,
                result.sourcebook_admission.created,
                result.run.id,
                result.sourcebook_work_item.id,
            )

    outcomes = await asyncio.gather(admit_once(), admit_once(), return_exceptions=True)
    assert all(not isinstance(outcome, Exception) for outcome in outcomes), outcomes
    values = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    assert sorted(value[0] for value in values) == [False, True]
    assert sorted(value[1] for value in values) == [False, True]
    assert len({value[2] for value in values}) == 1
    assert len({value[3] for value in values}) == 1

    async with factory() as verify:
        run_id = values[0][2]
        build_id = await verify.scalar(
            select(GenerationRunModel.build_id).where(GenerationRunModel.id == run_id)
        )
        assert build_id is not None
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationBuildModel)
                .where(GenerationBuildModel.owner_user_id == owner_id)
            )
            == baseline_builds + 1
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationBuildModel)
                .where(GenerationBuildModel.id == build_id)
            )
            == 1
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationRunModel)
                .where(GenerationRunModel.request_key == "postgres-concurrent-request")
            )
            == 1
        )
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(GenerationWorkItemModel)
                .where(GenerationWorkItemModel.item_key == "sourcebook")
            )
            == 1
        )
