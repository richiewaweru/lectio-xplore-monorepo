from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import MagicMock
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from core.auth.middleware import get_current_user
from core.database.models import (
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    UserModel,
)
from core.database.session import async_session_factory
from core.entities.user import User
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from generation.v3_studio.session_store import v3_studio_store
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentBrief,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    SectionBrief,
    SectionPlan,
    StructuralPlan,
)
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state, persist_structural_plan

TEST_USER_A = User(
    id="v3-chunked-user-a",
    email="v3chunkeda@example.com",
    name="V3 Chunked A",
    picture_url=None,
    has_profile=True,
    created_at="2026-03-25T00:00:00+00:00",
    updated_at="2026-03-25T00:00:00+00:00",
)

TEST_USER_B = User(
    id="v3-chunked-user-b",
    email="v3chunkedb@example.com",
    name="V3 Chunked B",
    picture_url=None,
    has_profile=True,
    created_at="2026-03-25T00:00:00+00:00",
    updated_at="2026-03-25T00:00:00+00:00",
)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _override_user_a() -> User:
    return TEST_USER_A


async def _override_user_b() -> User:
    return TEST_USER_B


async def _ensure_user(user: User) -> None:
    async with async_session_factory() as session:
        model = await session.get(UserModel, user.id)
        if model is None:
            session.add(
                UserModel(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    picture_url=user.picture_url,
                )
            )
            await session.commit()


def _chunked_start_payload() -> dict:
    return {
        "signals": {
            "topic": "Fractions",
            "subtopic": "Equivalent fractions",
            "prior_knowledge": ["equal sharing"],
            "learner_needs": [],
            "teacher_goal": "Build confidence",
            "inferred_lesson_mode": "first_exposure",
            "lesson_mode_confidence": "high",
        },
        "form": {
            "grade_level": "Grade 6",
            "subject": "Math",
            "duration_minutes": 45,
            "resource_type": "lesson",
            "topic": "Equivalent fractions",
            "subtopics": ["pizza slices"],
            "prior_knowledge": "equal sharing",
            "outcome": "Students can identify equivalent fractions.",
            "struggle": "Some learners still mix up numerator and denominator.",
            "learner_level": "on_grade",
            "reading_level": "on_grade",
            "language_support": "none",
            "prior_knowledge_level": "some_background",
            "free_text": "",
        },
    }


def _seed_context_models() -> tuple[V3SignalSummary, V3InputForm]:
    payload = _chunked_start_payload()
    return (
        V3SignalSummary.model_validate(payload["signals"]),
        V3InputForm.model_validate(payload["form"]),
    )


def _sample_structural_plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end students can identify equivalent fractions.",
            structure_rationale="Concrete-first structure for novice learners.",
        ),
        anchor=AnchorSpec(
            example="splitting a pizza into 8 equal slices",
            reuse_scope="intro then explain then practice",
        ),
        prior_knowledge=["equal sharing"],
        sections=[
            SectionPlan(
                id="intro",
                title="Intro",
                role="intro",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")],
            )
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="intro",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )


def _two_section_structural_plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end students can compare equivalent fractions.",
            structure_rationale="Move from hook into modeled reasoning.",
        ),
        anchor=AnchorSpec(
            example="splitting fraction strips",
            reuse_scope="intro then model then practice",
        ),
        prior_knowledge=["equal sharing"],
        sections=[
            SectionPlan(
                id="orient",
                title="Orient",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="Open the lesson")],
            ),
            SectionPlan(
                id="practice",
                title="Practice",
                role="practice",
                visual_required=False,
                transition_note="Try the idea independently.",
                components=[ComponentSlot(slug="practice-stack", purpose="Independent practice")],
            ),
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="orient",
                temperature="warm",
                diagram_required=False,
            ),
            QPlanItem(
                question_id="q2",
                section_id="practice",
                temperature="cold",
                diagram_required=False,
            ),
        ],
        answer_key_style="brief_explanations",
    )


