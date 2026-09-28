"""Gate 1: native-only routing — no legacy retry/stage2 for native generations."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson
from print.http.v3_studio import router as studio_router


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
    assert "resume_stage2" not in source
    assert "return await resume_stage2" not in source


# P12B: /chunked/{generation_id}/retry-section (and its handler
# post_chunked_retry_section) is deleted outright — its native branch only
# duplicated the real native-retry contract already covered end-to-end via
# accept_native_retry/POST .../retry-native (see
# tests/planning/test_native_retry_pre_worker.py and
# tests/planning/test_native_retry_durability.py), and its historical-v1
# branch was already permanently read-only. See
# tests/architecture/test_p12b_whole_lesson_lifecycle_guard.py for the
# route-is-gone proof.
