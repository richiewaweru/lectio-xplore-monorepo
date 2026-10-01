from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import app
from core.database.models import (
    ConceptModel,
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from core.entities.user import User
from curriculum.planning.objective_ownership import hash_path_objective
from curriculum.shared_task_authoring import ApprovedItemSnapshot
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson import run_admission
from document.shared_lesson.runtime import TeachingPlanSource
from infra.auth.middleware import get_current_user
from infra.database.models import GenerationBuildModel, GenerationRunModel
from infra.database.session import get_async_session


def _plan(user_id: str) -> TeachingPlan:
    return TeachingPlan(
        contract_version=2,
        teaching_plan_id=f"plan-{user_id}",
        revision=1,
        preparation_hash="preparation-hash",
        approval_status="pending",
        learner_title="How water reaches a leaf",
        arc="Trace water movement from roots to leaves.",
        starting_state=["Learner can name a root."],
        target_state=["Learner can explain water movement."],
        sections=[
            {
                "slot_id": "orient",
                "display_title": "Start with the root",
                "specific_purpose": "Connect the observation to the question.",
                "entry_state": ["Learner can name a root."],
                "must_establish": ["Roots take in water."],
                "avoid_repeating": [],
                "bridge_from_previous": None,
                "exit_state": ["Learner can describe root uptake."],
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Observe a plant root.",
                        "evidence": "Learner identifies the root.",
                    }
                ],
            }
        ],
    )


async def _prepared(db_session, *, user_id: str = "source-owner"):
    user = UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id)
    unit = UnitModel(
        id=f"unit-{user_id}",
        owner_id=user_id,
        title="Water movement",
        topic="Plants",
        subject="Science",
        grade_level="4",
        destination_objective="Explain water movement.",
    )
    concept = ConceptModel(
        id=f"concept-{user_id}",
        canonical_slug=f"water-{user_id}",
        subject="Science",
        title="Water movement",
        created_by=user_id,
    )
    version = PathVersionModel(
        id=f"version-{user_id}",
        unit_id=unit.id,
        version=1,
        source_plan_json={"lessons": []},
        status="approved",
    )
    lesson = PathLessonModel(
        id=f"lesson-{user_id}",
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug="water-movement",
        title="Water movement",
        objective="Explain how water reaches a leaf.",
        objective_hash=hash_path_objective("Explain how water reaches a leaf."),
        primary_knowledge_type="conceptual",
        position=0,
        revision=3,
    )
    plan = _plan(user_id)
    state: dict[str, object] = {"teaching_plan_id": plan.teaching_plan_id}
    store = TeachingRevisionStore(state)
    store.record_draft(plan, preparation_hash="preparation-hash", revision=1)
    record = store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
        reviewed_by=user_id,
    )
    generation_id = f"prep-{user_id}"
    generation = GenerationModel(
        id=generation_id,
        user_id=user_id,
        subject="Science",
        context="shared preparation",
        status="awaiting_review",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"page_document_v2": state},
    )
    lesson.pack_id = generation_id
    provenance = LessonProvenanceModel(
        pack_id=generation_id,
        path_version_id=version.id,
        path_lesson_id=lesson.id,
        objective_hash=lesson.objective_hash,
        path_lesson_revision=lesson.revision,
    )
    db_session.add_all([user, unit, concept, version, lesson, generation, provenance])
    await db_session.flush()
    source = TeachingPlanSource(
        plan=TeachingPlan.model_validate(record.plan),
        revision_record=record,
        id=record.teaching_plan_id,
        revision=record.revision,
        content_hash=record.content_hash or "",
    )
    return generation, lesson, source


async def _resolved(value):
    return value


async def _snapshot(source):
    return ApprovedItemSnapshot(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        items={},
    )


@pytest.fixture
async def admission_http(db_session_factory):
    identity = {"user_id": None}

    async def current_user() -> User:
        user_id = identity["user_id"]
        return User(
            id=user_id,
            email=f"{user_id}@example.invalid",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def db_session_override():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_async_session] = db_session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, identity
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_async_session, None)


async def _seed_preparation(db_session_factory, *, user_id: str = "source-owner"):
    async with db_session_factory() as session:
        generation, lesson, source = await _prepared(session, user_id=user_id)
        await session.commit()
    return generation.id, lesson.id, source


async def _count_builds(db_session_factory, *, owner_id: str) -> int:
    async with db_session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(GenerationBuildModel)
                .where(GenerationBuildModel.owner_user_id == owner_id)
            )
            or 0
        )


