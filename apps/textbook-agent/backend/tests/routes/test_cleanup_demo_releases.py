"""Cleanup script (work order 38 section 4): dry run writes nothing, apply deletes in FK order."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select

from infra.database.models import (
    ConceptEvidenceModel,
    EditableLessonModel,
    LearnAssignmentModel,
    LearnerAttemptModel,
    LearnerIdentityModel,
    LearningInstanceModel,
    LearnReleaseModel,
    LessonProgressModel,
)
from tests.routes.test_learn_anonymous_learner import (  # noqa: F401  (fixtures + helpers)
    _ATTEMPT,
    _client,
    _first_instance,
    _h,
    _join,
    _overrides,
    _seed,
    _teacher_setup,
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cleanup_demo_releases.py"
_spec = importlib.util.spec_from_file_location("cleanup_demo_releases", _SCRIPT)
cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cleanup)


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.mark.asyncio
async def test_dry_run_writes_nothing_and_apply_deletes_in_order(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _teacher_setup(client, _overrides)
        joined = await _join(client, ctx["invite"], "Ann")
        iid = (await _first_instance(client, joined))["id"]
        res = await client.post(
            f"/api/v1/learn/instances/{iid}/attempts", json=_ATTEMPT, headers=_h(joined["token"])
        )
        assert res.status_code == 200, res.text

    tracked = [
        LearnReleaseModel,
        LearnAssignmentModel,
        LearningInstanceModel,
        LearnerAttemptModel,
        LessonProgressModel,
        ConceptEvidenceModel,
    ]
    async with db_session_factory() as session:
        before = {m.__name__: await _count(session, m) for m in tracked}
        lessons = await _count(session, EditableLessonModel)
        learners = await _count(session, LearnerIdentityModel)
    assert before["LearnReleaseModel"] == 2
    assert before["LearningInstanceModel"] == 1
    assert before["LearnerAttemptModel"] == 1

    async with db_session_factory() as session:
        dry = await cleanup.run_cleanup(session, apply=False)
    assert dry["counts"]["learn_releases"] == 2
    assert dry["counts"]["learner_attempts"] == 1
    assert dry["counts"]["learning_instances"] == 1
    assert dry["counts"]["learn_assignments"] == 1
    async with db_session_factory() as session:
        assert {m.__name__: await _count(session, m) for m in tracked} == before

    async with db_session_factory() as session:
        done = await cleanup.run_cleanup(session, apply=True)
    assert done["applied"] is True
    async with db_session_factory() as session:
        for m in tracked:
            assert await _count(session, m) == 0, m.__name__
        assert await _count(session, EditableLessonModel) == lessons
        assert await _count(session, LearnerIdentityModel) == learners
