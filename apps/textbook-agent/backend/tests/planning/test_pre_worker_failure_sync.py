"""Pre-worker native failure must sync generation status, chunked stage, error, and events."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.v3_studio.router import _run_chunked_stage2_pipeline
from planning.whole_lesson.native_status import project_native_status
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.teaching_agent import run_lesson_approach_planner
from planning.whole_lesson.teaching_plan import TeachingPlan
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
)


def _teaching_packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-provider-failure",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="a1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause"]),
        ],
        limits=LessonLimits(),
        resource_id="lesson",
    )


async def _run_through_teaching_boundary(*_args: Any, **_kwargs: Any) -> None:
    await run_lesson_approach_planner(_teaching_packet(), require_items=False)


async def _run_deterministic_input_boundary(*_args: Any, **_kwargs: Any) -> None:
    await run_lesson_approach_planner(_teaching_packet(), require_items=True)


def _sample_plan() -> StructuralPlan:
    return StructuralPlan(
        document_contract_version=2,
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end students can explain why plants need light.",
            structure_rationale="Concrete-first structure for novice learners.",
        ),
        anchor=AnchorSpec(
            example="two plants on a windowsill",
            reuse_scope="intro then explain then check",
        ),
        prior_knowledge=["plants grow"],
        sections=[
            SectionPlan(
                id="orient",
                title="Orient",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")],
            )
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="orient",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )


async def _seed_native_pre_worker() -> tuple[str, str]:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    plan = _sample_plan()
    signals = {
        "topic": "Plants",
        "subtopic": "Light",
        "prior_knowledge": ["plants grow"],
        "learner_needs": [],
        "teacher_goal": "Explain light",
        "inferred_lesson_mode": "first_exposure",
        "lesson_mode_confidence": "high",
    }
    form = {
        "grade_level": "Grade 4",
        "subject": "Science",
        "duration_minutes": 45,
        "resource_type": "lesson",
        "topic": "plants and light",
        "subtopics": ["windowsill plants"],
        "prior_knowledge": "plants grow",
        "outcome": "Students can explain why plants need light.",
        "struggle": "",
        "learner_level": "on_grade",
        "reading_level": "on_grade",
        "language_support": "none",
        "prior_knowledge_level": "some_background",
        "free_text": "",
    }
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="pending",
                chunked_state_json={
                    "stage": "stage2_running",
                    "native_whole_lesson": True,
                    "skip_item_generation": True,
                    "context": {
                        "native_whole_lesson": True,
                        "signals": signals,
                        "form": form,
                        "resource_spec": {
                            "resource_type": "lesson",
                            "depth": "standard",
                            "spec": {},
                            "rendered": "x",
                        },
                    },
                    "structural_plan": plan.model_dump(mode="json"),
                    "variant_spec": {
                        "label": "everyone",
                        "group_description": "whole class",
                        "voice": {
                            "register_name": "balanced",
                            "tone": "encouraging",
                            "notation": None,
                        },
                    },
                },
            )
        )
        await session.commit()
    return gid, user_id


@pytest.mark.asyncio
async def test_teaching_planner_failure_syncs_all_status_sources() -> None:
    gid, user_id = await _seed_native_pre_worker()

    with (
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=AsyncMock(side_effect=RuntimeError("teaching planner boom")),
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_terminal"
        chunked = dict(generation.chunked_state_json or {})
        assert chunked.get("stage") == "failed_terminal"
        assert chunked.get("stage") != "stage2_error"
        page = dict(chunked.get("page_document_v2") or {})
        execution = dict(page.get("execution") or {})
        last_error = dict(execution.get("last_error") or {})
        assert last_error.get("stage") == "planning_teaching"
        assert "teaching planner boom" in str(last_error.get("message") or "")
        assert "retryable" in last_error
        assert generation.error == last_error.get("message")
        assert generation.error_type == last_error.get("type")
        assert generation.error_code == last_error.get("code")
        events = list(page.get("events") or [])
        assert any(
            str(event.get("type") or "") == "pre_worker_failure"
            and str(event.get("status") or "") == "failed_terminal"
            for event in events
        )
        projected = project_native_status(
            gid,
            chunked,
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["stage"] == "failed_terminal"
        assert projected.get("next_action") == "inspect_error"
        assert projected.get("error_detail")
        assert "teaching planner boom" in str(projected["error_detail"].get("message") or "")


@pytest.mark.asyncio
async def test_recoverable_teaching_failure_syncs_generation_error_aliases() -> None:
    gid, user_id = await _seed_native_pre_worker()

    with (
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=AsyncMock(side_effect=TimeoutError("provider timed out")),
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        chunked = dict(generation.chunked_state_json or {})
        assert chunked.get("stage") == generation.status
        page = dict(chunked.get("page_document_v2") or {})
        last_error = dict((page.get("execution") or {}).get("last_error") or {})
        assert last_error.get("stage") == "planning_teaching"
        assert generation.error == last_error.get("message")
        assert generation.error_type == last_error.get("type")
        assert generation.error_code == last_error.get("code")
        projected = project_native_status(
            gid,
            chunked,
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["next_action"] == "retry_teaching"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_error, expected_code",
    [
        (TimeoutError("provider timed out"), "TIMEOUT"),
        (
            ModelAPIError(model_name="deepseek-v4", message="Connection error."),
            "TRANSPORT",
        ),
    ],
    ids=["timeout", "model-api-error"],
)
async def test_teaching_boundary_preserves_recoverable_provider_failure(
    provider_error: Exception,
    expected_code: str,
) -> None:
    gid, user_id = await _seed_native_pre_worker()
    model_call = AsyncMock(side_effect=provider_error)

    with (
        patch(
            "planning.whole_lesson.teaching_agent._call_teaching_model",
            new=model_call,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_run_through_teaching_boundary,
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    assert model_call.await_count == 2
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        chunked = dict(generation.chunked_state_json or {})
        last_error = dict(
            ((chunked.get("page_document_v2") or {}).get("execution") or {}).get(
                "last_error"
            )
            or {}
        )
        assert last_error.get("type") == type(provider_error).__name__
        assert last_error.get("code") == expected_code
        assert last_error.get("retryable") is True
        projected = project_native_status(
            gid,
            chunked,
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["next_action"] == "retry_teaching"


@pytest.mark.asyncio
async def test_teaching_boundary_persists_schema_exhaustion_as_recoverable() -> None:
    gid, user_id = await _seed_native_pre_worker()
    schema_error = UnexpectedModelBehavior("Exceeded maximum output retries (0)")
    model_call = AsyncMock(side_effect=schema_error)

    with (
        patch(
            "planning.whole_lesson.teaching_agent._call_teaching_model",
            new=model_call,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_run_through_teaching_boundary,
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    assert model_call.await_count == 2
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        chunked = dict(generation.chunked_state_json or {})
        page = dict(chunked.get("page_document_v2") or {})
        last_error = dict(
            (page.get("execution") or {}).get("last_error")
            or {}
        )
        assert last_error.get("type") == "TeachingPlanOutputInvalidError"
        assert last_error.get("code") == "MODEL_OUTPUT_INVALID"
        assert last_error.get("retryable") is True
        assert not page.get("teaching_plan")
        projected = project_native_status(
            gid,
            chunked,
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["next_action"] == "retry_teaching"


@pytest.mark.asyncio
async def test_teaching_boundary_persists_semantic_exhaustion_as_recoverable() -> None:
    gid, user_id = await _seed_native_pre_worker()
    invalid = TeachingPlan(
        arc="Invalid empty lesson",
        anchor_usage=[],
        sections=[],
    )
    model_call = AsyncMock(return_value=(invalid, invalid.model_dump_json()))

    with (
        patch(
            "planning.whole_lesson.teaching_agent._call_teaching_model",
            new=model_call,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_run_through_teaching_boundary,
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    assert model_call.await_count == 2
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        chunked = dict(generation.chunked_state_json or {})
        page = dict(chunked.get("page_document_v2") or {})
        last_error = dict((page.get("execution") or {}).get("last_error") or {})
        assert last_error.get("code") == "MODEL_OUTPUT_INVALID"
        assert last_error.get("retryable") is True
        assert not page.get("teaching_plan")
        projected = project_native_status(
            gid,
            chunked,
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["next_action"] == "retry_teaching"


@pytest.mark.asyncio
async def test_generic_unexpected_model_behavior_remains_terminal() -> None:
    gid, user_id = await _seed_native_pre_worker()
    model_call = AsyncMock(
        side_effect=UnexpectedModelBehavior("Provider returned an unexpected response")
    )

    with (
        patch(
            "planning.whole_lesson.teaching_agent._call_teaching_model",
            new=model_call,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_run_through_teaching_boundary,
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    assert model_call.await_count == 1
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_terminal"
        chunked = dict(generation.chunked_state_json or {})
        page = dict(chunked.get("page_document_v2") or {})
        last_error = dict((page.get("execution") or {}).get("last_error") or {})
        assert last_error.get("type") == "UnexpectedModelBehavior"
        assert last_error.get("code") == "UNKNOWN"
        assert last_error.get("retryable") is False
        assert not page.get("teaching_plan")


@pytest.mark.asyncio
async def test_deterministic_teaching_input_failure_is_terminal_without_provider_call() -> None:
    gid, user_id = await _seed_native_pre_worker()
    model_call = AsyncMock(side_effect=AssertionError("provider must not run"))

    with (
        patch(
            "planning.whole_lesson.teaching_agent._call_teaching_model",
            new=model_call,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_run_deterministic_input_boundary,
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    model_call.assert_not_awaited()
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_terminal"
        chunked = dict(generation.chunked_state_json or {})
        page = dict(chunked.get("page_document_v2") or {})
        last_error = dict((page.get("execution") or {}).get("last_error") or {})
        assert last_error.get("type") == "ItemPoolEmptyError"
        assert last_error.get("retryable") is False
        assert not page.get("teaching_plan")


async def _seed_planning_forms_without_form_plan() -> str:
    from planning.whole_lesson.legality import build_lesson_legality_snapshot
    from planning.whole_lesson.repository import empty_page_document_state
    from tests.planning.contract_fixtures import teaching_and_form

    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    packet = _teaching_packet()
    teaching, _form = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["lesson_legality"] = build_lesson_legality_snapshot(packet).model_dump(mode="json")
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["teaching_raw"] = "persisted-teaching-raw"
    state["form_plan"] = None
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="planning_forms",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "planning_forms",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


@pytest.mark.asyncio
async def test_injected_form_timeout_persists_through_worker_boundary() -> None:
    from planning.whole_lesson.executor import execute_after_teaching_approval
    from planning.whole_lesson.failure_injection import (
        configure_failure_injection,
        reset_failure_injection,
    )
    from planning.whole_lesson.repository import PageDocumentRepository
    from planning.whole_lesson.worker import NativeExecutionWorker

    gid = await _seed_planning_forms_without_form_plan()
    configure_failure_injection(
        enabled=True,
        generation_id=gid,
        node="planning_forms",
        fail_once=True,
    )
    form_calls = {"n": 0}

    async def _form_boom(*_a, **_k):
        form_calls["n"] += 1
        raise AssertionError("form provider must not run on injected timeout")

    try:
        async with async_session_factory() as session:
            lease = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="form-timeout-worker"
            )
            assert lease is not None
        with patch(
            "planning.whole_lesson.executor.run_form_planner",
            new=_form_boom,
        ):
            async with async_session_factory() as session:
                with pytest.raises(TimeoutError, match="injected form planner timeout"):
                    await execute_after_teaching_approval(
                        session=session,
                        generation_id=gid,
                        lease=lease,
                    )
        worker = NativeExecutionWorker(worker_id="form-timeout-worker")
        await worker._persist_failure(lease, TimeoutError("injected form planner timeout"))
    finally:
        reset_failure_injection()

    assert form_calls["n"] == 0
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        repo = PageDocumentRepository(session, gid)
        state = await repo.load_page_generation_state()
        last_error = dict((state.get("execution") or {}).get("last_error") or {})
        assert last_error.get("code") == "TIMEOUT"
        assert last_error.get("retryable") is True
        assert last_error.get("stage") == "planning_forms"
        events = list(state.get("events") or [])
        assert any(event.get("type") == "proof_fault_injected" for event in events)
        assert state.get("teaching_raw") == "persisted-teaching-raw"
        assert state.get("form_plan") is None


@pytest.mark.asyncio
async def test_form_timeout_injection_is_exact_generation_one_shot(monkeypatch) -> None:
    from planning.whole_lesson.failure_injection import (
        configure_failure_injection,
        get_failure_injection,
        load_failure_injection_from_env,
        reset_failure_injection,
    )

    gid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    configure_failure_injection(
        enabled=True, generation_id=gid, node="planning_forms", fail_once=True
    )
    hook = get_failure_injection()
    assert hook.should_fail_node(generation_id=gid, node="planning_forms") is True
    assert hook.should_fail_node(generation_id=gid, node="planning_forms") is False
    configure_failure_injection(
        enabled=True, generation_id=gid, node="planning_forms", fail_once=True
    )
    hook = get_failure_injection()
    assert hook.should_fail_node(generation_id="other", node="planning_forms") is False
    assert hook.should_fail_node(generation_id=gid, node="planning_teaching") is False
    configure_failure_injection(enabled=False, generation_id=gid, node="planning_forms")
    assert get_failure_injection().should_fail_node(generation_id=gid, node="planning_forms") is False

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("XPLORE_NATIVE_FAILURE_INJECTION", "true")
    monkeypatch.setenv("XPLORE_NATIVE_FAILURE_GENERATION_ID", gid)
    monkeypatch.setenv("XPLORE_NATIVE_FAILURE_NODE", "planning_forms")
    refused = load_failure_injection_from_env()
    assert refused.enabled is False
    assert refused.refused_reason == "production-like APP_ENV"

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("XPLORE_NATIVE_FAILURE_GENERATION_ID", raising=False)
    incomplete = load_failure_injection_from_env()
    assert incomplete.enabled is False

    monkeypatch.setenv("XPLORE_NATIVE_FAILURE_INJECTION", "true")
    monkeypatch.setenv("XPLORE_NATIVE_FAILURE_NODE", "not_a_node")
    unknown = load_failure_injection_from_env()
    assert unknown.enabled is False
    reset_failure_injection()
