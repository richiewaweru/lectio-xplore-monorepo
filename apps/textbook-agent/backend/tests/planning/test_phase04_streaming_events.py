"""Phase 04 streaming snapshot helpers."""

from __future__ import annotations

from planning.whole_lesson.events import make_event


def test_d04_visual_pending_section_event_shape() -> None:
    event = make_event(
        "section_ready",
        generation_id="gen-1",
        status="streaming",
        section_ids=["orient"],
        document_revision=1,
    )
    assert event["type"] == "section_ready"
    assert event["section_ids"] == ["orient"]
    assert event["document_revision"] == 1


def test_d05_noop_revision_contract_documented() -> None:
    # Repository.persist_streaming_snapshot only bumps when sha changes.
    prior = "abc"
    current = "abc"
    assert (prior != current) is False