def _parse_sse_event_name(chunk: str) -> str:
    for line in chunk.splitlines():
        if line.startswith("event:"):
            return line.partition(":")[2].strip()
    return ""


def _parse_sse_payload(chunk: str) -> dict:
    for line in chunk.splitlines():
        if line.startswith("data:"):
            return __import__("json").loads(line.partition(":")[2].strip())
    return {}


@pytest.fixture(autouse=True)
def _reset_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chunked_plan_start_is_quarantined_without_creating_rows() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    async with _client() as client:
        resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code == 410
    assert "approved path" in resp.json()["detail"]

    async with async_session_factory() as session:
        assert (await session.execute(select(GenerationModel))).scalars().all() == []
        assert (await session.execute(select(LearningPackModel))).scalars().all() == []


@pytest.mark.asyncio
async def test_chunked_events_route_streams_planning_events_and_keeps_generation_queue() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream, _ensure_generation_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    chunked_queue = await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await _ensure_generation_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"bp-{generation_id}",
    )
    await chunked_queue.put('event: stage2_section_start\ndata: {"section_id":"intro"}\n\n')
    await chunked_queue.put('event: generation_warning\ndata: {"message":"warning"}\n\n')
    await chunked_queue.put(None)

    async with _client() as client:
        async with client.stream("GET", f"/api/v1/v3/chunked/{generation_id}/events") as resp:
            assert resp.status_code == 200
            payload = await resp.aread()

    assert b"stage2_section_start" in payload
    assert b"generation_warning" in payload
    assert await v3_studio_store.get_chunked_queue(generation_id) is None
    assert await v3_studio_store.get_generation_queue(generation_id) is not None


@pytest.mark.asyncio
async def test_generation_events_404_before_execution_queue_registration_for_chunked_flow() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/events")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_quarantined_chunked_plan_start_does_not_run_stage1() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    async with _client() as client:
        resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_quarantined_chunked_plan_start_does_not_capture_stage1_errors() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    async with _client() as client:
        resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_chunked_approve_rejects_historical_v1_before_scheduling() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )

    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=AsyncMock(return_value=None)) as run_stage2:
        async with _client() as client:
            resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")

    assert resp.status_code == 409
    assert "contract v2" in resp.json()["detail"]
    run_stage2.assert_not_awaited()
    state = await load_chunked_state(generation_id)
    assert state["stage"] == "plan_ready"


@pytest.mark.asyncio
async def test_chunked_approve_accepts_native_path_generation() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    sample_plan = _sample_structural_plan().model_copy(
        update={"document_contract_version": 2}
    )
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
        planning_spec_json=sample_plan.model_dump_json(),
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )
    await persist_chunked_state(
        generation_id,
        {"stage": "awaiting_review", "native_whole_lesson": True},
    )
    async with async_session_factory() as session:
        session.add(
            LessonProvenanceModel(
                pack_id=generation_id,
                path_version_id="path-version-native",
                path_lesson_id="path-lesson-native",
            )
        )
        await session.commit()

    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=AsyncMock(return_value=None)) as run_stage2:
        async with _client() as client:
            resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["stage"] == "stage2_running"
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
    assert generation is not None
    assert generation.status == "running"
    run_stage2.assert_awaited_once()


