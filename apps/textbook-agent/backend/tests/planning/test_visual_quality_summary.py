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


def _figure(qc: dict | None) -> dict:
    outcome: dict = {
        "object": "figure",
        "status": "ready",
        "request_id": "req-figure-1",
        "content": {"asset": {"status": "ready", "src": "/images/a.png"}},
    }
    if qc is not None:
        outcome["visual_qc"] = qc
    return {execution_key("section-1", "figure-1"): outcome}


def test_figure_without_qc_verdict_is_unreviewed_not_ready() -> None:
    summary = visual_quality_summary(_state(_figure(None)))
    assert summary["status"] == "unreviewed"
    assert summary["unreviewed_count"] == 1
    assert summary["retryable"] is False


def test_figure_with_qc_verdict_is_ready_only_when_qc_enabled(monkeypatch) -> None:
    state = _state(_figure({"status": "ready"}))
    monkeypatch.setenv("V3_VISUAL_QC_ENABLED", "true")
    assert visual_quality_summary(state)["status"] == "ready"
    monkeypatch.setenv("V3_VISUAL_QC_ENABLED", "false")
    assert visual_quality_summary(state)["status"] == "unreviewed"


def test_document_revision_reads_page_document_revision() -> None:
    assert _document_revision({"page_document_v2": {"document_revision": 3}}) == 3
    assert _document_revision({"page_document_v2": {}}) == 0
    assert _document_revision({}) is None


def _rec(qc_state: str, *, failed: bool = False, node: str = "fig"):
    from document.shared_lesson.realization_source import FigureQcRecord

    return FigureQcRecord(node, qc_state, failed=failed)


def test_shared_document_figures_without_qc_are_unreviewed_not_ready() -> None:
    from print.generation.whole_lesson.visual_quality import visual_quality_from_figure_qc

    summary = visual_quality_from_figure_qc([_rec("unreviewed", node=f"f{i}") for i in range(4)])
    assert summary["status"] == "unreviewed"
    assert summary["unreviewed_count"] == 4


def test_shared_document_ready_only_when_all_figures_passed() -> None:
    from print.generation.whole_lesson.visual_quality import visual_quality_from_figure_qc

    assert visual_quality_from_figure_qc([_rec("passed"), _rec("passed")])["status"] == "ready"
    assert visual_quality_from_figure_qc([_rec("passed"), _rec("unavailable")])["status"] == "unreviewed"


def test_shared_document_flagged_and_failed_take_precedence() -> None:
    from print.generation.whole_lesson.visual_quality import visual_quality_from_figure_qc

    flagged = visual_quality_from_figure_qc([_rec("flagged", node="a"), _rec("unreviewed", node="b")])
    assert flagged["status"] == "ready_with_quality_warning"
    assert flagged["flagged_count"] == 1 and flagged["retryable"] is True
    failed = visual_quality_from_figure_qc([_rec("passed"), _rec("unreviewed", failed=True, node="x")])
    assert failed["status"] == "failed"
    assert failed["failed_request_ids"] == ["x"]