async def test_admission_requires_authentication() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/shared-documents/generations",
            json={
                "path_lesson_id": "lesson",
                "preparation_generation_id": "preparation",
                "request_key": "request",
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admission_returns_queued_run_identity_and_status(admission_http, db_session_factory):
    client, identity = admission_http
    preparation_id, lesson_id, _source = await _seed_preparation(db_session_factory)
    identity["user_id"] = "source-owner"

    response = await client.post(
        "/api/v1/shared-documents/generations",
        json={
            "path_lesson_id": lesson_id,
            "preparation_generation_id": preparation_id,
            "request_key": "route-admission-request",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["stage"] == "sourcebook_generation"
    assert body["build_id"]
    assert body["run_id"]
    assert body["sourcebook_work_item_id"]
    assert body["source"] == {
        "type": "teaching_plan",
        "id": "plan-source-owner",
        "revision": 1,
        "hash": body["source"]["hash"],
    }
    assert body["progress"] == {
        "active": 1,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 1,
    }
    assert body["latest_error"] is None
    assert body["output"] is None
    assert body["work_items"] == [
        {
            "id": body["sourcebook_work_item_id"],
            "key": "sourcebook",
            "stage": "sourcebook_generation",
            "status": "queued",
            "current": True,
            "replaced_by": None,
            "attempt": 1,
            "max_attempts": 3,
            "latest_error": None,
            "allowed_actions": [],
            "links": {},
        }
    ]
    assert body["links"]["status"] == f"/api/v1/generation/runs/{body['run_id']}"
    assert body["links"]["build"] == f"/api/v1/generation/builds/{body['build_id']}"
    assert await _count_builds(db_session_factory, owner_id="source-owner") == 1


@pytest.mark.asyncio
async def test_duplicate_admission_reuses_ids(admission_http, db_session_factory):
    client, identity = admission_http
    preparation_id, lesson_id, _source = await _seed_preparation(db_session_factory)
    identity["user_id"] = "source-owner"
    request = {
        "path_lesson_id": lesson_id,
        "preparation_generation_id": preparation_id,
        "request_key": "route-duplicate-request",
    }

    first = await client.post("/api/v1/shared-documents/generations", json=request)
    second = await client.post("/api/v1/shared-documents/generations", json=request)

    assert first.status_code == second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["build_id"] == first.json()["build_id"]
    assert second.json()["sourcebook_work_item_id"] == first.json()["sourcebook_work_item_id"]
    assert await _count_builds(db_session_factory, owner_id="source-owner") == 1


@pytest.mark.asyncio
async def test_hash_conflict_returns_409_without_new_build(
    admission_http,
    db_session_factory,
    monkeypatch,
):
    client, identity = admission_http
    preparation_id, lesson_id, source = await _seed_preparation(db_session_factory)
    identity["user_id"] = "source-owner"
    request = {
        "path_lesson_id": lesson_id,
        "preparation_generation_id": preparation_id,
        "request_key": "route-hash-conflict",
    }
    first = await client.post("/api/v1/shared-documents/generations", json=request)
    assert first.status_code == 202

    plan = source.plan.model_copy(update={"arc": "Changed approved arc"})
    digest = teaching_plan_content_hash(plan)
    variant = source.model_copy(
        update={
            "plan": plan,
            "content_hash": digest,
            "revision_record": source.revision_record.model_copy(
                update={"content_hash": digest, "plan": plan.model_dump(mode="json")}
            ),
        }
    )
    monkeypatch.setattr(
        run_admission,
        "load_current_approved_teaching_plan_source",
        lambda **_kwargs: _resolved(variant),
    )
    monkeypatch.setattr(
        run_admission,
        "load_approved_item_snapshot",
        lambda **_kwargs: _snapshot(variant),
    )

    response = await client.post("/api/v1/shared-documents/generations", json=request)

    assert response.status_code == 409
    assert "different run identity" in response.json()["detail"]
    assert await _count_builds(db_session_factory, owner_id="source-owner") == 1


@pytest.mark.asyncio
async def test_foreign_owner_and_invalid_snapshot_fail_before_build(
    admission_http, db_session_factory
):
    client, identity = admission_http
    preparation_id, lesson_id, _source = await _seed_preparation(db_session_factory)
    identity["user_id"] = "other-owner"
    request = {
        "path_lesson_id": lesson_id,
        "preparation_generation_id": preparation_id,
        "request_key": "route-foreign-owner",
    }
    response = await client.post("/api/v1/shared-documents/generations", json=request)
    assert response.status_code == 404
    assert await _count_builds(db_session_factory, owner_id="source-owner") == 0

    identity["user_id"] = "source-owner"
    async with db_session_factory() as session:
        generation = await session.get(GenerationModel, preparation_id)
        assert generation is not None
        state = deepcopy(generation.chunked_state_json)
        page = state["page_document_v2"]
        page["teaching_revisions"][0]["approved_item_snapshot"] = None
        page["teaching_revisions"][0]["approved_item_snapshot_hash"] = None
        generation.chunked_state_json = state
        await session.commit()

    request["request_key"] = "route-invalid-snapshot"
    response = await client.post("/api/v1/shared-documents/generations", json=request)
    assert response.status_code == 404
    assert await _count_builds(db_session_factory, owner_id="source-owner") == 0


@pytest.mark.asyncio
async def test_admission_rolls_back_build_and_run_on_post_admission_failure(
    admission_http,
    db_session_factory,
    monkeypatch,
):
    client, identity = admission_http
    preparation_id, lesson_id, _source = await _seed_preparation(db_session_factory)
    identity["user_id"] = "source-owner"
    real_admit = run_admission.admit_shared_document_run

    async def admit_then_fail(*args, **kwargs):
        await real_admit(*args, **kwargs)
        raise RuntimeError("deliberate route rollback")

    import document.shared_lesson.http as shared_http

    monkeypatch.setattr(shared_http, "admit_shared_document_run", admit_then_fail)
    response = await client.post(
        "/api/v1/shared-documents/generations",
        json={
            "path_lesson_id": lesson_id,
            "preparation_generation_id": preparation_id,
            "request_key": "route-rollback",
        },
    )

    assert response.status_code == 500
    assert await _count_builds(db_session_factory, owner_id="source-owner") == 0
    async with db_session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(GenerationRunModel)
                .where(GenerationRunModel.request_key == "route-rollback")
            )
            == 0
        )
