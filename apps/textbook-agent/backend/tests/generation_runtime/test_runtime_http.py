from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import app
from core.entities.user import User
from infra.auth.middleware import get_current_user
from infra.database.models import (
    ConceptModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.database.session import get_async_session
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    BuildAdmission,
    RunAdmission,
    RunType,
    admit_run,
    create_build,
)


async def _seed_owned_lesson(session: AsyncSession, suffix: str) -> tuple[str, str]:
    owner_id = f"runtime-http-owner-{suffix}"
    lesson_id = f"runtime-http-lesson-{suffix}"
    concept = ConceptModel(
        id=f"runtime-http-concept-{suffix}",
        canonical_slug=f"runtime-http.{suffix}",
        subject="Science",
        title="HTTP status fixture",
        created_by=owner_id,
    )
    unit = UnitModel(
        id=f"runtime-http-unit-{suffix}",
        owner_id=owner_id,
        title="HTTP status fixture",
        topic="Runtime status",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Expose owner-scoped status.",
    )
    version = PathVersionModel(
        id=f"runtime-http-path-{suffix}",
        unit_id=unit.id,
        version=1,
        source_plan_json={},
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="HTTP status fixture",
        objective="Expose owner-scoped status.",
        objective_hash="objective-http",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all(
        [
            UserModel(id=owner_id, email=f"{owner_id}@example.invalid"),
            concept,
            unit,
            version,
            lesson,
        ]
    )
    await session.flush()
    return owner_id, lesson_id


async def _seed_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    suffix: str,
    status: str = "queued",
    item_specs: tuple[dict, ...] = (),
) -> tuple[str, str, list[str]]:
    async with session_factory() as session:
        owner_id, lesson_id = await _seed_owned_lesson(session, suffix)
        build = await create_build(
            session,
            BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
        )
        admitted = await admit_run(
            session,
            RunAdmission(
                build_id=build.id,
                owner_user_id=owner_id,
                run_type=RunType.SHARED_DOCUMENT,
                request_key=f"http-request-{suffix}",
                stage="section_writing",
                source_artifact_type="teaching_plan",
                source_artifact_id=f"plan-{suffix}",
                source_revision=3,
                source_hash="source-hash",
            ),
        )
        run = admitted.record
        run.status = status
        if status == "ready":
            run.output_artifact_type = "shared_document"
            run.output_artifact_id = f"document-{suffix}"
            run.output_revision = 1
            run.output_hash = "output-hash"
        run.error_code = "provider_output" if status == "failed_recoverable" else None
        run.error_class = "provider_output" if status == "failed_recoverable" else None
        run.error_summary = "Safe run failure summary." if status == "failed_recoverable" else None
        run.recovery_action = "retry" if status == "failed_recoverable" else None
        item_ids = []
        item_ids_by_key = {}
        for spec in item_specs:
            item = GenerationWorkItemModel(
                id=f"runtime-http-item-{suffix}-{spec['key']}",
                run_id=run.id,
                replaces_work_item_id=item_ids_by_key.get(spec.get("replaces_key")),
                item_key=spec["key"],
                stage=spec.get("stage", "section_writing"),
                status=spec.get("status", "queued"),
                attempt=spec.get("attempt", 1),
                max_attempts=spec.get("max_attempts", 3),
                input_hash=spec.get("input_hash", "input-hash"),
                definition_hash=spec.get("definition_hash", "definition-hash"),
                output_json=spec.get("output_json"),
                output_hash=spec.get("output_hash"),
                error_code=spec.get("error_code"),
                error_class=spec.get("error_class"),
                error_summary=spec.get("error_summary"),
                recovery_action=spec.get("recovery_action"),
            )
            session.add(item)
            item_ids.append(item.id)
            item_ids_by_key[spec["key"]] = item.id
        await session.commit()
        return owner_id, run.id, item_ids


@pytest.fixture
async def runtime_http(db_session_factory):
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


async def test_generation_status_requires_authentication() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/generation/runs/missing")
    assert response.status_code == 401


async def test_replacement_history_does_not_inflate_run_progress(runtime_http, db_session_factory):
    client, identity = runtime_http
    owner_id, run_id, item_ids = await _seed_run(
        db_session_factory,
        suffix="replacement-progress",
        item_specs=(
            {
                "key": "original",
                "status": "ready",
                "output_json": {"section": "old"},
                "output_hash": content_hash({"section": "old"}),
            },
            {
                "key": "replacement",
                "replaces_key": "original",
                "status": "queued",
            },
            {
                "key": "sibling",
                "status": "ready",
                "output_json": ["kept"],
                "output_hash": content_hash(["kept"]),
            },
        ),
    )
    identity["user_id"] = owner_id
    response = await client.get(f"/api/v1/generation/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["progress"] == {
        "active": 1,
        "completed": 1,
        "failed": 0,
        "cancelled": 0,
        "total": 2,
    }
    historical, replacement, _sibling = body["work_items"]
    assert historical["id"] == item_ids[0]
    assert historical["current"] is False
    assert historical["replaced_by"] == item_ids[1]
    assert replacement["current"] is True