@pytest.mark.asyncio
async def test_variant_children_inherit_native_identity_before_scheduling(monkeypatch) -> None:
    from generation.v3_studio import router
    from generation.v3_studio.dtos import V3InputForm
    from v3_blueprint.planning.models import core_variant_spec

    _signals, form = _seed_context_models()
    plan = _sample_structural_plan().model_copy(
        update={"document_contract_version": 2}
    )
    state = {
        "pack_id": "pack-native-variants",
        "native_whole_lesson": True,
        "variants": [core_variant_spec().model_dump(mode="json")],
        "structural_plan": plan.model_dump(mode="json"),
        "context": {
            "native_whole_lesson": True,
            "form": V3InputForm.model_validate(form).model_dump(mode="json"),
        },
    }
    ensured: list[dict] = []
    persisted: list[dict] = []

    async def fake_ensure(**kwargs):
        ensured.append(kwargs)

    async def fake_persist(_generation_id, patch):
        persisted.append(patch)

    async def fake_stream(**_kwargs):
        return None

    monkeypatch.setattr(router, "_ensure_chunked_generation_row", fake_ensure)
    monkeypatch.setattr(router, "persist_chunked_state", fake_persist)
    monkeypatch.setattr(router, "_ensure_chunked_stream", fake_stream)

    ids = await router._prepare_variant_generations(
        coordinator_id="coordinator-native",
        user_id="user-native",
        state=state,
    )

    assert ids
    assert ensured[0]["planning_spec_json"]
    assert json.loads(ensured[0]["planning_spec_json"])["document_contract_version"] == 2
    assert persisted[0]["native_whole_lesson"] is True


@pytest.mark.asyncio
async def test_historical_v1_regenerate_is_read_only_before_mutation() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()
    from generation.v3_studio import router
    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await persist_structural_plan(
        generation_id,
        _sample_structural_plan(),
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )
    persist = AsyncMock()
    stream = AsyncMock()
    stage1 = AsyncMock()
    with (
        patch.object(router, "persist_chunked_state", new=persist),
        patch.object(router, "_ensure_chunked_stream", new=stream),
        patch.object(router, "run_stage1_with_retry", new=stage1),
    ):
        async with _client() as client:
            response = await client.post(
                f"/api/v1/v3/chunked/{generation_id}/regenerate",
                json={"note": "try again"},
            )

    assert response.status_code == 409
    assert "read-only" in response.json()["detail"]
    persist.assert_not_awaited()
    stream.assert_not_awaited()
    stage1.assert_not_awaited()


@pytest.mark.asyncio
async def test_historical_v1_retry_section_is_read_only_before_mutation() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()
    from generation.v3_studio import router
    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await persist_structural_plan(
        generation_id,
        _sample_structural_plan(),
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )
    await persist_chunked_state(
        generation_id,
        {"stage": "assembly_blocked", "failed_sections": ["intro"]},
    )
    persist = AsyncMock()
    stream = AsyncMock()
    claim = AsyncMock(return_value=True)
    with (
        patch.object(router, "persist_chunked_state", new=persist),
        patch.object(router, "_ensure_chunked_stream", new=stream),
        patch.object(router.V3GenerationWriter, "claim_resume_attempt", new=claim),
    ):
        async with _client() as client:
            response = await client.post(
                f"/api/v1/v3/chunked/{generation_id}/retry-section",
                json={"section_id": "intro"},
            )

    assert response.status_code == 409
    assert "read-only" in response.json()["detail"]
    persist.assert_not_awaited()
    stream.assert_not_awaited()
    claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_chunked_approve_is_user_scoped() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chunked_retry_section_rejects_non_failed_section() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )

    async with _client() as client:
        resp = await client.post(
            f"/api/v1/v3/chunked/{generation_id}/retry-section",
            json={"section_id": "intro"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_chunked_regenerate_is_read_only_for_historical_v1() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    from generation.v3_studio import router
    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    persist = AsyncMock()
    stream = AsyncMock()
    stage1 = AsyncMock()
    with (
        patch.object(router, "persist_chunked_state", new=persist),
        patch.object(router, "_ensure_chunked_stream", new=stream),
        patch.object(router, "run_stage1_with_retry", new=stage1),
    ):
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/chunked/{generation_id}/regenerate",
                json={"note": "Keep section two shorter."},
            )
    assert resp.status_code == 409
    assert "read-only" in resp.json()["detail"]
    persist.assert_not_awaited()
    stream.assert_not_awaited()
    stage1.assert_not_awaited()


@pytest.mark.asyncio
async def test_chunked_status_reports_next_action_by_stage() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())

    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await persist_chunked_state(generation_id, {"stage": "assembly_blocked", "failed_sections": ["model"]})

    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.document_json = {
            "progress": {"stage": "writing", "updated_at": "2026-07-17T10:00:00+00:00"}
        }
        await session.commit()

    async with _client() as client:
        blocked = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["next_action"] == "retry_failed_sections"
    assert blocked_payload["doc_version"] == "2026-07-17T10:00:00+00:00"
    assert "structural_plan" not in blocked_payload
    assert "section_briefs" not in blocked_payload

    await persist_chunked_state(
        generation_id,
        {"stage": "stage2_error", "error": "executor failed", "error_type": "RuntimeError"},
    )
    async with _client() as client:
        stage2_error = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
    assert stage2_error.status_code == 200
    assert stage2_error.json()["stage"] == "stage2_error"
    assert stage2_error.json()["next_action"] == "resume_stage2"
    assert stage2_error.json()["error_type"] == "RuntimeError"

    await persist_chunked_state(
        generation_id,
        {"stage": "blueprint_ready", "execution_started": True, "blueprint_id": "bp-123"},
    )
    async with _client() as client:
        ready = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
    assert ready.status_code == 200
    assert ready.json()["next_action"] == "generation_running"


