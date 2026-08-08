"""Phase 06: doc_version projection from document_revision."""

from __future__ import annotations

from planning.whole_lesson.native_status import project_native_status


def test_u01_native_status_exposes_document_revision() -> None:
    native = project_native_status(
        "gen-1",
        {
            "page_document_v2": {
                "document_revision": 3,
                "form_plan": {"sections": []},
                "block_execution": {},
                "execution": {"stage": "awaiting_visuals"},
            },
            "stage": "awaiting_visuals",
        },
        {"document_version": 2, "id": "doc-1", "sections": []},
        generation_status="awaiting_visuals",
    )
    assert native is not None
    assert native["document_revision"] == 3
    assert native["document_exists"] is True
    assert native["next_action"] == "wait_visuals"
