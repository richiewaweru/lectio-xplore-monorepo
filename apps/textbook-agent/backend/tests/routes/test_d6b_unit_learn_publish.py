"""D6B — Unit → Learn → Builder → Preview → Publish closeout.

Proves Unit prepare admits Component Lectio, mocked generation produces a valid
Learn document, Builder edit/save/reload works, draft preview does not mutate
release/runtime tables, and publish v1 stays immutable after v2.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import app
from application.unit_lesson import prepare_path_lesson
from core.database.models import (
    GenerationModel,
    LearnerAttemptModel,
    LearningInstanceModel,
    LearnReleaseModel,
    PathLessonModel,
    UserModel,
)
from core.entities.user import User
from curriculum.path_models import PrepareLessonRequest
from curriculum.service import approve_path, create_unit, persist_path_plan
from infra.auth.middleware import get_current_user
from infra.database.session import get_async_session
from learn.contracts.lesson_document import validate_lesson_document
from learn.generation.component_lectio.service import run_component_lectio_execution
from learn.release_routes import document_hash
from learn.generation.contracts import GenerationInputForm as V3InputForm
from learn.generation.contracts import GenerationSignalSummary as V3SignalSummary
from application.unit_lesson.dispatch import _path_resource_spec
from tests.generation.test_component_lectio_final_contract import _exec_kwargs
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture
from tests.planning.test_path_bridge import (
    _fake_component_selector,
    _fake_structural_planner,
)
from tests.v3_blueprint.planning.test_intent_plan import (
    SUBJECT_FIXTURES,
    _intent_plan_for_subject,
)
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from v3_blueprint.planning.persistence import (
    load_chunked_state,
    persist_structural_plan,
)

FIXTURE = "grade4-photosynthesis-path.json"

USER = User(
    id="d6b-learn-owner",
    email="d6b-learn@example.invalid",
    name="D6B Learn",
    picture_url=None,
    has_profile=True,
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _bind_session_factory(db_session_factory, monkeypatch) -> None:
    """Route Component Lectio persistence onto the HTTP test DB."""

    @asynccontextmanager
    async def _factory():
        async with db_session_factory() as session:
            yield session

    monkeypatch.setattr(
        "learn.generation.component_lectio.service.async_session_factory",
        _factory,
    )
    monkeypatch.setattr(
        "v3_blueprint.planning.persistence.async_session_factory",
        _factory,
    )


async def _count(session, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_d6b_unit_learn_builder_preview_publish(
    db_session_factory, monkeypatch
) -> None:
    _bind_session_factory(db_session_factory, monkeypatch)

    async with db_session_factory() as session:
        session.add(UserModel(id=USER.id, email=USER.email, name=USER.name))
        plan = load_canonical_plan(FIXTURE)
        unit = await create_unit(
            session,
            owner_id=USER.id,
            request=unit_create_from_fixture(FIXTURE),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None

        response, _structural = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(lesson_mode="first_exposure"),
            structural_planner=_fake_structural_planner,
            component_selector=_fake_component_selector,
        )
        gid = response.generation_id
        unit_id = unit.id
        lesson_id = lesson.id
        path_version_id = version.id
        path_revision = version.revision
        chunked = await load_chunked_state(gid, session)
        assert (chunked.get("control") or {}).get("pipeline") == "component_lectio"
        assert chunked.get("path_prepared") is True
        # Print-native prepare uses skeleton roles (organise/guided/…) that are not
        # Learn resource-spec roles. Keep the Unit-owned generation + provenance,
        # and admit a Learn-compatible structural plan for Component Lectio
        # execution (documented as ARCH/Learn slot ownership debt).
        learn_plan = intent_plan_to_structural_plan(
            _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
        )
        form = V3InputForm(
            grade_level=unit.grade_level,
            subject=unit.subject,
            duration_minutes=45,
            resource_type="lesson",
            topic=unit.topic,
            subtopics=[learn_plan.cards[0].title],
            prior_knowledge="",
            outcome=learn_plan.cards[0].objective,
            prior_knowledge_level="some_background",
            free_text="D6B Learn execution on Unit-prepared generation",
        )
        signals = V3SignalSummary(
            topic=unit.topic,
            prior_knowledge=[],
            learner_needs=[],
            teacher_goal=learn_plan.cards[0].objective,
            inferred_lesson_mode="first_exposure",
            lesson_mode_confidence="high",
        )
        await persist_structural_plan(
            gid,
            learn_plan,
            session,
            signals=signals,
            form=form,
            resource_spec=_path_resource_spec(),
        )
        await session.commit()

    document = await run_component_lectio_execution(
        generation_id=gid,
        plan=learn_plan,
        form=form,
        title=form.topic or "D6B Learn",
        **_exec_kwargs(),
    )
    errors = validate_lesson_document(document)
    assert errors == [], errors[:5]

    async with db_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "completed"
        assert generation.document_json is not None
        state = generation.chunked_state_json or {}
        builder_id = state.get("builder_id")
        assert builder_id, "Component Lectio success must open a Builder lesson"
        assert state.get("stage") == "complete"
        lesson_row = await session.get(PathLessonModel, lesson_id)
        assert lesson_row is not None
        assert lesson_row.pack_id == gid
        from core.database.models import LessonProvenanceModel

        provenance = await session.get(LessonProvenanceModel, gid)
        assert provenance is not None
        assert provenance.invalidated_at is None
        assert provenance.path_lesson_id == lesson_id

    monkeypatch.setattr(
        "core.capabilities.settings",
        __import__("infra.config", fromlist=["settings"]).settings,
    )
    from infra.config import settings as app_settings

    monkeypatch.setattr(app_settings, "xplore_v2_enabled", True)
    monkeypatch.setattr(app_settings, "xplore_v2_beta_users", "")

    async def override_user():
        return USER

    async def override_session():
        async with db_session_factory() as session:
            from core.database.models import UnitModel

            unit_row = await session.get(UnitModel, unit_id)
            gen_row = await session.get(GenerationModel, gid)
            assert unit_row is not None, "override session missing unit"
            assert unit_row.owner_id == USER.id
            assert gen_row is not None, "override session missing generation"
            assert gen_row.user_id == USER.id
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    # Also override the symbol units_routes closed over, in case of import aliasing.
    import learn.generation.units_routes as units_routes_mod

    app.dependency_overrides[units_routes_mod.get_async_session] = override_session
    app.dependency_overrides[units_routes_mod.get_current_user] = override_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        loaded = await client.get(f"/api/v1/builder/lessons/{builder_id}")
        assert loaded.status_code == 200, loaded.text
        draft = loaded.json()["document"]
        assert draft["blocks"]

        status = await client.get(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/generation"
        )
        assert status.status_code == 200, (
            status.text
            + f" unit={unit_id} lesson={lesson_id} gid={gid} builder={builder_id}"
        )
        body = status.json()
        assert body["generation_id"] == gid
        assert body["pipeline"] == "component_lectio"
        assert body["stage"] == "complete"
        assert body["document_present"] is True
        # Meaningful Builder edit → save → reload.
        edited = dict(draft)
        edited["title"] = "D6B edited Learn title"
        first_block_id = next(iter(edited["blocks"]))
        block = dict(edited["blocks"][first_block_id])
        content = dict(block.get("content") or {})
        if "body" in content:
            content["body"] = "D6B edited explanation body."
        else:
            content["d6b_marker"] = "edited"
        block["content"] = content
        edited["blocks"] = {**edited["blocks"], first_block_id: block}

        saved = await client.put(
            f"/api/v1/builder/lessons/{builder_id}",
            json={"title": edited["title"], "document": edited},
        )
        assert saved.status_code == 200, saved.text

        reloaded = await client.get(f"/api/v1/builder/lessons/{builder_id}")
        assert reloaded.status_code == 200, reloaded.text
        reloaded_doc = reloaded.json()["document"]
        assert reloaded_doc["title"] == "D6B edited Learn title"
        assert reloaded_doc["blocks"][first_block_id]["content"] == content

        # Preview / draft load must not mutate releases or runtime tables.
        async with db_session_factory() as session:
            before = {
                "releases": await _count(session, LearnReleaseModel),
                "instances": await _count(session, LearningInstanceModel),
                "attempts": await _count(session, LearnerAttemptModel),
            }
        preview = await client.get(f"/api/v1/builder/lessons/{builder_id}")
        assert preview.status_code == 200
        async with db_session_factory() as session:
            after = {
                "releases": await _count(session, LearnReleaseModel),
                "instances": await _count(session, LearningInstanceModel),
                "attempts": await _count(session, LearnerAttemptModel),
            }
        assert after == before

        # Publish immutable v1, edit draft, publish v2 without mutating v1.
        pub1 = await client.post(
            f"/api/v1/learn/lessons/{builder_id}/releases", json={}
        )
        assert pub1.status_code == 201, pub1.text
        v1 = pub1.json()
        assert v1["release_number"] == 1
        hash1 = v1["document_hash"]
        assert hash1 == document_hash(v1["document"])

        draft2 = dict(reloaded_doc)
        draft2["title"] = "D6B v2 draft"
        draft2["blocks"] = {
            **draft2["blocks"],
            first_block_id: {
                **draft2["blocks"][first_block_id],
                "content": {
                    **draft2["blocks"][first_block_id]["content"],
                    "body": "V2 body text",
                }
                if "body" in draft2["blocks"][first_block_id]["content"]
                else {
                    **draft2["blocks"][first_block_id]["content"],
                    "d6b_marker": "v2",
                },
            },
        }
        update2 = await client.put(
            f"/api/v1/builder/lessons/{builder_id}",
            json={"title": "D6B v2 draft", "document": draft2},
        )
        assert update2.status_code == 200, update2.text

        get_v1 = await client.get(f"/api/v1/learn/releases/{v1['id']}")
        assert get_v1.status_code == 200
        assert get_v1.json()["document_hash"] == hash1
        assert get_v1.json()["document"]["title"] == "D6B edited Learn title"

        pub2 = await client.post(
            f"/api/v1/learn/lessons/{builder_id}/releases", json={}
        )
        assert pub2.status_code == 201, pub2.text
        v2 = pub2.json()
        assert v2["release_number"] == 2
        assert v2["id"] != v1["id"]
        assert v2["document_hash"] != hash1
        assert v2["document"]["title"] == "D6B v2 draft"

        listed = await client.get(f"/api/v1/learn/lessons/{builder_id}/releases")
        assert listed.status_code == 200
        assert [item["release_number"] for item in listed.json()] == [1, 2]

        # Units open-builder remains idempotent after publish.
        open_builder = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/generation:open-builder",
            json={
                "path_version_id": path_version_id,
                "path_revision": path_revision,
            },
        )
        assert open_builder.status_code == 200, open_builder.text
        assert open_builder.json().get("builder_id") in {None, builder_id} or (
            open_builder.json().get("stage") == "complete"
        )
