from __future__ import annotations

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from curriculum.teaching_plan.revisions import (
    TeachingRevisionApprovedItemError,
    TeachingRevisionConflictError,
    TeachingRevisionContentMismatchError,
    TeachingRevisionStore,
    approved_item_snapshot_hash,
    read_approved_item_snapshot,
)


def _plan(*, source_ids: list[str] | None = None) -> TeachingPlan:
    ids = list(source_ids or [])
    block = TeachingPlanBlock(
        id="check-b1",
        position=0,
        intent="check-understanding",
        brief="Check the idea.",
        evidence="Learner identifies the idea.",
        source_question_ids=ids,
        task_mode="assessment" if ids else "none",
        learner_action=(
            LearnerActionBrief(
                action="select-one",
                target="the idea",
                purpose="Check the idea",
                expected_evidence="Learner identifies the idea.",
                difficulty="guided",
            )
            if ids
            else None
        ),
    )
    return TeachingPlan(
        arc="Explain and check the idea",
        sections=[TeachingPlanSection(slot_id="check", blocks=[block])],
    )


def _item(item_id: str = "item-a", *, stem: str = "Approved question") -> dict:
    return {
        "id": item_id,
        "card_id": "card-a",
        "stem": stem,
        "options": [{"key": "A", "text": "Correct"}],
        "correct_key": "A",
        "diagnoses": {},
    }


def _approved(source_ids: list[str] | None = None) -> tuple[dict, TeachingPlan]:
    plan = _plan(source_ids=source_ids)
    state: dict = {
        "lesson_packet": {"approved_items": [_item(item_id) for item_id in (source_ids or [])]}
    }
    store = TeachingRevisionStore(state)
    store.record_draft(plan, preparation_hash="prep-a", revision=1)
    return state, plan


def test_approval_freezes_exact_source_items_and_plan_lineage() -> None:
    state, plan = _approved(["item-a"])
    store = TeachingRevisionStore(state)

    record = store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
    )

    assert record.approved_item_snapshot == {
        "schema_version": 1,
        "teaching_plan_id": record.teaching_plan_id,
        "teaching_plan_revision": 1,
        "teaching_plan_hash": record.content_hash,
        "items": {"item-a": _item()},
    }
    assert record.approved_item_snapshot_hash == approved_item_snapshot_hash(
        record.approved_item_snapshot
    )
    from curriculum.shared_task_authoring import (
        ApprovedItemSnapshot,
    )
    from curriculum.shared_task_authoring import (
        approved_item_snapshot_hash as shared_hash,
    )

    assert record.approved_item_snapshot_hash == shared_hash(
        ApprovedItemSnapshot.model_validate(record.approved_item_snapshot)
    )
    state["lesson_packet"]["approved_items"][0]["stem"] = "Refreshed packet content"
    assert read_approved_item_snapshot(record, state=state) == record.approved_item_snapshot


def test_approval_without_sources_freezes_empty_snapshot() -> None:
    state, plan = _approved()
    record = TeachingRevisionStore(state).approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
    )

    assert record.approved_item_snapshot is not None
    assert record.approved_item_snapshot["items"] == {}
    assert read_approved_item_snapshot(record, state=state)["items"] == {}


@pytest.mark.parametrize(
    ("packet", "message"),
    [
        ({"approved_items": [_item("other-item")]}, "missing source ids"),
        ({"approved_items": [_item(), _item()]}, "duplicate id"),
        ({"approved_items": {"item-a": _item()}}, "must be a list"),
        ({"approved_items": ["item-a"]}, "entries must be objects"),
    ],
)
def test_approval_rejects_invalid_persisted_item_pool(packet: dict, message: str) -> None:
    state = {"lesson_packet": packet}
    plan = _plan(source_ids=["item-a"])
    store = TeachingRevisionStore(state)
    store.record_draft(plan, preparation_hash="prep-a", revision=1)

    with pytest.raises(TeachingRevisionConflictError, match=message):
        store.approve(expected_revision=1)


def test_snapshot_verifier_rejects_item_content_mutation() -> None:
    state, plan = _approved(["item-a"])
    store = TeachingRevisionStore(state)
    store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
    )
    # Mutate the durable approved revision row, leaving the current packet
    # untouched; historical snapshots are verified against their own hash.
    state["teaching_revisions"][0]["approved_item_snapshot"]["items"]["item-a"]["stem"] = (
        "Changed after approval"
    )

    mutated = store.get_revision(1)
    assert mutated is not None
    with pytest.raises(TeachingRevisionContentMismatchError, match="persisted hash"):
        read_approved_item_snapshot(mutated, state=state)


def test_snapshot_verifier_rejects_tampered_snapshot_hash_and_legacy_snapshot() -> None:
    state, plan = _approved(["item-a"])
    store = TeachingRevisionStore(state)
    record = store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
    )
    state["teaching_revisions"][0]["approved_item_snapshot"]["items"]["item-a"]["stem"] = "Tampered"
    tampered = store.get_revision(1)
    assert tampered is not None
    with pytest.raises(TeachingRevisionContentMismatchError, match="persisted hash"):
        read_approved_item_snapshot(tampered)

    legacy = record.model_copy(
        update={"approved_item_snapshot": None, "approved_item_snapshot_hash": None}
    )
    with pytest.raises(TeachingRevisionApprovedItemError, match="no approved item snapshot"):
        read_approved_item_snapshot(legacy)