@pytest.mark.asyncio
async def test_chunked_status_derives_version_for_legacy_document_without_progress() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())

    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Legacy snapshot",
    )
    await persist_chunked_state(
        generation_id,
        {"stage": "stage2_running", "execution_started": True},
    )
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.document_json = {"kind": "v3_booklet_pack", "sections": [{"section_id": "intro"}]}
        await session.commit()

    async with _client() as client:
        response = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")

    assert response.status_code == 200
    assert response.json()["doc_version"].startswith("sha256:")


@pytest.mark.asyncio
async def test_chunked_plan_endpoint_returns_immutable_plan_metadata() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await persist_structural_plan(
        generation_id,
        _sample_structural_plan(),
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )

    async with _client() as client:
        response = await client.get(f"/api/v1/v3/chunked/{generation_id}/plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generation_id"] == generation_id
    assert payload["structural_plan"]["anchor"]["example"] == "splitting a pizza into 8 equal slices"
    assert payload["display_title"] == form.topic
    assert "section_briefs" not in payload

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        forbidden = await client.get(f"/api/v1/v3/chunked/{generation_id}/plan")
    assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_native_pipeline_timeout_persists_recoverable_error_state() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()
    sample_plan = _sample_structural_plan().model_copy(
        update={"document_contract_version": 2}
    )

    from generation.v3_studio.router import (
        _ensure_chunked_generation_row,
        _run_chunked_stage2_pipeline,
    )

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "stage2_running",
            "native_whole_lesson": True,
            "skip_item_generation": True,
        },
    )

    with (
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=AsyncMock(side_effect=TimeoutError("teaching provider timed out")),
        ),
        patch("generation.v3_studio.router._chunked_emit_event", new=AsyncMock()),
    ):
        await _run_chunked_stage2_pipeline(generation_id=generation_id, user_id=TEST_USER_A.id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        state = dict(generation.chunked_state_json or {})
        assert state["stage"] == "failed_recoverable"
        page = dict(state.get("page_document_v2") or {})
        last_error = dict((page.get("execution") or {}).get("last_error") or {})
        assert last_error["stage"] == "planning_teaching"
        assert "teaching provider timed out" in str(last_error.get("message"))
        assert generation.error == last_error.get("message")
        assert generation.error_type == last_error.get("type")
        assert generation.error_code == last_error.get("code")


@pytest.mark.asyncio
async def test_chunked_approve_resumes_stage2_error() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await persist_structural_plan(
        generation_id,
        _sample_structural_plan(),
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )
    await persist_chunked_state(generation_id, {"stage": "stage2_error", "error_type": "RuntimeError"})

    pipeline = AsyncMock(return_value=None)
    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=pipeline):
        async with _client() as client:
            response = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
        await asyncio.sleep(0)

    assert response.status_code == 409
    assert "contract v2" in response.json()["detail"]
    pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_chunked_retry_section_is_read_only_for_historical_v1() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "assembly_blocked",
            "failed_sections": ["intro"],
            "section_briefs": {"intro": None},
            "execution_started": False,
        },
    )

    from generation.v3_studio import router
    persist = AsyncMock()
    stream = AsyncMock()
    claim = AsyncMock(return_value=True)
    with (
        patch.object(router, "persist_chunked_state", new=persist),
        patch.object(router, "_ensure_chunked_stream", new=stream),
        patch.object(router.V3GenerationWriter, "claim_resume_attempt", new=claim),
    ):
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/chunked/{generation_id}/retry-section",
                json={"section_id": "intro"},
            )

    assert resp.status_code == 409
    assert "read-only" in resp.json()["detail"]
    persist.assert_not_awaited()
    stream.assert_not_awaited()
    claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_8eca999f_starts_with_null_document() -> None:
    generation_id = "8eca999f-d638-47cb-a613-5a923c575d53"
    queue = asyncio.Queue()
    blueprint = MagicMock()
    blueprint.metadata.title = "Equivalent Fractions"
    blueprint.metadata.subject = "Math"
    blueprint.sections = [MagicMock(components=[], visual_required=False)]
    blueprint.question_plan = []
    generation_writer = MagicMock()
    generation_writer.get_document_json = AsyncMock(return_value=None)
    generation_writer.upsert_started = AsyncMock()
    generation_writer.write_planning_artifact = AsyncMock()
    trace_writer = MagicMock()
    trace_writer.start_run = AsyncMock()
    trace_writer.record_blueprint_snapshot = AsyncMock()
    pump_result = object()
    pump = MagicMock(return_value=pump_result)

    with (
        patch("generation.v3_studio.router.V3GenerationWriter", return_value=generation_writer),
        patch("generation.v3_studio.router.get_v3_trace_repository", return_value=MagicMock()),
        patch("generation.v3_studio.router.V3TraceWriter", return_value=trace_writer),
        patch(
            "generation.v3_studio.router.telemetry_monitor.initialise_v3_recorder",
            new=AsyncMock(),
        ),
        patch("generation.v3_studio.router.build_planning_artifact", return_value={}),
        patch("generation.v3_studio.router._chunked_emit_event", new=AsyncMock()),
        patch("generation.v3_studio.router._pump_sse_to_queue", new=pump),
        patch("generation.v3_studio.router._spawn_background_task") as spawn,
    ):
        from generation.v3_studio.router import _start_generation_from_chunked_blueprint

        await _start_generation_from_chunked_blueprint(
            generation_id=generation_id,
            blueprint_id=f"bp-{generation_id}",
            blueprint=blueprint,
            form=None,
            display_title=None,
            user_id=TEST_USER_A.id,
            queue=queue,
        )

    assert pump.call_args.kwargs["preserved_ready_sections"] == []
    spawn.assert_called_once_with(pump_result)


