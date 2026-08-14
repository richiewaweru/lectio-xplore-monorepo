from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.dependencies import get_jwt_handler
from core.entities.user import User
from telemetry.dependencies import get_llm_call_repository
from telemetry.dtos.usage import LLMUsageBreakdownItem, LLMUsageResponse
from telemetry.service import TelemetryMonitor


def _now() -> datetime:
    return datetime.now(timezone.utc)


TEST_USER = User(
    id="telemetry-user-id",
    email="telemetry@example.com",
    name="Telemetry User",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


@asynccontextmanager
async def _client():
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


class RecordingLLMCallRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.saved: list[dict[str, object]] = []

    async def aggregate_usage(self, **kwargs) -> LLMUsageResponse:
        self.calls.append(kwargs)
        return LLMUsageResponse(
            total_calls=2,
            total_tokens_in=300,
            total_tokens_out=150,
            total_thinking_tokens=90,
            avg_tokens_out=75.0,
            avg_thinking_tokens=45.0,
            total_cost_usd=0.42,
            by_caller=[LLMUsageBreakdownItem(key="planner", calls=2, tokens_in=300, tokens_out=150, total_thinking_tokens=90, avg_tokens_out=75.0, avg_thinking_tokens=45.0, cost_usd=0.42)],
            by_model=[LLMUsageBreakdownItem(key="claude-sonnet-4-6", calls=2, tokens_in=300, tokens_out=150, total_thinking_tokens=90, avg_tokens_out=75.0, avg_thinking_tokens=45.0, cost_usd=0.42)],
            by_slot=[LLMUsageBreakdownItem(key="standard", calls=2, tokens_in=300, tokens_out=150, total_thinking_tokens=90, avg_tokens_out=75.0, avg_thinking_tokens=45.0, cost_usd=0.42)],
            by_node=[LLMUsageBreakdownItem(key="v3_stage1_planner", calls=2, tokens_in=300, tokens_out=150, total_thinking_tokens=90, avg_tokens_out=75.0, avg_thinking_tokens=45.0, cost_usd=0.42)],
        )

    async def save_call(self, **kwargs) -> None:
        self.saved.append(kwargs)


async def override_current_user():
    return TEST_USER


async def test_llm_usage_route_scopes_to_authenticated_user() -> None:
    repo = RecordingLLMCallRepo()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_llm_call_repository] = lambda: repo

    jwt_handler = get_jwt_handler()
    headers = {"Authorization": f"Bearer {jwt_handler.create_access_token(TEST_USER.id, TEST_USER.email)}"}

    try:
        async with _client() as client:
            response = await client.get(
                "/api/v1/telemetry/llm-usage",
                params={
                    "caller": "planner",
                    "model_name": "claude-sonnet-4-6",
                    "slot": "standard",
                    "trace_id": "planning-trace-1",
                },
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_calls"] == 2
    assert payload["total_tokens_in"] == 300
    assert payload["total_thinking_tokens"] == 90
    assert payload["avg_thinking_tokens"] == 45.0
    assert payload["by_caller"][0]["key"] == "planner"
    assert payload["by_node"][0]["key"] == "v3_stage1_planner"
    assert repo.calls == [
        {
            "user_id": TEST_USER.id,
            "date_from": None,
            "date_to": None,
            "caller": "planner",
            "model_name": "claude-sonnet-4-6",
            "slot": "standard",
            "trace_id": "planning-trace-1",
        }
    ]


async def test_v3_recorder_registration_scopes_llm_events() -> None:
    repo = RecordingLLMCallRepo()
    monitor = TelemetryMonitor()

    async def load_llm_repo():
        return repo

    monitor.configure(llm_call_repository_factory=load_llm_repo)
    await monitor.initialise_v3_recorder(
        generation_id="telemetry-v3-finalize",
        user_id=TEST_USER.id,
        blueprint_title="Triangles",
        subject="Mathematics",
        template_id="guided-concept-path",
    )
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_succeeded",
            "generation_id": "telemetry-v3-finalize",
            "trace_id": "telemetry-v3-finalize",
            "caller": "section_writer",
            "slot": "standard",
        }
    )

    assert repo.saved[0]["user_id"] == TEST_USER.id
    assert repo.saved[0]["caller"] == "section_writer"


