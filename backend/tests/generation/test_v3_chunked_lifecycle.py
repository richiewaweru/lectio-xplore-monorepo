from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
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
    QuestionBrief,
    SectionBrief,
    SectionPlan,
    Stage1PlanFailure,
    StructuralPlan,
    VoiceSpec,
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
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
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
        voice=VoiceSpec(register_name="simple", tone="encouraging"),
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
async def test_chunked_plan_start_returns_plan_ready_state() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    sample_plan = _sample_structural_plan()

    async def fake_stage1(*, signals, form, resource_spec, generation_id, **kwargs):  # noqa: ANN001
        emit_event = kwargs.get("emit_event")
        await persist_structural_plan(
            generation_id,
            sample_plan,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
        )
        if emit_event is not None:
            await emit_event(
                "plan_ready",
                {"generation_id": generation_id, "plan": sample_plan.model_dump(mode="json")},
            )
        return sample_plan

    with patch("generation.v3_studio.router.run_stage1_with_retry", new=AsyncMock(side_effect=fake_stage1)):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stage"] == "plan_ready"
    assert payload["generation_id"]
    assert payload["structural_plan"]["anchor"]["example"] == "splitting a pizza into 8 equal slices"
    queue = await v3_studio_store.get_chunked_queue(payload["generation_id"])
    assert queue is not None
    chunk = await asyncio.wait_for(queue.get(), timeout=3)
    assert isinstance(chunk, str)
    assert _parse_sse_event_name(chunk) == "plan_ready"


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
async def test_chunked_plan_start_surfaces_stage1_failure() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)

    with patch(
        "generation.v3_studio.router.run_stage1_with_retry",
        new=AsyncMock(side_effect=Stage1PlanFailure(errors=["unknown slug"])),
    ):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code == 422
    body = resp.json()
    assert "could not generate a valid lesson plan" in body["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_chunked_plan_start_surfaces_unexpected_stage1_exception_detail() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    captured_generation_id: str | None = None

    async def fake_stage1(*, generation_id, **kwargs):  # noqa: ANN001
        nonlocal captured_generation_id
        captured_generation_id = generation_id
        raise RuntimeError("stage1 exploded for diagnostics")

    with patch(
        "generation.v3_studio.router.run_stage1_with_retry",
        new=AsyncMock(side_effect=fake_stage1),
    ):
        async with _client() as client:
            resp = await client.post("/api/v1/v3/chunked/plan/start", json=_chunked_start_payload())

    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "[RuntimeError] stage1 exploded for diagnostics"
    assert captured_generation_id is not None
    state = await load_chunked_state(captured_generation_id)
    assert state["stage"] == "stage1_failed"
    assert state["errors"] == ["RuntimeError: stage1 exploded for diagnostics"]


@pytest.mark.asyncio
async def test_chunked_approve_marks_stage2_running() -> None:
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

    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=AsyncMock(return_value=None)):
        async with _client() as client:
            resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["stage"] == "stage2_running"


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
async def test_chunked_regenerate_appends_note_to_persisted_context() -> None:
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

    async def fake_stage1(*, signals, form, resource_spec, generation_id, **kwargs):  # noqa: ANN001
        _ = kwargs
        assert "Teacher adjustment note: Keep section two shorter." in form.free_text
        await persist_structural_plan(
            generation_id,
            sample_plan,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
        )
        return sample_plan

    with patch("generation.v3_studio.router.run_stage1_with_retry", new=AsyncMock(side_effect=fake_stage1)):
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/chunked/{generation_id}/regenerate",
                json={"note": "Keep section two shorter."},
            )
    assert resp.status_code == 200
    state = await load_chunked_state(generation_id)
    context = state.get("context") if isinstance(state, dict) else None
    assert isinstance(context, dict)
    form_raw = context.get("form")
    assert isinstance(form_raw, dict)
    assert "Teacher adjustment note: Keep section two shorter." in str(form_raw.get("free_text"))


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

    async with _client() as client:
        blocked = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
    assert blocked.status_code == 200
    assert blocked.json()["next_action"] == "retry_failed_sections"

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
async def test_stage2_pipeline_exception_persists_resumeable_error_state() -> None:
    app.dependency_overrides[get_current_user] = _override_user_a
    await _ensure_user(TEST_USER_A)
    generation_id = str(uuid.uuid4())
    signals, form = _seed_context_models()
    sample_plan = _sample_structural_plan()

    from generation.v3_studio.router import _ensure_chunked_generation_row, _run_chunked_stage2_pipeline

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

    with (
        patch(
            "generation.v3_studio.router.resume_stage2",
            new=AsyncMock(side_effect=RuntimeError("stage2 exploded")),
        ),
        patch("generation.v3_studio.router._chunked_emit_event", new=AsyncMock()),
    ):
        await _run_chunked_stage2_pipeline(generation_id=generation_id, user_id=TEST_USER_A.id)

    async with _client() as client:
        response = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")

    assert response.status_code == 200
    assert response.json()["stage"] == "stage2_error"
    assert response.json()["next_action"] == "resume_stage2"
    assert response.json()["error_type"] == "RuntimeError"


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

    assert response.status_code == 200
    assert response.json()["stage"] == "stage2_running"
    pipeline.assert_awaited_once_with(generation_id=generation_id, user_id=TEST_USER_A.id)