@pytest.mark.asyncio
async def test_attempt_chunked_assembly_logs_execution_handoff_success() -> None:
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    _signals, form = _seed_context_models()
    queue = asyncio.Queue()
    brief = SectionBrief(
        section_id="intro",
        components=[
            ComponentBrief(
                component_id="hook-hero",
                content_intent="Use the recovered anchor.",
            )
        ],
        question_briefs=[],
        visual_strategy=None,
    )
    blueprint = MagicMock(name="blueprint")

    with (
        patch("generation.v3_studio.router.assemble_blueprint", return_value=blueprint),
        patch("generation.v3_studio.router._validate_blueprint"),
        patch("generation.v3_studio.router.v3_studio_store.put_blueprint", new=AsyncMock()),
        patch("generation.v3_studio.router._ensure_generation_stream", new=AsyncMock(return_value=queue)),
        patch(
            "generation.v3_studio.router._start_generation_from_chunked_blueprint",
            new=AsyncMock(),
        ),
        patch("generation.v3_studio.router.persist_chunked_state", new=AsyncMock()),
        patch("builtins.print") as mock_print,
    ):
        from generation.v3_studio.router import _attempt_chunked_assembly

        await _attempt_chunked_assembly(
            generation_id=generation_id,
            user_id=TEST_USER_A.id,
            plan=sample_plan,
            briefs=[brief],
            form=form,
            resource_spec={"resource_type": "lesson"},
        )

    printed = [call.args[0] for call in mock_print.call_args_list]
    queue_registering = next(line for line in printed if "[EXECUTION QUEUE REGISTERING]" in line)
    queue_registered = next(line for line in printed if "[EXECUTION QUEUE REGISTERED]" in line)
    execution_starting = next(line for line in printed if "[EXECUTION STARTING]" in line)
    execution_started = next(line for line in printed if "[EXECUTION STARTED]" in line)

    assert f"generation_id={generation_id}" in queue_registering
    assert f"generation_id={generation_id}" in queue_registered
    assert "queue_exists=True" in queue_registered
    assert f"generation_id={generation_id}" in execution_starting
    assert "blueprint_id=" in execution_starting
    assert f"generation_id={generation_id}" in execution_started

    queue_registering_idx = printed.index(queue_registering)
    queue_registered_idx = printed.index(queue_registered)
    execution_starting_idx = printed.index(execution_starting)
    execution_started_idx = printed.index(execution_started)
    assert queue_registering_idx < queue_registered_idx < execution_starting_idx < execution_started_idx


