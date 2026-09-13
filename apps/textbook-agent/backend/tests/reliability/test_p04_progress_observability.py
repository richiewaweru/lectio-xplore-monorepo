"""P04 durable progress API + observability (G16–G18)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from application.unit_lesson.progress_routes import get_progress_store
from application.unit_lesson.realizations import admit_realization
from core.auth.middleware import get_current_user
from core.database.models import (
    GenerationModel,
    NativeRealizationModel,
    PathLessonModel,
    UserModel,
)
from core.database.session import async_session_factory
from core.entities.user import User
from curriculum.service import approve_path, create_unit, persist_path_plan
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringProviderCall,
    AuthoringRequest,
)
from infra.authoring.engine import AuthoringRegistry
from infra.execution.progress import ProgressStore, redact_secrets
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


OWNER = User(
    id="p04-owner",
    email="p04-owner@example.invalid",
    name="P04 Owner",
    picture_url=None,
    has_profile=True,
    created_at="2026-09-13T00:00:00+00:00",
    updated_at="2026-09-13T00:00:00+00:00",
)

OTHER = User(
    id="p04-other",
    email="p04-other@example.invalid",
    name="P04 Other",
    picture_url=None,
    has_profile=True,
    created_at="2026-09-13T00:00:00+00:00",
    updated_at="2026-09-13T00:00:00+00:00",
)


async def _ensure_user(user: User) -> None:
    async with async_session_factory() as session:
        model = await session.get(UserModel, user.id)
        if model is None:
            session.add(UserModel(id=user.id, email=user.email, name=user.name or user.id))
            await session.commit()


async def _prepared_realization(*, user_id: str) -> NativeRealizationModel:
    async with async_session_factory() as session:
        user = await session.get(UserModel, user_id)
        if user is None:
            session.add(UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id))
            await session.flush()
        plan = load_canonical_plan("grade4-photosynthesis-path.json")
        unit = await create_unit(
            session,
            owner_id=user_id,
            request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        prep_id = f"prep-{user_id}-{uuid.uuid4().hex[:8]}"
        session.add(
            GenerationModel(
                id=prep_id,
                user_id=user_id,
                subject="science",
                context="shared prep",
                status="awaiting_review",
                requested_template_id="lesson",
                requested_preset_id="standard",
                created_at=_utcnow(),
                chunked_state_json={
                    "shared_preparation": True,
                    "stage": "awaiting_teaching_approval",
                    "teaching_plan_id": f"tp-{user_id}",
                    "teaching_review": {"approved_revision": 1, "status": "approved"},
                    "teaching_plan": {
                        "teaching_plan_id": f"tp-{user_id}",
                        "revision": 1,
                        "hash": "abc",
                    },
                },
            )
        )
        await session.flush()
        row, _created = await admit_realization(
            session,
            path_lesson_id=lesson.id,
            path="learn",
            teaching_plan_id=f"tp-{user_id}",
            teaching_plan_revision=1,
            teaching_plan_hash="abc",
            preparation_generation_id=prep_id,
            pack_id=prep_id,
            admission_request_key=f"p04-{uuid.uuid4().hex}",
        )
        row.status = "writing"
        row.realization_revision = 2
        await session.commit()
        realization_id = row.id

    async with async_session_factory() as session:
        loaded = await session.get(NativeRealizationModel, realization_id)
        assert loaded is not None
        # Touch columns while session is open.
        _ = (
            loaded.id,
            loaded.path,
            loaded.status,
            loaded.realization_revision,
            loaded.teaching_plan_revision,
            loaded.path_lesson_id,
        )
        session.expunge(loaded)
        return loaded


def _definition() -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id="p04-demo",
        native_path="learn",
        modes=("generate",),
        instructions="Return a tiny payload.",
        payload_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "text"],
            "properties": {
                "kind": {"const": "paragraph"},
                "text": {"type": "string", "minLength": 1},
            },
        },
        definition_hash="p04-def-hash",
    )


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        return self.payload


# --- G16: durable status / ordered replay / retention snapshot -----------------


def test_g16_status_counts_retries_actions_and_ordered_replay() -> None:
    store = ProgressStore(event_retention=50)
    store.ensure_run(
        "run-1",
        path="learn",
        owner_user_id="u1",
        status="writing",
        stage="writing",
        realization_revision=2,
        teaching_plan_revision=1,
        total=3,
    )
    store.set_counts("run-1", completed=1, total=3)
    store.set_item_state("run-1", item_id="n1", stage="writing", attempt=1, state="running")
    store.schedule_retry(
        "run-1",
        item_id="n2",
        attempt=2,
        next_retry_at=datetime.now(UTC) + timedelta(seconds=30),
        reason="rate_limit",
    )
    e1 = store.append_event("run-1", event_type="stage_entered", stage="writing", item_id="n1")
    e2 = store.append_event("run-1", event_type="item_started", item_id="n1", attempt=1)
    e3 = store.append_event("run-1", event_type="item_completed", item_id="n0", attempt=1)

    status = store.get_status("run-1")
    assert status.completed == 1
    assert status.total == 3
    assert status.active_items[0].item_id == "n1"
    assert status.retry_schedule[0].item_id == "n2"
    assert "retry" not in status.allowed_actions  # writing is cancel/refresh
    assert "cancel" in status.allowed_actions
    assert status.revisions["realization_revision"] == 2
    assert [e1.seq, e2.seq, e3.seq] == [1, 2, 3]

    replay = store.replay("run-1", after_seq=1)
    assert replay.mode == "replay"
    assert [event.seq for event in replay.events] == [2, 3]

    # Duplicate reconnect with same cursor is idempotent.
    again = store.replay("run-1", after_seq=1)
    assert [event.seq for event in again.events] == [2, 3]


def test_g16_retention_gap_returns_snapshot() -> None:
    store = ProgressStore(event_retention=3)
    store.ensure_run("run-ret", path="print", owner_user_id="u1", status="running")
    for i in range(1, 6):
        store.append_event("run-ret", event_type="tick", payload={"i": i})
    # Retained seqs should be 3,4,5
    replay = store.replay("run-ret", after_seq=1)
    assert replay.mode == "snapshot"
    assert replay.snapshot is not None
    assert replay.snapshot["run_id"] == "run-ret"
    assert [event.seq for event in replay.events] == [3, 4, 5]
    assert replay.oldest_retained_seq == 3


@pytest.mark.asyncio
async def test_g16_http_status_agrees_with_db() -> None:
    await _ensure_user(OWNER)
    realization = await _prepared_realization(user_id=OWNER.id)
    store = ProgressStore()
    store.sync_from_db(
        realization.id,
        path=str(realization.path),
        owner_user_id=OWNER.id,
        status=str(realization.status),
        realization_revision=int(realization.realization_revision),
        teaching_plan_revision=int(realization.teaching_plan_revision),
        stage="writing",
    )
    store.set_counts(realization.id, completed=0, total=2)
    store.append_event(realization.id, event_type="run_started", stage="writing")

    async def _owner() -> User:
        return OWNER

    app.dependency_overrides[get_current_user] = _owner
    app.dependency_overrides[get_progress_store] = lambda: store
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/realizations/{realization.id}/status")
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["status"] == realization.status
            assert body["db_status"] == realization.status
            assert body["revisions"]["realization_revision"] == realization.realization_revision
            assert body["completed"] == 0
            assert body["total"] == 2
            assert body["latest_seq"] >= 1

            events = await client.get(
                f"/api/v1/realizations/{realization.id}/events",
                params={"after_seq": 0},
            )
            assert events.status_code == 200
            payload = events.json()
            assert payload["mode"] == "replay"
            assert payload["events"][0]["seq"] == 1
            assert payload["events"][0]["event_type"] == "run_started"
    finally:
        app.dependency_overrides.clear()


# --- G17: model call traces + unknown usage -----------------------------------


def test_g17_model_call_trace_links_and_unknown_usage_not_zero() -> None:
    store = ProgressStore()
    store.ensure_run("run-trace", path="learn", owner_user_id="u1", stage="writing")

    # Unknown usage stays None — never coerced to 0.
    unknown = store.record_model_call(
        "run-trace",
        path="learn",
        stage="writing",
        item_id="work-a",
        attempt=1,
        model="fake-model",
        prompt_hash="phash",
        policy_hash="polhash",
        composition_mode="llm",
        tokens_in=None,
        tokens_out=None,
        cost_usd=None,
        provider_request_id="req-1",
        emit_event=False,
    )
    assert unknown.tokens_in is None
    assert unknown.tokens_out is None
    assert unknown.cost_usd is None
    dumped = unknown.to_dict()
    assert dumped["tokens_in"] is None
    assert dumped["usage_known"] is False
    assert dumped["tokens_in"] != 0

    known = store.record_model_call(
        "run-trace",
        path="learn",
        stage="writing",
        item_id="work-a",
        attempt=2,
        model="fake-model",
        prompt_hash="phash2",
        tokens_in=10,
        tokens_out=20,
        cost_usd=0.01,
        emit_event=False,
    )
    assert known.tokens_in == 10
    traces = store.list_traces("run-trace")
    assert len(traces) == 2
    assert traces[0].run_id == "run-trace"
    assert traces[0].path == "learn"
    assert traces[0].stage == "writing"
    assert traces[0].item_id == "work-a"
    assert traces[0].attempt == 1
    assert traces[0].prompt_hash == "phash"


@pytest.mark.asyncio
async def test_g17_authoring_engine_records_trace_with_unknown_usage() -> None:
    store = ProgressStore()
    store.ensure_run("run-eng", path="learn", owner_user_id="u1")
    engine = AuthoringEngine(
        registry=AuthoringRegistry(),
        provider=FakeProvider({"kind": "paragraph", "text": "hello"}),
        progress_store=store,
        progress_run_id="run-eng",
        progress_stage="writing",
        max_transport_attempts=1,
        max_repair_attempts=0,
    )
    result = await engine.execute(
        AuthoringRequest(
            work_order_id="wo-1",
            definition=_definition(),
            scoped_request={"user_id": "u1"},
            inputs={},
            teaching_revision=1,
            mode="generate",
            policy={"policy_hash": "pol", "composition_mode": "llm"},
        )
    )
    assert result.payload["text"] == "hello"
    traces = store.list_traces("run-eng")
    assert len(traces) == 1
    trace = traces[0]
    assert trace.item_id == "wo-1"
    assert trace.attempt == 1
    assert trace.path == "learn"
    assert trace.stage == "writing"
    assert trace.prompt_hash
    assert trace.policy_hash == "pol"
    assert trace.composition_mode == "llm"
    # Fake provider returns no usage → unknown, not zero.
    assert trace.tokens_in is None
    assert trace.tokens_out is None
    assert trace.cost_usd is None


# --- G18: auth / redaction / exporter isolation -------------------------------


@pytest.mark.asyncio
async def test_g18_unauthorized_status_and_events_rejected() -> None:
    await _ensure_user(OWNER)
    await _ensure_user(OTHER)
    realization = await _prepared_realization(user_id=OWNER.id)
    store = ProgressStore()
    store.sync_from_db(
        realization.id,
        path=str(realization.path),
        owner_user_id=OWNER.id,
        status=str(realization.status),
        realization_revision=int(realization.realization_revision),
        teaching_plan_revision=int(realization.teaching_plan_revision),
    )

    app.dependency_overrides[get_progress_store] = lambda: store
    try:
        # No credentials → rejected (401/403).
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unauth = await client.get(f"/api/v1/realizations/{realization.id}/status")
            assert unauth.status_code in {401, 403}

            async def _other() -> User:
                return OTHER

            app.dependency_overrides[get_current_user] = _other
            forbidden = await client.get(f"/api/v1/realizations/{realization.id}/status")
            assert forbidden.status_code == 404
            forbidden_events = await client.get(f"/api/v1/realizations/{realization.id}/events")
            assert forbidden_events.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_g18_secrets_redacted_from_events() -> None:
    store = ProgressStore()
    store.ensure_run("run-sec", path="learn", owner_user_id="u1")
    event = store.append_event(
        "run-sec",
        event_type="debug",
        payload={
            "authorization": "Bearer secret-token",
            "api_key": "sk-live-xyz",
            "safe": "ok",
            "nested": {"password": "hunter2", "note": "visible"},
            "learner_response": "raw answer",
        },
    )
    assert event.payload["authorization"] == "***"
    assert event.payload["api_key"] == "***"
    assert event.payload["nested"]["password"] == "***"
    assert event.payload["nested"]["note"] == "visible"
    assert event.payload["learner_response"] == "***"
    assert event.payload["safe"] == "ok"
    assert redact_secrets({"access_token": "abc"})["access_token"] == "***"


def test_g18_exporter_outage_does_not_halt_generation() -> None:
    store = ProgressStore()
    store.ensure_run("run-exp", path="learn", owner_user_id="u1")
    store.record_model_call(
        "run-exp",
        path="learn",
        stage="writing",
        item_id="i1",
        attempt=1,
        model="m",
        prompt_hash="h",
        tokens_in=None,
        emit_event=False,
    )

    class BoomExporter:
        def export(self, traces: list[Any]) -> None:
            raise RuntimeError("exporter down")

    ok = store.export_traces("run-exp", BoomExporter())
    assert ok is False
    event = store.append_event("run-exp", event_type="continued")
    assert event.seq >= 1


@pytest.mark.asyncio
async def test_g18_engine_continues_when_exporter_fails() -> None:
    store = ProgressStore()
    store.ensure_run("run-eng-exp", path="learn", owner_user_id="u1")

    class BoomExporter:
        def export(self, traces: list[Any]) -> None:
            raise RuntimeError("otel unavailable")

    engine = AuthoringEngine(
        registry=AuthoringRegistry(),
        provider=FakeProvider({"kind": "paragraph", "text": "still works"}),
        progress_store=store,
        progress_run_id="run-eng-exp",
        trace_exporter=BoomExporter(),
        max_transport_attempts=1,
        max_repair_attempts=0,
    )
    result = await engine.execute(
        AuthoringRequest(
            work_order_id="wo-exp",
            definition=_definition(),
            scoped_request={"user_id": "u1"},
            inputs={},
            teaching_revision=1,
            mode="generate",
        )
    )
    assert result.payload["text"] == "still works"
    assert len(store.list_traces("run-eng-exp")) == 1
