"""Gate 1: native-only routing — no legacy retry/stage2 for native generations."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from generation.v3_studio import router as studio_router
from planning.whole_lesson.native_routing import generation_is_native_whole_lesson


def test_generation_is_native_from_context_flag() -> None:
    assert generation_is_native_whole_lesson({"context": {"native_whole_lesson": True}})


def test_generation_is_native_from_page_document() -> None:
    assert generation_is_native_whole_lesson({"page_document_v2": {"schema_version": 1}})


def test_generation_is_native_from_top_level_flag() -> None:
    assert generation_is_native_whole_lesson({"native_whole_lesson": True})


def test_generation_is_native_from_contract_version() -> None:
    generation = SimpleNamespace(
        chunked_state_json={},
        planning_spec_json='{"document_contract_version": 2}',
        status="pending",
    )
    assert generation_is_native_whole_lesson({}, generation)


def test_generation_is_native_from_status() -> None:
    generation = SimpleNamespace(
        chunked_state_json={},
        planning_spec_json="{}",
        status="writing_sections",
    )
    assert generation_is_native_whole_lesson({}, generation)


def test_legacy_stage2_pipeline_blocks_without_calling_resume() -> None:
    source = inspect.getsource(studio_router)
    assert "LegacyBackHalfDisabled" in source
    assert "return await resume_stage2" not in source


@pytest.mark.asyncio
async def test_native_retry_section_does_not_call_legacy_retry() -> None:
    generation = SimpleNamespace(
        id="gen-native-1",
        status="writing_sections",
        chunked_state_json={
            "native_whole_lesson": True,
            "page_document_v2": {"schema_version": 1},
            "stage": "writing_sections",
        },
        planning_spec_json='{"document_contract_version": 2}',
        document_json=None,
    )
    state = {
        "native_whole_lesson": True,
        "page_document_v2": {"schema_version": 1},
        "stage": "writing_sections",
        "structural_plan": {"sections": []},
        "failed_sections": ["orient"],
    }
    body = SimpleNamespace(section_id="orient")
    user = SimpleNamespace(id="user-1")

    with (
        patch.object(
            studio_router,
            "_load_owned_generation",
            new=AsyncMock(return_value=generation),
        ),
        patch.object(
            studio_router,
            "load_chunked_state",
            new=AsyncMock(return_value=state),
        ),
        patch.object(
            studio_router,
            "retry_failed_section",
            new=AsyncMock(side_effect=AssertionError("legacy retry must not run")),
        ) as legacy_retry,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await studio_router.post_chunked_retry_section(
                "gen-native-1",
                body,  # type: ignore[arg-type]
                user,  # type: ignore[arg-type]
            )
        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert detail["error_type"] == "NativeRetryRequired"
        legacy_retry.assert_not_called()


@pytest.mark.asyncio
async def test_native_retry_section_requeues_failed_recoverable() -> None:
    generation = SimpleNamespace(
        id="gen-native-2",
        status="failed_recoverable",
        chunked_state_json={
            "native_whole_lesson": True,
            "page_document_v2": {"schema_version": 1, "execution": {}},
            "stage": "failed_recoverable",
        },
        planning_spec_json='{"document_contract_version": 2}',
        document_json=None,
    )
    state = {
        "native_whole_lesson": True,
        "page_document_v2": {"schema_version": 1, "execution": {}},
        "stage": "failed_recoverable",
    }
    body = SimpleNamespace(section_id="orient")
    user = SimpleNamespace(id="user-1")
    queued_state = {**state, "stage": "queued"}

    repo = MagicMock()
    repo.transition = AsyncMock(return_value={})
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(
            studio_router,
            "_load_owned_generation",
            new=AsyncMock(return_value=generation),
        ),
        patch.object(
            studio_router,
            "load_chunked_state",
            new=AsyncMock(side_effect=[state, queued_state]),
        ),
        patch.object(
            studio_router,
            "persist_chunked_state",
            new=AsyncMock(),
        ),
        patch.object(
            studio_router,
            "async_session_factory",
            return_value=session_cm,
        ),
        patch(
            "planning.whole_lesson.repository.PageDocumentRepository",
            return_value=repo,
        ),
        patch.object(
            studio_router,
            "retry_failed_section",
            new=AsyncMock(side_effect=AssertionError("legacy retry must not run")),
        ) as legacy_retry,
        patch.object(
            studio_router,
            "_normalize_chunked_state",
            return_value=MagicMock(stage="queued", next_action="wait"),
        ) as normalize,
    ):
        result = await studio_router.post_chunked_retry_section(
            "gen-native-2",
            body,  # type: ignore[arg-type]
            user,  # type: ignore[arg-type]
        )
        assert result.stage == "queued"
        repo.transition.assert_awaited_once()
        legacy_retry.assert_not_called()
        normalize.assert_called()
