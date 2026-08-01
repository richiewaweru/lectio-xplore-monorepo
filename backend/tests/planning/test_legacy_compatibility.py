from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import app
from core.auth.middleware import get_current_user
from core.database.models import GenerationModel, LearningPackModel, UserModel
from core.dependencies import get_async_session
from core.entities.user import User


OWNER = User(
    id="legacy-owner",
    email="legacy-owner@example.invalid",
    name="Legacy Owner",
    created_at="2026-08-01T00:00:00+00:00",
    updated_at="2026-08-01T00:00:00+00:00",
)
OTHER = User(
    id="legacy-other",
    email="legacy-other@example.invalid",
    name="Legacy Other",
    created_at="2026-08-01T00:00:00+00:00",
    updated_at="2026-08-01T00:00:00+00:00",
)


async def test_legacy_packs_are_computed_as_one_lesson_units_without_writes(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        session.add_all(
            [
                UserModel(id=OWNER.id, email=OWNER.email, name=OWNER.name),
                UserModel(id=OTHER.id, email=OTHER.email, name=OTHER.name),
                LearningPackModel(
                    id="legacy-pack",
                    user_id=OWNER.id,
                    learning_job_type="lesson",
                    subject="Science",
                    topic="Cells",
                    pack_plan_json='{"learning_job":{"objective":"Explain cells."}}',
                    status="ready",
                    resource_count=1,
                    completed_count=1,
                ),
                LearningPackModel(
                    id="v2-pack",
                    user_id=OWNER.id,
                    learning_job_type="xplore_variants",
                    subject="Science",
                    topic="V2 internal",
                    pack_plan_json="{}",
                    status="ready",
                    resource_count=1,
                    completed_count=1,
                ),
            ]
        )
        session.add(
            GenerationModel(
                id="legacy-generation",
                user_id=OWNER.id,
                subject="Science",
                context="Cells",
                mode="v3",
                status="completed",
                requested_template_id="guided-concept-path",
                resolved_template_id="guided-concept-path",
                requested_preset_id="v3-studio",
                resolved_preset_id="v3-studio",
                pack_id="legacy-pack",
                document_json={
                    "kind": "v3_booklet_pack",
                    "generation_id": "legacy-generation",
                    "status": "completed",
                    "sections": [{"section_id": "intro", "blocks": []}],
                },
            )
        )
        session.add(
            GenerationModel(
                id="legacy-stale-generation",
                user_id=OWNER.id,
                subject="Science",
                context="Cells",
                mode="balanced",
                status="completed",
                requested_template_id="guided-concept-path",
                requested_preset_id="balanced",
                pack_id="legacy-pack",
            )
        )
        await session.commit()

    actor = {"user": OWNER}

    async def override_user() -> User:
        return actor["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/legacy-units")
            detail = await client.get("/api/v1/legacy-units/legacy-pack")
            actor["user"] = OTHER
            forbidden = await client.get("/api/v1/legacy-units/legacy-pack")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [row["legacy_pack_id"] for row in response.json()] == ["legacy-pack"]
    assert detail.status_code == 200
    assert detail.json()["lesson"] == {
        "title": "Cells",
        "pack_id": "legacy-pack",
        "generation_ids": ["legacy-generation"],
        "open_href": "/units/legacy/legacy-pack",
    }
    assert detail.json()["computed"] is True
    assert detail.json()["migration_required"] is False
    assert detail.json()["resource_count"] == 1
    assert detail.json()["completed_count"] == 1
    assert forbidden.status_code == 404

    async with db_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LearningPackModel)) == 2
        assert await session.scalar(select(func.count()).select_from(GenerationModel)) == 2
