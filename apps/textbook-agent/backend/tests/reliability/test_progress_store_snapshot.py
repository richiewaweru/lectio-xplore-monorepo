"""ProgressStore snapshot round-trip (G16 durability scaffolding)."""

from __future__ import annotations

from infra.execution.progress import ProgressStore


def test_progress_store_snapshot_round_trip_preserves_events() -> None:
    store = ProgressStore(event_retention=50)
    store.ensure_run(
        "run-1",
        path="print",
        owner_user_id="user-1",
        status="running",
        stage="writing_sections",
        realization_revision=2,
        teaching_plan_revision=3,
        total=4,
    )
    store.append_event(
        "run-1",
        event_type="print_block_ready",
        path="print",
        stage="writing_sections",
        item_id="block-1",
        attempt=1,
        payload={"object": "prose"},
    )
    store.append_event(
        "run-1",
        event_type="print_block_ready",
        path="print",
        stage="writing_sections",
        item_id="block-2",
        attempt=1,
    )
    snap = store.snapshot("run-1")
    assert snap["next_seq"] == 3
    assert len(snap["events"]) == 2

    restored = ProgressStore(event_retention=50)
    restored.import_run_snapshot(snap)
    status = restored.get_status("run-1")
    assert status.status == "running"
    assert status.stage == "writing_sections"
    assert status.revisions["realization_revision"] == 2
    replay = restored.replay("run-1", after_seq=0)
    assert [event.event_type for event in replay.events] == [
        "print_block_ready",
        "print_block_ready",
    ]
    assert replay.events[0].item_id == "block-1"