async def test_status_is_owner_scoped_and_omits_private_runtime_payloads(
    runtime_http, db_session_factory
) -> None:
    client, identity = runtime_http
    owner_id, run_id, _ = await _seed_run(
        db_session_factory,
        suffix="owner-scope",
        item_specs=(
            {
                "key": "private",
                "status": "running",
                "stage": "item_stage",
                "output_json": {"secret": "must not escape"},
                "error_code": "safe-code",
                "error_class": "validation",
                "error_summary": "Safe summary.",
            },
        ),
    )
    identity["user_id"] = owner_id
    response = await client.get(f"/api/v1/generation/runs/{run_id}")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "queued"
    assert body["stage"] == "item_stage"
    assert body["active_stages"] == ["item_stage"]
    assert body["run_stage"] == "section_writing"
    assert body["progress"] == {
        "active": 1,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 1,
    }
    assert body["latest_error"] == {
        "code": "safe-code",
        "class": "validation",
        "summary": "Safe summary.",
    }
    assert body["source"] == {
        "type": "teaching_plan",
        "id": "plan-owner-scope",
        "revision": 3,
        "hash": "source-hash",
    }
    serialized = response.text
    assert "secret" not in serialized
    assert "checkpoint_json" not in serialized
    assert "lease_token" not in serialized

    async with db_session_factory() as session:
        foreign_owner_id = "runtime-http-foreign-run-owner"
        session.add(
            UserModel(
                id=foreign_owner_id,
                email=f"{foreign_owner_id}@example.invalid",
            )
        )
        session.add(
            GenerationRunModel(
                id="runtime-http-foreign-run",
                build_id=body["build_id"],
                run_type="shared_document",
                owner_user_id=foreign_owner_id,
                status="running",
                stage="foreign-stage",
                attempt=1,
                source_artifact_type="teaching_plan",
                source_artifact_id="foreign-plan",
                source_revision=1,
                source_hash="foreign-source-hash",
                request_key="foreign-run-request",
            )
        )
        await session.commit()
    build_status = await client.get(f"/api/v1/generation/builds/{body['build_id']}")
    assert [run["id"] for run in build_status.json()["runs"]] == [run_id]

    identity["user_id"] = "different-owner"
    hidden_run = await client.get(f"/api/v1/generation/runs/{run_id}")
    hidden_build = await client.get(f"/api/v1/generation/builds/{body['build_id']}")
    missing_run = await client.get("/api/v1/generation/runs/unknown-id")
    assert hidden_run.status_code == hidden_build.status_code == missing_run.status_code == 404
    assert hidden_run.json() == hidden_build.json() == missing_run.json()


async def test_retry_action_is_targeted_and_preserves_ready_sibling(
    runtime_http, db_session_factory
) -> None:
    client, identity = runtime_http
    owner_id, run_id, item_ids = await _seed_run(
        db_session_factory,
        suffix="retry-action",
        status="failed_recoverable",
        item_specs=(
            {
                "key": "ready",
                "status": "ready",
                "output_json": ["stable"],
                "output_hash": content_hash(["stable"]),
            },
            {
                "key": "retry",
                "status": "failed_recoverable",
                "error_code": "provider_output",
                "error_class": "provider_output",
                "error_summary": "Safe item failure.",
                "recovery_action": "retry",
            },
        ),
    )
    identity["user_id"] = owner_id
    before = await client.get(f"/api/v1/generation/runs/{run_id}")
    before_items = {item["key"]: item for item in before.json()["work_items"]}
    assert before.json()["progress"] == {
        "active": 0,
        "completed": 1,
        "failed": 1,
        "cancelled": 0,
        "total": 2,
    }
    assert before_items["retry"]["allowed_actions"] == ["retry"]
    assert before_items["ready"]["allowed_actions"] == []

    retry = await client.post(f"/api/v1/generation/work-items/{item_ids[1]}/retry")
    assert retry.status_code == 200
    body = retry.json()
    after_items = {item["key"]: item for item in body["work_items"]}
    assert body["progress"] == {
        "active": 1,
        "completed": 1,
        "failed": 0,
        "cancelled": 0,
        "total": 2,
    }
    assert after_items["retry"]["status"] == "queued"
    assert after_items["retry"]["attempt"] == 2
    assert after_items["ready"]["status"] == "ready"
    assert after_items["ready"]["attempt"] == 1

    identity["user_id"] = "other-owner"
    hidden_retry = await client.post(f"/api/v1/generation/work-items/{item_ids[1]}/retry")
    missing_retry = await client.post("/api/v1/generation/work-items/unknown-item/retry")
    assert hidden_retry.status_code == missing_retry.status_code == 404
    assert hidden_retry.json() == missing_retry.json()


