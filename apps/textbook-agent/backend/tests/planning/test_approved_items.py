"""Approved item loader tests."""

from __future__ import annotations

from planning.approved_items import ApprovedItemRecord, approved_items_as_writer_records


def test_approved_item_to_writer_record() -> None:
    record = ApprovedItemRecord(
        id="pack:q1",
        card_id="card-1",
        stem="Which plant made food?",
        options=({"key": "A", "text": "Lit"},),
        correct_key="A",
        diagnoses={"B": "common error"},
    )
    payload = approved_items_as_writer_records((record,))[0]
    assert payload["id"] == "pack:q1"
    assert payload["prompt"] == record.stem
    assert payload["stem"] == record.stem
