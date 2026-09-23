from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.database.models import GenerationModel
from core.entities.user import User
from curriculum.shared_tasks.service import shared_task_for_block
from curriculum.shared_tasks.service import teaching_plan_hash as shared_task_plan_hash
from curriculum.shared_tasks.validation import validate_shared_tasks
from curriculum.teaching_plan.consumers import (
    TeachingRevisionContentError,
    TeachingRevisionNotApprovedError,
    accept_approved_teaching_revision,
    assert_identical_consumer_handoffs,
)
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import (
    TeachingRevisionConflictError,
    TeachingRevisionStore,
)
from learn.generation.native_production import (
    teaching_plan_content_hash as learn_content_hash,
)
from print.generation.native_production import (
    teaching_plan_content_hash as print_content_hash,
)


def _plan(*, arc: str = "Explain water movement") -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id="plan-identity-1",
        revision=1,
        preparation_hash="upstream-input-hash",
        arc=arc,
        misconception_focus_ids=["water-cycle-order"],
        anchor_usage=[{"slot_id": "orient", "usage": "Observe a covered leaf."}],
        sections=[
            {
                "slot_id": "orient",
                "specific_purpose": "Connect the observation to the question.",
                "transition": "Now trace the water.",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Describe what the learner sees.",
                        "evidence": "A relevant observation.",
                    }
                ],
            }
        ],
    )


def _approved_state() -> dict:
    state: dict = {}
    store = TeachingRevisionStore(state)
    plan = _plan()
    store.record_draft(plan, preparation_hash="upstream-input-hash", revision=1)
    store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
        reviewed_by="teacher-1",
    )
    return state


def test_canonical_hash_includes_every_pedagogical_field_but_excludes_identity_metadata() -> None:
    plan = _plan()
    original_hash = teaching_plan_content_hash(plan)
    print_hash = print_content_hash(plan)
    learn_hash = learn_content_hash(plan)

    assert original_hash == print_hash == learn_hash
    assert (
        teaching_plan_content_hash(
            plan.model_copy(
                update={
                    "teaching_plan_id": "different-id",
                    "revision": 9,
                    "preparation_hash": "different-upstream-input",
                    "approval_status": "approved",
                }
            )
        )
        == original_hash
    )
    assert (
        teaching_plan_content_hash(
            plan.model_copy(update={"misconception_focus_ids": ["different-misconception"]})
        )
        != original_hash
    )


def test_shared_task_reuse_invalidates_when_content_changes_at_same_preparation_hash() -> None:
    plan_payload = _plan().model_dump(mode="json")
    plan_payload["sections"][0]["blocks"][0]["learner_action"] = {
        "action": "enter-text",
        "target": "one stage",
        "purpose": "Check the concept.",
        "expected_evidence": "A correct stage.",
        "difficulty": "independent",
    }
    plan = TeachingPlan.model_validate(plan_payload)
    old_task = shared_task_for_block(plan, plan.sections[0].blocks[0])
    changed_plan = plan.model_copy(update={"arc": "Same inputs, changed approved meaning."})

    assert changed_plan.preparation_hash == plan.preparation_hash
    assert shared_task_plan_hash(changed_plan) != old_task.teaching_plan_hash
    assert any(
        "wrong teaching_plan_hash" in error
        for error in validate_shared_tasks(changed_plan, [old_task])
    )


def test_approval_rejects_stale_revision_and_displayed_content_hash() -> None:
    state: dict = {}
    store = TeachingRevisionStore(state)
    plan = _plan()
    store.record_draft(plan, preparation_hash="upstream-input-hash", revision=1)

    with pytest.raises(TeachingRevisionConflictError, match="stale teaching revision"):
        store.approve(expected_revision=2, expected_content_hash=teaching_plan_content_hash(plan))
    with pytest.raises(
        TeachingRevisionConflictError, match="displayed Teaching Plan content changed"
    ):
        store.approve(expected_revision=1, expected_content_hash="old-browser-bytes")

    assert state["teaching_review"]["status"] == "pending"
    assert state["teaching_review"].get("approved_revision") is None


def test_approval_rejects_same_revision_replacement_and_persists_snapshot_digest() -> None:
    state: dict = {}
    store = TeachingRevisionStore(state)
    plan = _plan()
    store.record_draft(plan, preparation_hash="upstream-input-hash", revision=1)
    state["teaching_plan"]["arc"] = "Replacement bytes in the same revision"

    with pytest.raises(TeachingRevisionConflictError, match="differ from the pending revision"):
        store.approve(expected_revision=1)

    state["teaching_plan"] = dict(store.get_revision(1).plan)
    expected_hash = teaching_plan_content_hash(plan)
    approved = store.approve(expected_revision=1, expected_content_hash=expected_hash)
    assert approved.content_hash == expected_hash
    assert approved.approval_hash_binding == "submitted"
    assert teaching_plan_content_hash(approved.plan) == expected_hash


