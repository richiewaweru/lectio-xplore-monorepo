from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from core.auth.middleware import get_current_user
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from core.database.models import (
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    UserModel,
)
from core.database.session import async_session_factory
from core.entities.user import User
from print.http.v3_studio.dtos import V3InputForm, V3SignalSummary
from curriculum.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
)
from curriculum.planning.persistence import (
    load_chunked_state,
    persist_chunked_state,
    persist_structural_plan,
)

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
async def test_chunked_plan_start_route_is_deleted_and_creates_no_rows() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    async with async_session_factory() as session:
        before_generation_ids = {
            row.id for row in (await session.execute(select(GenerationModel))).scalars().all()
        }
        before_pack_ids = {
            row.id for row in (await session.execute(select(LearningPackModel))).scalars().all()
        }

    async with _client() as client:
        resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code in {404, 405}

    async with async_session_factory() as session:
        after_generation_ids = {
            row.id for row in (await session.execute(select(GenerationModel))).scalars().all()
        }
        after_pack_ids = {
            row.id for row in (await session.execute(select(LearningPackModel))).scalars().all()
        }
    assert after_generation_ids == before_generation_ids
    assert after_pack_ids == before_pack_ids


@pytest.mark.asyncio
async def test_generation_events_404_before_execution_queue_registration_for_chunked_flow() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())

    from print.http.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
    )

    async with _client() as client:
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/events")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chunked_approve_rejects_historical_v1_before_scheduling() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from print.http.v3_studio.router import _ensure_chunked_generation_row

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

    with patch("print.http.v3_studio.router.admit_preparation_run", new=AsyncMock(return_value=None)) as run_stage2:
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

    from print.http.v3_studio.router import _ensure_chunked_generation_row

    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER_A.id,
        subject="Math",
        context="Equivalent fractions",
        planning_spec_json=sample_plan.model_dump_json(),
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

    with patch("print.http.v3_studio.router.admit_preparation_run", new=AsyncMock(return_value=None)) as run_stage2:
        async with _client() as client:
            resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")

    # Approve is a thin alias of the preparation admission (Option D, 3A): it
    # admits the Run and returns; no in-process task runs stage 2.
    assert resp.status_code == 200
    run_stage2.assert_awaited_once()
    assert run_stage2.await_args.kwargs["generation_id"] == generation_id
    assert run_stage2.await_args.kwargs["owner_user_id"] == TEST_USER_A.id


@pytest.mark.asyncio
async def test_chunked_approve_is_user_scoped() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    await _ensure_user(TEST_USER_B)
    sample_plan = _sample_structural_plan()
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from print.http.v3_studio.router import _ensure_chunked_generation_row

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

    app.dependency_overrides[get_current_user] = _override_user_b
    async with _client() as client:
        resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chunked_status_reports_next_action_by_stage() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())

    from print.http.v3_studio.router import _ensure_chunked_generation_row

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

    from print.http.v3_studio.router import _ensure_chunked_generation_row

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

    from print.http.v3_studio.router import _ensure_chunked_generation_row

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
async def test_chunked_approve_resumes_stage2_error() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()

    from print.http.v3_studio.router import _ensure_chunked_generation_row

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
    with patch("print.http.v3_studio.router.admit_preparation_run", new=pipeline):
        async with _client() as client:
            response = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
        await asyncio.sleep(0)

    assert response.status_code == 409
    assert "contract v2" in response.json()["detail"]
    pipeline.assert_not_awaited()


