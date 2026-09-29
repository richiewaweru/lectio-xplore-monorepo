"""Visual QC summary and document revision exposed on the generation detail."""

from __future__ import annotations

from print.generation.whole_lesson.states import execution_key
from print.generation.whole_lesson.visual_quality import visual_quality_summary
from print.http.v3_studio.router import _document_revision


def _state(block_execution: dict) -> dict:
    return {"page_document_v2": {"block_execution": block_execution}}


def test_empty_state_is_ready_and_not_retryable() -> None:
    summary = visual_quality_summary({})
    assert summary["status"] == "ready"
    assert summary["retryable"] is False


def test_failed_visual_callback_is_retryable_after_ready_asset() -> None:
    key = execution_key("section-1", "figure-1")
    summary = visual_quality_summary(
        _state(
            {
                key: {
                    "object": "figure",
                    "status": "ready",
                    "request_id": "req-figure-1",
                    "content": {"asset": {"status": "ready", "src": "/images/a.png"}},
                    "error": {
                        "code": "VISUAL_DISPATCH",
                        "message": "fresh-session validation failed after visual patch",
                    },
                }
            }
        )
    )
    assert summary["status"] == "failed"
    assert summary["retryable"] is True
    assert summary["failed_request_ids"] == ["req-figure-1"]


def test_archived_flagged_qc_surfaces_until_accepted_replacement() -> None:
    key = execution_key("section-1", "figure-1")
    summary = visual_quality_summary(
        _state(
            {
                key: {
                    "object": "figure",
                    "status": "ready",
                    "request_id": "req-figure-1",
                    "content": {"asset": {"status": "ready", "src": "/images/a.png"}},
                    "visual_qc_history": [
                        {"status": "flagged_quality", "reasons": ["stale artwork"]}
                    ],
                }
            }
        )
    )
    assert summary["status"] == "ready_with_quality_warning"
    assert summary["retryable"] is True
    assert summary["flagged_count"] == 1


def test_document_revision_reads_page_document_revision() -> None:
    assert _document_revision({"page_document_v2": {"document_revision": 3}}) == 3
    assert _document_revision({"page_document_v2": {}}) == 0
    assert _document_revision({}) is None