def test_print_and_learn_pin_same_approved_snapshot_hash() -> None:
    state = _approved_state()
    print_plan = accept_approved_teaching_revision(state, consumer="print")
    learn_plan = accept_approved_teaching_revision(state, consumer="learn")

    assert print_plan.model_dump(mode="json") == learn_plan.model_dump(mode="json")
    assert state["teaching_consumer_handoffs"]["print"][
        "content_hash"
    ] == teaching_plan_content_hash(print_plan)
    assert (
        state["teaching_consumer_handoffs"]["print"]["content_hash"]
        == state["teaching_consumer_handoffs"]["learn"]["content_hash"]
    )
    assert_identical_consumer_handoffs(state)


def test_older_approved_snapshot_remains_readable_by_explicit_revision_after_new_approval() -> None:
    state: dict = {}
    store = TeachingRevisionStore(state)
    first = _plan(arc="Original approved arc")
    store.record_draft(first, preparation_hash="prep-1", revision=1)
    first_hash = teaching_plan_content_hash(first)
    store.approve(expected_revision=1, expected_content_hash=first_hash)

    second = _plan(arc="New approved arc")
    store.edit_plan(second, preparation_hash="prep-2")
    second_hash = teaching_plan_content_hash(second)
    store.approve(expected_revision=2, expected_content_hash=second_hash)

    first_record = store.get_revision(1)
    assert first_record is not None
    assert first_record.status == "superseded"
    assert first_record.content_hash == first_hash
    pinned = accept_approved_teaching_revision(state, consumer="print", revision=1)
    current = accept_approved_teaching_revision(state, consumer="learn")
    assert pinned.arc == "Original approved arc"
    assert teaching_plan_content_hash(pinned) == first_hash
    assert current.arc == "New approved arc"


@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_consumer_rejects_missing_or_mismatched_persisted_approval_hash(mutation: str) -> None:
    state = _approved_state()
    row = state["teaching_revisions"][0]
    if mutation == "missing":
        row["content_hash"] = None
    else:
        row["plan"]["arc"] = "mutated after approval"

    with pytest.raises(TeachingRevisionContentError) as error:
        accept_approved_teaching_revision(state, consumer="learn")
    assert error.value.code in {
        "TEACHING_CONTENT_HASH_UNAVAILABLE",
        "TEACHING_CONTENT_HASH_MISMATCH",
    }


def test_consumer_rejects_missing_approval_pointer_or_ledger_row() -> None:
    with pytest.raises(TeachingRevisionNotApprovedError):
        accept_approved_teaching_revision({}, consumer="print")

    state = {
        "teaching_review": {"status": "approved", "revision": 2, "approved_revision": 1},
        "teaching_revisions": [],
    }
    with pytest.raises(ValueError, match="approved teaching revision 1 missing"):
        accept_approved_teaching_revision(state, consumer="learn")


@pytest.mark.asyncio
async def test_lesson_approach_get_separates_plan_review_and_identity(
    db_session_factory, monkeypatch
) -> None:
    import application.unit_lesson.native_http as native_http

    state: dict = {}
    plan = _plan()
    store = TeachingRevisionStore(state)
    store.record_draft(plan, preparation_hash="upstream-input-hash", revision=1)
    generation = GenerationModel(
        id="p2-lesson-approach-get",
        user_id="p2-get-user",
        subject="science",
        requested_template_id="lesson",
        requested_preset_id="balanced",
        status="awaiting_teaching_approval",
        chunked_state_json={"page_document_v2": state},
    )
    async with db_session_factory() as session:
        session.add(generation)
        await session.commit()

    monkeypatch.setattr(native_http, "async_session_factory", db_session_factory)
    monkeypatch.setattr(
        native_http,
        "_load_owned_generation",
        AsyncMock(return_value=generation),
    )
    response = await native_http.get_lesson_approach(
        generation.id,
        User(
            id=generation.user_id,
            email="p2@example.invalid",
            name="P2 Teacher",
            created_at="2026-09-22T00:00:00Z",
            updated_at="2026-09-22T00:00:00Z",
        ),
    )

    assert response["teaching_plan"]["arc"] == plan.arc
    assert response["teaching_review"]["status"] == "pending"
    assert response["teaching_plan_identity"]["revision"] == 1
    assert response["teaching_plan_identity"]["pending_content_hash"] == teaching_plan_content_hash(
        plan
    )
    assert response["teaching_plan_identity"]["pending_hash_verified"] is True


@pytest.mark.asyncio
async def test_active_lesson_approval_rejects_missing_content_hash(monkeypatch) -> None:
    from fastapi import HTTPException

    import application.unit_lesson.native_http as native_http
    from core.entities.user import User

    monkeypatch.setattr(
        native_http,
        "_load_owned_generation",
        AsyncMock(return_value=GenerationModel(id="missing-hash", user_id="teacher")),
    )
    body = native_http.LessonApproachApproveRequest(expected_revision=1)
    teacher = User(
        id="teacher",
        email="teacher@example.invalid",
        name="Teacher",
        created_at="2026-09-22T00:00:00Z",
        updated_at="2026-09-22T00:00:00Z",
    )

    with pytest.raises(HTTPException) as raised:
        await native_http.post_lesson_approach_approve("missing-hash", body, teacher)

    assert raised.value.status_code == 409
    assert raised.value.detail == {
        "code": "TEACHING_CONTENT_HASH_REQUIRED",
        "message": "Reload the Teaching Plan review and approve the displayed version.",
        "recovery_action": "reload_review",
    }
