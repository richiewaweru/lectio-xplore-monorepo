from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.entities.user import User
from document.shared_lesson import build_shared_lesson_document
from infra.auth.middleware import get_current_user
from infra.database.models import (
    ConceptModel,
    GenerationBuildModel,
    GenerationRunModel,
    PathLessonModel,
    PathVersionModel,
    SharedLessonDocumentModel,
    UnitModel,
    UserModel,
)
from infra.database.session import get_async_session
from infra.execution.checkpoints import content_hash


def _document(document_id: str):
    return build_shared_lesson_document(
        {
            "id": document_id,
            "revision": 1,
            "teaching_plan_id": "plan-preview",
            "teaching_plan_revision": 3,
            "teaching_plan_hash": "a" * 64,
            "title": "Photosynthesis",
            "sections": [
                {
                    "id": "section-preview",
                    "title": "How plants make food",
                    "position": 0,
                    "nodes": [
                        {
                            "id": "paragraph-preview",
                            "kind": "paragraph",
                            "display": {"text": "Plants use light."},
                        }
                    ],
                }
            ],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )


async def _seed_preview(
    db_session_factory,
    *,
    suffix: str,
    owner_id: str,
    document_status: str = "ready",
    output_hash: str | None = None,
) -> tuple[str, object]:
    lesson_id = f"preview-lesson-{suffix}"
    document = _document(f"preview-document-{suffix}")
    async with db_session_factory() as session:
        concept = ConceptModel(
            id=f"preview-concept-{suffix}",
            canonical_slug=f"preview.{suffix}",
            subject="Science",
            title="Preview fixture",
            created_by=owner_id,
        )
        unit = UnitModel(
            id=f"preview-unit-{suffix}",
            owner_id=owner_id,
            title="Preview fixture",
            topic="Preview",
            subject="Science",
            grade_level="Grade 7",
            destination_objective="Preview immutable content.",
        )
        version = PathVersionModel(
            id=f"preview-path-{suffix}",
            unit_id=unit.id,
            version=1,
            source_plan_json={},
        )
        lesson = PathLessonModel(
            id=lesson_id,
            path_version_id=version.id,
            concept_id=concept.id,
            concept_slug=concept.canonical_slug,
            title="Preview fixture",
            objective="Preview immutable content.",
            objective_hash="preview-objective",
            primary_knowledge_type="conceptual",
            position=0,
        )
        build = GenerationBuildModel(
            id=f"preview-build-{suffix}",
            path_lesson_id=lesson_id,
            owner_user_id=owner_id,
        )
        run = GenerationRunModel(
            id=f"preview-run-{suffix}",
            build_id=build.id,
            run_type="shared_document",
            owner_user_id=owner_id,
            status="ready",
            stage="document_qa",
            source_artifact_type="teaching_plan",
            source_artifact_id="plan-preview",
            source_revision=3,
            source_hash="b" * 64,
            output_artifact_type="shared_lesson_document",
            output_artifact_id=document.id,
            output_revision=document.revision,
            output_hash=output_hash or content_hash(document.model_dump(mode="json")),
            request_key=f"preview-request-{suffix}",
        )
        stored = SharedLessonDocumentModel(
            id=document.id,
            revision=document.revision,
            path_lesson_id=lesson_id,
            teaching_plan_id=document.teaching_plan_id,
            teaching_plan_revision=document.teaching_plan_revision,
            teaching_plan_hash=document.teaching_plan_hash,
            content_hash=document.content_hash,
            document_json=document.model_dump(mode="json"),
            status=document_status,
        )
        session.add_all(
            [
                UserModel(id=owner_id, email=f"{owner_id}@example.invalid"),
                concept,
                unit,
                version,
                lesson,
                build,
                run,
                stored,
            ]
        )
        await session.commit()
    return document.id, document


@pytest.fixture
async def preview_http(db_session_factory):
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


async def test_preview_requires_authentication() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/shared-documents/missing/revisions/1")
    assert response.status_code == 401


async def test_preview_returns_exact_document_and_lineage(preview_http, db_session_factory):
    client, identity = preview_http
    owner_id = "preview-owner-success"
    document_id, document = await _seed_preview(
        db_session_factory,
        suffix="success",
        owner_id=owner_id,
    )
    identity["user_id"] = owner_id

    response = await client.get(f"/api/v1/shared-documents/{document_id}/revisions/1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["document"] == document.model_dump(mode="json")
    assert body["source"] == {
        "type": "teaching_plan",
        "id": "plan-preview",
        "revision": 3,
        "hash": "b" * 64,
    }
    assert body["output"]["type"] == "shared_lesson_document"
    assert body["output"]["id"] == document_id
    assert body["output"]["revision"] == 1
    assert body["output"]["hash"] == content_hash(document.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("suffix", "owner_id", "request_owner", "document_status", "output_hash"),
    [
        ("foreign", "preview-owner-foreign", "preview-owner-other", "ready", None),
        ("draft", "preview-owner-draft", "preview-owner-draft", "draft", None),
        (
            "stale-hash",
            "preview-owner-stale",
            "preview-owner-stale",
            "ready",
            "c" * 64,
        ),
    ],
)
async def test_preview_fails_closed_for_foreign_nonready_or_stale_output(
    preview_http,
    db_session_factory,
    suffix,
    owner_id,
    request_owner,
    document_status,
    output_hash,
):
    client, identity = preview_http
    document_id, _ = await _seed_preview(
        db_session_factory,
        suffix=suffix,
        owner_id=owner_id,
        document_status=document_status,
        output_hash=output_hash,
    )
    identity["user_id"] = request_owner

    response = await client.get(f"/api/v1/shared-documents/{document_id}/revisions/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Shared document not found"}