@pytest.mark.asyncio
async def test_attempt_chunked_assembly_proceeds_with_partial_failed_sections() -> None:
    sample_plan = _two_section_structural_plan()
    generation_id = str(uuid.uuid4())
    _signals, form = _seed_context_models()
    queue = asyncio.Queue()
    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    orient_brief = SectionBrief(
        section_id="orient",
        components=[
            ComponentBrief(
                component_id="hook-hero",
                content_intent="Use a fraction strip hook.",
            )
        ],
        visual_strategy=None,
    )
    practice_failed = SectionBrief(
        section_id="practice",
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    practice_failed._failed = True
    practice_failed._errors = ["retry exhausted"]

    with (
        patch("generation.v3_studio.router._validate_blueprint"),
        patch("generation.v3_studio.router.v3_studio_store.put_blueprint", new=AsyncMock()),
        patch("generation.v3_studio.router._ensure_generation_stream", new=AsyncMock(return_value=queue)),
        patch("generation.v3_studio.router._start_generation_from_chunked_blueprint", new=AsyncMock()),
    ):
        from generation.v3_studio.router import _attempt_chunked_assembly

        await _attempt_chunked_assembly(
            generation_id=generation_id,
            user_id=TEST_USER_A.id,
            plan=sample_plan,
            briefs=[orient_brief, practice_failed],
            form=form,
            resource_spec={"resource_type": "lesson"},
        )

    state = await load_chunked_state(generation_id)
    assert state["stage"] == "blueprint_ready"
    assert state["execution_started"] is True
    assert state["failed_sections"] == ["practice"]


@pytest.mark.asyncio
async def test_attempt_chunked_assembly_blocks_only_when_no_sections_renderable() -> None:
    sample_plan = _two_section_structural_plan()
    generation_id = str(uuid.uuid4())
    _signals, form = _seed_context_models()
    from generation.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    orient_failed = SectionBrief(
        section_id="orient",
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    practice_failed = SectionBrief(
        section_id="practice",
        components=[],
        question_briefs=[],
        visual_strategy=None,
    )
    orient_failed._failed = True
    practice_failed._failed = True

    with (
        patch("generation.v3_studio.router._chunked_emit_event", new=AsyncMock()),
        patch("generation.v3_studio.router._start_generation_from_chunked_blueprint", new=AsyncMock()),
    ):
        from generation.v3_studio.router import _attempt_chunked_assembly

        await _attempt_chunked_assembly(
            generation_id=generation_id,
            user_id=TEST_USER_A.id,
            plan=sample_plan,
            briefs=[orient_failed, practice_failed],
            form=form,
            resource_spec={"resource_type": "lesson"},
        )

    state = await load_chunked_state(generation_id)
    assert state["stage"] == "assembly_blocked"
    assert state["execution_started"] is False
    assert state["failed_sections"] == ["orient", "practice"]


@pytest.mark.asyncio
async def test_attempt_chunked_assembly_logs_execution_start_failure_and_reraises() -> None:
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    _signals, form = _seed_context_models()
    queue = asyncio.Queue()
    brief = SectionBrief(
        section_id="intro",
        components=[
            ComponentBrief(
                component_id="hook-hero",
                content_intent="Use the recovered anchor.",
            )
        ],
        question_briefs=[],
        visual_strategy=None,
    )
    blueprint = MagicMock(name="blueprint")

    with (
        patch("generation.v3_studio.router.assemble_blueprint", return_value=blueprint),
        patch("generation.v3_studio.router._validate_blueprint"),
        patch("generation.v3_studio.router.v3_studio_store.put_blueprint", new=AsyncMock()),
        patch("generation.v3_studio.router._ensure_generation_stream", new=AsyncMock(return_value=queue)),
        patch(
            "generation.v3_studio.router._start_generation_from_chunked_blueprint",
            new=AsyncMock(side_effect=RuntimeError("executor boot failed")),
        ),
        patch("generation.v3_studio.router.persist_chunked_state", new=AsyncMock()),
        patch("builtins.print") as mock_print,
    ):
        from generation.v3_studio.router import _attempt_chunked_assembly

        with pytest.raises(RuntimeError, match="executor boot failed"):
            await _attempt_chunked_assembly(
                generation_id=generation_id,
                user_id=TEST_USER_A.id,
                plan=sample_plan,
                briefs=[brief],
                form=form,
                resource_spec={"resource_type": "lesson"},
            )

    printed = [call.args[0] for call in mock_print.call_args_list]
    failure_log = next(line for line in printed if "[EXECUTION START FAILED]" in line)
    assert f"generation_id={generation_id}" in failure_log
    assert "type=RuntimeError" in failure_log
    assert "message=executor boot failed" in failure_log
    assert "Traceback" in failure_log


@pytest.mark.asyncio
async def test_chunked_approve_emits_stage2_progress_events() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from generation.v3_studio.router import _chunked_emit_event, _ensure_chunked_generation_row, _ensure_chunked_stream

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )
    await _ensure_chunked_stream(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        blueprint_id=f"chunked-plan-{generation_id}",
    )
    await persist_structural_plan(
        generation_id,
        sample_plan,
        signals=signals,
        form=form,
        resource_spec={"resource_type": "lesson", "depth": "standard", "spec": {}, "rendered": "x"},
    )

    async def fake_stage2_pipeline(*, generation_id: str, user_id: str):  # noqa: ANN001
        _ = user_id
        await _chunked_emit_event(generation_id, "stage2_section_start", {"generation_id": generation_id, "section_id": "intro"})
        await _chunked_emit_event(generation_id, "stage2_section_retry", {"generation_id": generation_id, "section_id": "intro", "attempt": 2})
        await _chunked_emit_event(
            generation_id,
            "stage2_section_done",
            {
                "generation_id": generation_id,
                "section_id": "intro",
                "brief": {
                    "components": [
                        {"component_id": "hook-hero", "content_intent": "Set up the anchor visually."}
                    ],
                    "question_prompts": ["Which two fractions show the same amount?"],
                    "visual_subject": "A fraction strip comparison",
                },
            },
        )
        await _chunked_emit_event(generation_id, "stage2_complete", {"generation_id": generation_id, "failed_sections": ["intro"]})
        await persist_chunked_state(generation_id, {"stage": "assembly_blocked", "failed_sections": ["intro"]})

    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=AsyncMock(side_effect=fake_stage2_pipeline)) as stage2:
        async with _client() as client:
            approve = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
            assert approve.status_code == 409
    stage2.assert_not_awaited()
