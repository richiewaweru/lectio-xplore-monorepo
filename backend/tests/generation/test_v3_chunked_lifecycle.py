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
            "inferred_resource_type": "lesson",
            "confidence": "medium",
        },
        "form": {
            "grade_level": "Grade 6",
            "subject": "Math",
            "duration_minutes": 45,
            "topic": "Equivalent fractions",
            "subtopics": ["pizza slices"],
            "prior_knowledge": "equal sharing",
            "lesson_mode": "first_exposure",
            "lesson_mode_other": "",
            "intended_outcome": "understand",
            "intended_outcome_other": "",
            "learner_level": "on_grade",
            "reading_level": "on_grade",
            "language_support": "none",
            "prior_knowledge_level": "some_background",
            "support_needs": [],
            "learning_preferences": [],
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


def _parse_sse_event_name(chunk: str) -> str:
    for line in chunk.splitlines():
        if line.startswith("event:"):
            return line.partition(":")[2].strip()
    return ""


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
        {"stage": "blueprint_ready", "execution_started": True, "blueprint_id": "bp-123"},
    )
    async with _client() as client:
        ready = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
    assert ready.status_code == 200
    assert ready.json()["next_action"] == "generation_running"


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
        await _chunked_emit_event(generation_id, "stage2_section_failed", {"generation_id": generation_id, "section_id": "intro", "errors": ["capacity"]})
        await _chunked_emit_event(generation_id, "stage2_complete", {"generation_id": generation_id, "failed_sections": ["intro"]})
        await persist_chunked_state(generation_id, {"stage": "assembly_blocked", "failed_sections": ["intro"]})

    with patch("generation.v3_studio.router._run_chunked_stage2_pipeline", new=AsyncMock(side_effect=fake_stage2_pipeline)):
        async with _client() as client:
            approve = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve")
            assert approve.status_code == 200

    queue = await v3_studio_store.get_chunked_queue(generation_id)
    assert queue is not None
    event_names: list[str] = []
    for _ in range(4):
        chunk = await asyncio.wait_for(queue.get(), timeout=5)
        assert isinstance(chunk, str)
        event_names.append(_parse_sse_event_name(chunk))

    assert event_names == [
        "stage2_section_start",
        "stage2_section_retry",
        "stage2_section_failed",
        "stage2_complete",
    ]