async def test_trace_registered_event_scopes_pre_generation_llm_events() -> None:
    repo = RecordingLLMCallRepo()
    monitor = TelemetryMonitor()

    async def load_llm_repo():
        return repo

    monitor.configure(llm_call_repository_factory=load_llm_repo)
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "trace_registered",
            "trace_id": "studio-preflight-trace",
            "user_id": TEST_USER.id,
            "source": "planning",
        }
    )
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_failed",
            "trace_id": "studio-preflight-trace",
            "generation_id": None,
            "caller": "v3_studio",
            "node": "v3_narrow",
            "slot": "fast",
            "attempt": 1,
            "error": "boom",
        }
    )

    assert repo.saved[0]["user_id"] == TEST_USER.id
    assert repo.saved[0]["trace_id"] == "studio-preflight-trace"
    assert repo.saved[0]["generation_id"] is None
    assert repo.saved[0]["node"] == "v3_narrow"


async def test_registered_parent_trace_scopes_derived_planning_call() -> None:
    repo = RecordingLLMCallRepo()
    monitor = TelemetryMonitor()

    async def load_llm_repo():
        return repo

    monitor.configure(llm_call_repository_factory=load_llm_repo)
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "trace_registered",
            "trace_id": "path-prepare:user-id:request-id",
            "user_id": TEST_USER.id,
            "source": "planning",
        }
    )
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_succeeded",
            "trace_id": "path-prepare:user-id:request-id:structural1",
            "generation_id": None,
            "caller": "planner",
            "node": "v2_structural_planner",
            "slot": "standard",
            "attempt": 1,
        }
    )

    assert repo.saved[0]["user_id"] == TEST_USER.id
    assert repo.saved[0]["trace_id"] == "path-prepare:user-id:request-id:structural1"
    assert repo.saved[0]["generation_id"] is None


async def test_failed_llm_event_persists_retryable_and_error_class_in_existing_fields() -> None:
    repo = RecordingLLMCallRepo()
    monitor = TelemetryMonitor()

    async def load_llm_repo():
        return repo

    monitor.configure(llm_call_repository_factory=load_llm_repo)
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "trace_registered",
            "trace_id": "planning-trace-errors",
            "user_id": TEST_USER.id,
            "source": "planning",
        }
    )
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_failed",
            "trace_id": "planning-trace-errors",
            "generation_id": None,
            "caller": "planner",
            "node": "v2_path_planner",
            "slot": "fast",
            "attempt": 2,
            "retryable": False,
            "error": "provider rejected request",
            "error_class": "ModelHTTPError",
        }
    )

    assert repo.saved[0]["retryable"] is False
    assert repo.saved[0]["error"] == "[ModelHTTPError] provider rejected request"


async def test_failed_llm_event_persists_inherent_retryability_at_final_attempt() -> None:
    repo = RecordingLLMCallRepo()
    monitor = TelemetryMonitor()

    async def load_llm_repo():
        return repo

    monitor.configure(llm_call_repository_factory=load_llm_repo)
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "trace_registered",
            "trace_id": "planning-trace-connection",
            "user_id": TEST_USER.id,
            "source": "planning",
        }
    )
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_failed",
            "trace_id": "planning-trace-connection",
            "generation_id": None,
            "caller": "planner",
            "node": "v2_form_planner",
            "slot": "fast",
            "attempt": 2,
            # Retryable describes the error, not whether this local runner has
            # another attempt left.
            "retryable": True,
            "error": "Connection error",
            "error_class": "ModelAPIError",
        }
    )

    assert repo.saved[0]["attempt"] == 2
    assert repo.saved[0]["retryable"] is True
    assert repo.saved[0]["error"] == "[ModelAPIError] Connection error"


async def test_failed_llm_event_preserves_error_class_when_message_is_empty() -> None:
    repo = RecordingLLMCallRepo()
    monitor = TelemetryMonitor()

    async def load_llm_repo():
        return repo

    monitor.configure(llm_call_repository_factory=load_llm_repo)
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "trace_registered",
            "trace_id": "native-timeout-trace",
            "user_id": TEST_USER.id,
            "source": "native_generation",
        }
    )
    await monitor._handle_event(  # noqa: SLF001
        {
            "type": "llm_call_failed",
            "trace_id": "native-timeout-trace",
            "generation_id": "native-timeout-generation",
            "caller": "v3_item_executor",
            "node": "v3_item_executor",
            "slot": "standard",
            "attempt": 1,
            "retryable": False,
            "error": "",
            "error_class": "TimeoutError",
        }
    )

    assert repo.saved[0]["error"] == "[TimeoutError]"
