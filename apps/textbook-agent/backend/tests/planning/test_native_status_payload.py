"""Gate 8: native status projection fields and next_action mapping."""

from __future__ import annotations

from planning.whole_lesson.native_status import project_native_status
from planning.whole_lesson.states import execution_key


def _native_state(*, stage: str, block_execution: dict | None = None) -> dict:
    return {
        "native_whole_lesson": True,
        "stage": stage,
        "page_document_v2": {
            "schema_version": 1,
            "form_plan": {
                "sections": [
                    {
                        "slot_id": "section-1",
                        "forms": [{"block_id": "s1-b1", "object": "prose"}],
                    },
                    {
                        "slot_id": "section-2",
                        "forms": [{"block_id": "s2-b1", "object": "prose"}],
                    },
                    {
                        "slot_id": "section-3",
                        "forms": [{"block_id": "s3-b1", "object": "questions"}],
                    },
                    {
                        "slot_id": "section-4",
                        "forms": [
                            {"block_id": "s4-questions", "object": "questions"}
                        ],
                    },
                ]
            },
            "block_execution": block_execution or {},
            "execution": {"last_error": None},
        },
    }


def test_native_status_writing_projection() -> None:
    key1 = execution_key("section-1", "s1-b1")
    key2 = execution_key("section-2", "s2-b1")
    state = _native_state(
        stage="writing_sections",
        block_execution={
            key1: {"status": "ready", "block_id": "s1-b1", "section_id": "section-1"},
            key2: {
                "status": "visual_pending",
                "block_id": "s2-b1",
                "section_id": "section-2",
            },
        },
    )
    projected = project_native_status("fixture-generation-001", state, None)
    assert projected is not None
    assert projected["stage"] == "writing_sections"
    assert projected["document_version"] == 2
    assert projected["document_exists"] is False
    assert projected["sections_total"] == 4
    assert projected["sections_ready"] == 2
    assert projected["blocks_total"] == 4
    assert projected["blocks_ready"] == 2
    assert projected["blocks_failed"] == 0
    assert projected["next_action"] == "wait"
    assert projected["error"] is None


def test_native_status_awaiting_visuals_is_not_active_execution() -> None:
    projected = project_native_status(
        "fixture-generation-visual-review",
        _native_state(stage="awaiting_visuals"),
    )

    assert projected is not None
    assert projected["stage"] == "awaiting_visuals"
    assert projected["next_action"] == "wait_visuals"
    assert projected["execution_started"] is False


def test_native_status_prefers_live_checkpoint_over_stale_generation_row() -> None:
    projected = project_native_status(
        "fixture-generation-running",
        _native_state(stage="stage2_running"),
        generation_status="awaiting_review",
    )

    assert projected is not None
    assert projected["stage"] == "stage2_running"
    assert projected["execution_started"] is False


def test_native_status_recoverable_failure_has_structured_error() -> None:
    key_fail = execution_key("section-4", "s4-questions")
    state = _native_state(
        stage="failed_recoverable",
        block_execution={
            execution_key("section-1", "s1-b1"): {
                "status": "ready",
                "block_id": "s1-b1",
                "section_id": "section-1",
            },
            execution_key("section-2", "s2-b1"): {
                "status": "ready",
                "block_id": "s2-b1",
                "section_id": "section-2",
            },
            execution_key("section-3", "s3-b1"): {
                "status": "ready",
                "block_id": "s3-b1",
                "section_id": "section-3",
            },
            key_fail: {
                "status": "failed_recoverable",
                "block_id": "s4-questions",
                "section_id": "section-4",
                "error": {
                    "scope": "block",
                    "code": "VALIDATION",
                    "message": "questions item contains forbidden property correct_key",
                    "retryable": True,
                    "section_id": "section-4",
                    "block_id": "s4-questions",
                    "validation_errors": [
                        {
                            "path": "content.items.0.correct_key",
                            "message": "Extra inputs are not permitted",
                        }
                    ],
                },
            },
        },
    )
    projected = project_native_status("fixture-generation-002", state, None)
    assert projected is not None
    assert projected["stage"] == "failed_recoverable"
    assert projected["next_action"] == "retry_native"
    assert projected["sections_failed"] == 1
    assert projected["failed_section_ids"] == ["section-4"]
    assert projected["failed_block_ids"] == ["s4-questions"]
    assert projected["error"]
    assert projected["error_detail"]["code"] == "VALIDATION"
    assert projected["error_detail"]["retryable"] is True
    assert projected["error_detail"]["validation_errors"]


def test_native_status_ready_with_document() -> None:
    keys = {
        execution_key("section-1", "s1-b1"): {
            "status": "ready",
            "block_id": "s1-b1",
            "section_id": "section-1",
        },
        execution_key("section-2", "s2-b1"): {
            "status": "ready",
            "block_id": "s2-b1",
            "section_id": "section-2",
        },
        execution_key("section-3", "s3-b1"): {
            "status": "ready",
            "block_id": "s3-b1",
            "section_id": "section-3",
        },
        execution_key("section-4", "s4-questions"): {
            "status": "ready",
            "block_id": "s4-questions",
            "section_id": "section-4",
        },
    }
    state = _native_state(stage="ready", block_execution=keys)
    doc = {"document_version": 2, "id": "doc-1", "sections": []}
    projected = project_native_status("fixture-generation-003", state, doc)
    assert projected is not None
    assert projected["document_exists"] is True
    assert projected["document_version"] == 2
    assert projected["sections_ready"] == 4
    assert projected["blocks_ready"] == 4
    assert projected["next_action"] == "done"
    assert projected["error"] is None


def test_native_status_terminal_never_null_error() -> None:
    state = _native_state(stage="failed_terminal", block_execution={})
    state["page_document_v2"]["execution"] = {
        "last_error": {
            "code": "PROGRAMMING",
            "message": "TypeError boom",
            "retryable": False,
        }
    }
    projected = project_native_status("gen-term", state, None)
    assert projected is not None
    assert projected["next_action"] == "inspect_error"
    assert projected["error"] == "TypeError boom"
    assert projected["error_detail"]["code"] == "PROGRAMMING"


def test_normalize_chunked_status_uses_native_projector() -> None:
    from generation.v3_studio.router import _normalize_chunked_status

    state = _native_state(stage="awaiting_teaching_approval")
    dto = _normalize_chunked_status(
        "gen-approve",
        state,
        None,
        generation_status="awaiting_teaching_approval",
    )
    assert dto.next_action == "approve_teaching"
    assert dto.document_version == 2
    assert dto.sections_total == 4