@pytest.mark.asyncio
async def test_chunked_retry_section_can_unblock_assembly() -> None:
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

    async def fake_assembly(**kwargs):  # noqa: ANN001
        await persist_chunked_state(
            generation_id,
            {
                "stage": "blueprint_ready",
                "failed_sections": [],
                "execution_started": True,
                "blueprint_id": "bp-123",
            },
        )

    with (
        patch(
            "generation.v3_studio.router.retry_failed_section",
            new=AsyncMock(
                return_value=[
                    SectionBrief(
                        section_id="intro",
                        components=[
                            ComponentBrief(
                                component_id="hook-hero",
                                content_intent="recovered brief",
                            )
                        ],
                        question_briefs=[],
                        visual_strategy=None,
                    )
                ]
            ),
        ),
        patch("generation.v3_studio.router._attempt_chunked_assembly", new=AsyncMock(side_effect=fake_assembly)),
    ):
        async with _client() as client:
            resp = await client.post(
                f"/api/v1/v3/chunked/{generation_id}/retry-section",
                json={"section_id": "intro"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "blueprint_ready"
    assert body["execution_started"] is True
    queue = await v3_studio_store.get_chunked_queue(generation_id)
    assert queue is not None
    start_chunk = await asyncio.wait_for(queue.get(), timeout=5)
    done_chunk = await asyncio.wait_for(queue.get(), timeout=5)
    assert isinstance(start_chunk, str)
    assert isinstance(done_chunk, str)
    assert _parse_sse_event_name(start_chunk) == "stage2_section_start"
    assert _parse_sse_event_name(done_chunk) == "stage2_section_done"
    assert _parse_sse_payload(done_chunk) == {
        "generation_id": generation_id,
        "section_id": "intro",
        "brief": {
            "components": [
                {
                    "component_id": "hook-hero",
                    "content_intent": "recovered brief",
                }
            ],
            "question_prompts": [],
            "visual_subject": None,
        },
    }


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
        question_briefs=[
            QuestionBrief(
                question_id="q1",
                prompt_text="Which fraction strips show the same amount?",
                expected_answer="The strips that cover the same length are equivalent.",
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

    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=AsyncMock(side_effect=fake_stage2_pipeline)):
        async with _client() as client:
            approve = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
            assert approve.status_code == 200

    queue = await v3_studio_store.get_chunked_queue(generation_id)
    assert queue is not None
    events: list[tuple[str, dict]] = []
    for _ in range(4):
        chunk = await asyncio.wait_for(queue.get(), timeout=5)
        assert isinstance(chunk, str)
        events.append((_parse_sse_event_name(chunk), _parse_sse_payload(chunk)))

    assert [event for event, _payload in events] == [
        "stage2_section_start",
        "stage2_section_retry",
        "stage2_section_done",
        "stage2_complete",
    ]
    assert events[2][1] == {
        "generation_id": generation_id,
        "section_id": "intro",
        "brief": {
            "components": [
                {"component_id": "hook-hero", "content_intent": "Set up the anchor visually."}
            ],
            "question_prompts": ["Which two fractions show the same amount?"],
            "visual_subject": "A fraction strip comparison",
        },
    }