async def test_cancel_action_updates_run_and_preserves_ready_output(
    runtime_http, db_session_factory
) -> None:
    client, identity = runtime_http
    owner_id, run_id, _ = await _seed_run(
        db_session_factory,
        suffix="cancel-action",
        status="running",
        item_specs=(
            {
                "key": "ready",
                "status": "ready",
                "output_json": {"stable": True},
                "output_hash": content_hash({"stable": True}),
            },
            {"key": "queued", "status": "queued"},
        ),
    )
    identity["user_id"] = owner_id
    response = await client.post(f"/api/v1/generation/runs/{run_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    items = {item["key"]: item for item in body["work_items"]}
    assert items["ready"]["status"] == "ready"
    assert items["queued"]["status"] == "cancelled"
    assert body["progress"] == {
        "active": 0,
        "completed": 1,
        "failed": 0,
        "cancelled": 1,
        "total": 2,
    }
    assert body["allowed_actions"] == []

    repeated = await client.post(f"/api/v1/generation/runs/{run_id}/cancel")
    assert repeated.status_code == 200
    assert repeated.json() == body

    ready_owner_id, ready_run_id, _ = await _seed_run(
        db_session_factory,
        suffix="cancel-ready",
        status="ready",
    )
    identity["user_id"] = ready_owner_id
    illegal = await client.post(f"/api/v1/generation/runs/{ready_run_id}/cancel")
    assert illegal.status_code == 409


async def test_build_status_lists_owned_run_summaries(runtime_http, db_session_factory) -> None:
    client, identity = runtime_http
    owner_id, run_id, _ = await _seed_run(db_session_factory, suffix="build-status")
    identity["user_id"] = owner_id
    run = (await client.get(f"/api/v1/generation/runs/{run_id}")).json()
    response = await client.get(f"/api/v1/generation/builds/{run['build_id']}")
    assert response.status_code == 200
    assert [value["id"] for value in response.json()["runs"]] == [run_id]
    assert response.json()["aggregate"]["status"] == "queued"
    assert response.json()["aggregate"]["progress"] == {
        "active": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 0,
    }


async def test_empty_build_status_has_no_invented_lifecycle_state(
    runtime_http, db_session_factory
) -> None:
    client, identity = runtime_http
    suffix = "empty-build"
    async with db_session_factory() as session:
        owner_id, lesson_id = await _seed_owned_lesson(session, suffix)
        build = await create_build(
            session,
            BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
        )
        await session.commit()
        build_id = build.id
    identity["user_id"] = owner_id
    response = await client.get(f"/api/v1/generation/builds/{build_id}")
    assert response.status_code == 200
    assert response.json()["runs"] == []
    assert response.json()["aggregate"] == {
        "status": None,
        "runs": 0,
        "ready_runs": 0,
        "active_runs": 0,
        "failed_runs": 0,
        "cancelled_runs": 0,
        "progress": {
            "active": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "total": 0,
        },
    }


async def test_build_aggregate_precedence_handles_mixed_run_outcomes(
    runtime_http, db_session_factory
) -> None:
    client, identity = runtime_http
    owner_id, active_run_id, _ = await _seed_run(
        db_session_factory,
        suffix="mixed-build",
        item_specs=({"key": "queued", "status": "queued"},),
    )
    async with db_session_factory() as session:
        active_run = await session.get(GenerationRunModel, active_run_id)
        assert active_run is not None
        failed_run = GenerationRunModel(
            id="runtime-http-failed-run-mixed-build",
            build_id=active_run.build_id,
            run_type="shared_document",
            owner_user_id=owner_id,
            status="failed_terminal",
            stage="section_writing",
            attempt=1,
            source_artifact_type="teaching_plan",
            source_artifact_id="failed-plan",
            source_revision=1,
            source_hash="failed-source-hash",
            request_key="failed-request-mixed-build",
        )
        session.add(failed_run)
        await session.commit()
        build_id = active_run.build_id

    identity["user_id"] = owner_id
    response = await client.get(f"/api/v1/generation/builds/{build_id}")
    aggregate = response.json()["aggregate"]
    assert aggregate["status"] == "queued"
    assert aggregate["active_runs"] == 1
    assert aggregate["failed_runs"] == 1
    assert aggregate["progress"] == {
        "active": 1,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "total": 1,
    }

    async with db_session_factory() as session:
        active_run = await session.get(GenerationRunModel, active_run_id)
        assert active_run is not None
        active_run.status = "ready"
        active_run.output_artifact_type = "shared_document"
        active_run.output_artifact_id = "ready-document-mixed-build"
        active_run.output_revision = 1
        active_run.output_hash = "ready-output-hash"
        await session.commit()
    terminal_response = await client.get(f"/api/v1/generation/builds/{build_id}")
    assert terminal_response.json()["aggregate"]["status"] is None
