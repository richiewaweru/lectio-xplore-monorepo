"""R01–R07: stage-aware native retry accept (202) + worker completion."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.database.models import ConceptCardModel, GenerationModel, PackItemModel, UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from generation.page_objects.document_assembly import persist_document_json
from planning.whole_lesson.native_retry import (
    NativeRetryConflict,
    NativeRetryTarget,
    accept_native_retry,
    decide_native_retry_target,
    run_pre_worker_retry,
)
from planning.whole_lesson.native_status import project_native_status
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    empty_page_document_state,
    persist_native_failure_for_generation,
)
from planning.whole_lesson.states import (
    WORK_KIND_PRE_WORKER_ITEM,
    WORK_KIND_PRE_WORKER_TEACHING,
    execution_key,
)
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
)
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state
from v3_execution.executors.item_diagnostics import attempt_record
from v3_execution.executors.item_executor import ItemGenerationResult, ItemGenerationRun
from v3_blueprint.planning.models import ItemOption, QuestionBrief


TEST_USER = User(
    id="native-retry-owner",
    email="native-retry@example.invalid",
    name="Native Retry",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)


async def _override_user() -> User:
    return TEST_USER


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


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


def _form_payload() -> dict[str, Any]:
    return {
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


def _valid_result(card_id: str) -> ItemGenerationResult:
    return ItemGenerationResult(
        card_id=card_id,
        items=[
            QuestionBrief(
                question_id=f"q{i}",
                prompt_text=f"Stem {i}",
                options=[
                    ItemOption(key="A", text="correct", correct=True, diagnoses=None),
                    ItemOption(key="B", text="wrong", correct=False, diagnoses="m1"),
                    ItemOption(key="C", text="other", correct=False, diagnoses=None),
                    ItemOption(key="D", text="other2", correct=False, diagnoses=None),
                ],
                expected_answer="correct",
            )
            for i in range(1, 6)
        ],
    )


async def _ensure_user() -> None:
    async with async_session_factory() as session:
        if await session.get(UserModel, TEST_USER.id) is None:
            session.add(
                UserModel(id=TEST_USER.id, email=TEST_USER.email, name=TEST_USER.name)
            )
            await session.commit()


async def _seed_generation(
    *,
    status: str,
    last_error: dict[str, Any] | None,
    skip_items: bool = False,
    with_cards: bool = True,
    ready_card: bool = False,
) -> tuple[str, str]:
    await _ensure_user()
    gid = str(uuid.uuid4())
    card_id = f"card-{gid[:8]}"
    plan = _sample_plan()
    page = empty_page_document_state()
    if last_error is not None:
        page["execution"]["last_error"] = last_error
    async with async_session_factory() as session:
        session.add(
            GenerationModel(
                id=gid,
                user_id=TEST_USER.id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status=status,
                pack_id=gid,
                error=(last_error or {}).get("message"),
                error_type=(last_error or {}).get("type"),
                error_code=(last_error or {}).get("code"),
                chunked_state_json={
                    "stage": status,
                    "native_whole_lesson": True,
                    "skip_item_generation": skip_items,
                    "page_document_v2": page,
                    "context": {
                        "native_whole_lesson": True,
                        "signals": {
                            "topic": "Plants",
                            "subtopic": "Light",
                            "prior_knowledge": ["plants grow"],
                            "learner_needs": [],
                            "teacher_goal": "Explain light",
                            "inferred_lesson_mode": "first_exposure",
                            "lesson_mode_confidence": "high",
                        },
                        "form": _form_payload(),
                        "resource_spec": {
                            "resource_type": "lesson",
                            "depth": "standard",
                            "spec": {},
                            "rendered": "x",
                        },
                    },
                    "structural_plan": plan.model_dump(mode="json"),
                    "item_generation": {"attempts": [], "failed_cards": []},
                },
            )
        )
        if with_cards:
            session.add(
                ConceptCardModel(
                    id=card_id,
                    pack_id=gid,
                    slug="science.plants.light",
                    title="Light",
                    objective="Explain why plants need light",
                    prereqs=[],
                    misconceptions=[
                        {"id": "m1", "description": "Plants eat soil", "source": "drafted"},
                        {
                            "id": "m2",
                            "description": "Plants only need water",
                            "source": "drafted",
                        },
                    ],
                )
            )
            if ready_card:
                for i in range(5):
                    session.add(
                        PackItemModel(
                            id=f"{gid}:q{i+1}",
                            pack_id=gid,
                            card_id=card_id,
                            stem=f"Stem {i+1}",
                            options=[
                                {
                                    "key": "a",
                                    "text": "correct",
                                    "correct": True,
                                    "diagnoses": None,
                                },
                                {
                                    "key": "b",
                                    "text": "wrong",
                                    "correct": False,
                                    "diagnoses": "m1",
                                },
                            ],
                            correct_key="a",
                            diagnoses={"a": None, "b": "m1"},
                            stale=False,
                        )
                    )
        await session.commit()
    return gid, card_id


async def _accept_and_run(
    generation_id: str,
    *,
    worker_id: str = "r-test-worker",
) -> tuple[dict[str, Any], dict[str, Any]]:
    accepted = await accept_native_retry(generation_id, user_id=TEST_USER.id)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        lease = await repo.claim_pre_worker_retry(worker_id=worker_id, lease_seconds=90)
    assert lease is not None, "expected pre-worker claim after accept"
    result = await run_pre_worker_retry(lease=lease)
    return accepted, result


async def _teaching_ok(session, generation_id, **kwargs):
    repo = PageDocumentRepository(session, generation_id)
    await repo.save_teaching_plan(
        plan={"arc": "Orient → explain → check", "sections": []},
        validation={"ok": True},
        qc=[],
        stage="awaiting_teaching_approval",
        worker_id=kwargs.get("worker_id"),
        lease_token=kwargs.get("lease_token"),
    )
    return {
        "teaching_plan": {"arc": "x"},
        "validation": {"ok": True},
        "qc": [],
        "review": {"status": "pending"},
        "packet": {},
    }


def test_decide_targets() -> None:
    assert (
        decide_native_retry_target(
            "failed_recoverable", {"stage": "item_generation", "retryable": True}
        )
        == NativeRetryTarget.ITEM_GENERATION
    )
    assert (
        decide_native_retry_target(
            "failed_recoverable", {"stage": "planning_teaching", "retryable": True}
        )
        == NativeRetryTarget.TEACHING_PLAN
    )
    assert (
        decide_native_retry_target(
            "failed_recoverable", {"stage": "planning_forms", "retryable": True}
        )
        == NativeRetryTarget.POST_APPROVAL_WORKER
    )
    assert (
        decide_native_retry_target(
            "awaiting_visuals", {"stage": "awaiting_visuals", "retryable": True}
        )
        == NativeRetryTarget.VISUALS
    )
    assert (
        decide_native_retry_target("failed_terminal", {"stage": "planning_teaching"})
        == NativeRetryTarget.NOT_RETRYABLE
    )


@pytest.mark.asyncio
async def test_r01_item_transport_failure_then_retry() -> None:
    gid, card_id = await _seed_generation(
        status="pending",
        last_error=None,
        skip_items=False,
        ready_card=False,
    )
    await persist_chunked_state(
        gid,
        {
            "item_generation": {
                "attempts": [
                    attempt_record(
                        correlation_id=f"item:{gid}:{card_id}",
                        card_id=card_id,
                        attempt=1,
                        started_at=0.0,
                        outcome_class="TIMEOUT",
                        error="timed out",
                        retryable=True,
                    )
                ],
                "failed_cards": [],
            }
        },
    )
    await persist_native_failure_for_generation(
        gid,
        exc=TimeoutError("item provider timed out"),
        stage="item_generation",
        event="pre_worker_failure",
    )

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_recoverable"
        projected = project_native_status(
            gid,
            dict(generation.chunked_state_json or {}),
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["next_action"] == "retry_items"

    item_calls: list[str] = []

    async def _ok_items(card, **_k):
        item_calls.append(card.id)
        cid = f"item:{gid}:{card.id}"
        return ItemGenerationRun(
            result=_valid_result(card.id),
            attempts=[
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=2,
                    started_at=0.0,
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=cid,
        )

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=_ok_items,
        ),
        patch(
            "generation.v3_studio.router._persist_item_results",
            new=AsyncMock(),
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_teaching_ok,
        ),
    ):
        accepted, result = await _accept_and_run(gid)

    assert accepted["status"] == "item_generation"
    assert accepted["next_action"] == "wait"
    assert accepted["work_kind"] == WORK_KIND_PRE_WORKER_ITEM
    assert result["status"] == "awaiting_teaching_approval"
    assert item_calls == [card_id]
    state = await load_chunked_state(gid)
    attempts = (state.get("item_generation") or {}).get("attempts") or []
    assert len(attempts) >= 2
    assert attempts[0]["class"] == "TIMEOUT"
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_teaching_approval"
        assert generation.error is None
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        assert (page.get("execution") or {}).get("last_error") is None
        assert (page.get("execution") or {}).get("work_kind") is None


@pytest.mark.asyncio
async def test_r02_teaching_retry_does_not_rerun_items() -> None:
    gid, _card_id = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    item_exec = AsyncMock(side_effect=AssertionError("items must not run"))
    form_planner = AsyncMock(side_effect=AssertionError("form planner must not run"))

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=item_exec,
        ),
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=_teaching_ok,
        ),
        patch(
            "planning.whole_lesson.executor.run_form_planner",
            new=form_planner,
        ),
    ):
        accepted, result = await _accept_and_run(gid)

    assert accepted["status"] == "planning_teaching"
    assert accepted["work_kind"] == WORK_KIND_PRE_WORKER_TEACHING
    assert result["status"] == "awaiting_teaching_approval"
    assert result["retry_target"] == "planning_teaching"
    item_exec.assert_not_called()
    form_planner.assert_not_called()


@pytest.mark.asyncio
async def test_r03_terminal_teaching_reject_retry() -> None:
    gid, _ = await _seed_generation(
        status="failed_terminal",
        last_error={
            "type": "ValueError",
            "code": "CONTRACT",
            "message": "contract broken",
            "stage": "planning_teaching",
            "retryable": False,
        },
        skip_items=True,
        ready_card=True,
    )
    projected = project_native_status(
        gid,
        await load_chunked_state(gid),
        None,
        generation_status="failed_terminal",
    )
    assert projected is not None
    assert projected["next_action"] == "inspect_error"
    with pytest.raises(NativeRetryConflict) as exc_info:
        await accept_native_retry(gid, user_id=TEST_USER.id)
    assert exc_info.value.code in {"INVALID_STATUS", "NOT_RETRYABLE"}


@pytest.mark.asyncio
async def test_r04_duplicate_retry_protection() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    first = await accept_native_retry(gid, user_id=TEST_USER.id)
    assert first["status"] == "planning_teaching"
    with pytest.raises(NativeRetryConflict) as exc_info:
        await accept_native_retry(gid, user_id=TEST_USER.id)
    assert exc_info.value.code == "RETRY_IN_PROGRESS"

    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teaching_ok,
    ):
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, gid)
            lease = await repo.claim_pre_worker_retry(
                worker_id="r04-worker", lease_seconds=90
            )
        assert lease is not None
        result = await run_pre_worker_retry(lease=lease)
    assert result["status"] == "awaiting_teaching_approval"


@pytest.mark.asyncio
async def test_r05_post_approval_queues() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "forms timed out",
            "stage": "planning_forms",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )
    accepted = await accept_native_retry(gid, user_id=TEST_USER.id)
    assert accepted["status"] == "queued"
    assert accepted["next_action"] == "wait"
    assert accepted["accepted"] is True
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "queued"


@pytest.mark.asyncio
async def test_r06_visual_failure_not_owned_by_retry_native() -> None:
    gid = str(uuid.uuid4())
    await _ensure_user()
    page = empty_page_document_state()
    page["execution"]["last_error"] = {
        "type": "VisualDispatchError",
        "code": "VISUAL_DISPATCH",
        "message": "dispatcher exploded",
        "stage": "awaiting_visuals",
        "retryable": True,
    }
    page["block_execution"] = {
        execution_key("explain", "fig-1"): {
            "status": "failed_recoverable",
            "object": "figure",
            "block_id": "fig-1",
            "request_id": "req-1",
            "content": {"asset": {"status": "failed", "request_id": "req-1"}},
        }
    }
    doc = {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-visual",
        "title": "Plants",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "id": "fig-1",
                        "object": "figure",
                        "intent": "explain",
                        "position": 0,
                        "content": {
                            "alt_text": "Leaf",
                            "caption": "Leaf",
                            "asset": {
                                "status": "failed",
                                "request_id": "req-1",
                                "kind": "image",
                            },
                        },
                        "layout": {"placement": "main"},
                    }
                ],
            }
        ],
    }
    async with async_session_factory() as session:
        session.add(
            GenerationModel(
                id=gid,
                user_id=TEST_USER.id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="awaiting_visuals",
                document_json=persist_document_json({}, doc),
                error="dispatcher exploded",
                error_type="VisualDispatchError",
                error_code="VISUAL_DISPATCH",
                chunked_state_json={
                    "stage": "awaiting_visuals",
                    "native_whole_lesson": True,
                    "page_document_v2": page,
                },
            )
        )
        await session.commit()

    projected = project_native_status(
        gid,
        await load_chunked_state(gid),
        doc,
        generation_status="awaiting_visuals",
    )
    assert projected is not None
    assert projected["next_action"] == "retry_visuals"

    app.dependency_overrides[get_current_user] = _override_user
    try:
        async with _client() as client:
            denied = await client.post(f"/api/v1/v3/generations/{gid}/retry-native")
            assert denied.status_code == 409
            assert denied.json()["detail"]["error_type"] == "USE_VISUALS_RETRY"

            async def fake_execute(order, emit, **kwargs):
                return [
                    type(
                        "B",
                        (),
                        {
                            "status": "ready",
                            "fallback_image_url": "https://example.test/leaf.png",
                            "html_content": None,
                        },
                    )()
                ]

            with (
                patch(
                    "planning.whole_lesson.visual_dispatch.execute_visual",
                    new=fake_execute,
                ),
                patch(
                    "generation.v3_studio.router._generate_shared_pack_items",
                    new=AsyncMock(side_effect=AssertionError("items")),
                ),
                patch(
                    "planning.whole_lesson.service.run_and_persist_teaching_plan",
                    new=AsyncMock(side_effect=AssertionError("teaching")),
                ),
                patch(
                    "planning.whole_lesson.executor.run_form_planner",
                    new=AsyncMock(side_effect=AssertionError("forms")),
                ),
            ):
                ok = await client.post(f"/api/v1/v3/generations/{gid}/visuals/retry")
            assert ok.status_code == 200, ok.text
            assert ok.json()["status"] == "ready"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_r07_error_aliases_clear_after_teaching_recovery() -> None:
    gid, _ = await _seed_generation(
        status="failed_recoverable",
        last_error={
            "type": "TimeoutError",
            "code": "TIMEOUT",
            "message": "teaching timed out",
            "stage": "planning_teaching",
            "retryable": True,
        },
        skip_items=True,
        ready_card=True,
    )

    with patch(
        "planning.whole_lesson.service.run_and_persist_teaching_plan",
        new=_teaching_ok,
    ):
        await _accept_and_run(gid)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_teaching_approval"
        assert generation.error is None
        assert generation.error_type is None
        assert generation.error_code is None
        page = dict((generation.chunked_state_json or {}).get("page_document_v2") or {})
        assert (page.get("execution") or {}).get("last_error") is None
