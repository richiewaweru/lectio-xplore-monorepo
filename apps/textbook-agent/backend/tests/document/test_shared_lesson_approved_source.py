from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from core.database.models import (
    ConceptModel,
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from curriculum.planning.objective_ownership import hash_path_objective
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import LearnerActionBrief, TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_approved_item_snapshot,
    make_approved_source_verifier,
)
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _plan(
    *, plan_id: str = "plan-1", revision: int = 1, source_question_ids: list[str] | None = None
) -> TeachingPlan:
    source_ids = list(source_question_ids or [])
    return TeachingPlan(
        contract_version=2,
        teaching_plan_id=plan_id,
        revision=revision,
        preparation_hash="preparation-hash",
        approval_status="pending",
        learner_title="How water reaches a leaf",
        arc="Trace water movement from roots to leaves.",
        starting_state=["Learner can name a root."],
        target_state=["Learner can explain water movement."],
        sections=[
            {
                "slot_id": "orient",
                "display_title": "Start with the root",
                "specific_purpose": "Connect the observation to the question.",
                "entry_state": ["Learner can name a root."],
                "must_establish": ["Roots take in water."],
                "avoid_repeating": [],
                "bridge_from_previous": None,
                "exit_state": ["Learner can describe root uptake."],
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Observe a plant root.",
                        "evidence": "Learner identifies the root.",
                        "source_question_ids": source_ids,
                        "task_mode": "assessment" if source_ids else "none",
                        "learner_action": (
                            LearnerActionBrief(
                                action="select-one",
                                target="the root",
                                purpose="Check the root idea",
                                expected_evidence="Learner identifies the root.",
                                difficulty="guided",
                            )
                            if source_ids
                            else None
                        ),
                    }
                ],
            }
        ],
    )


async def _prepared(
    db_session,
    *,
    user_id: str = "source-owner",
    with_item: bool = False,
):
    user = UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id)
    unit = UnitModel(
        id=f"unit-{user_id}",
        owner_id=user_id,
        title="Water movement",
        topic="Plants",
        subject="Science",
        grade_level="4",
        destination_objective="Explain water movement.",
    )
    concept = ConceptModel(
        id=f"concept-{user_id}",
        canonical_slug=f"water-{user_id}",
        subject="Science",
        title="Water movement",
        created_by=user_id,
    )
    version = PathVersionModel(
        id=f"version-{user_id}",
        unit_id=unit.id,
        version=1,
        source_plan_json={"lessons": []},
        status="approved",
    )
    lesson = PathLessonModel(
        id=f"lesson-{user_id}",
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug="water-movement",
        title="Water movement",
        objective="Explain how water reaches a leaf.",
        objective_hash=hash_path_objective("Explain how water reaches a leaf."),
        primary_knowledge_type="conceptual",
        position=0,
        revision=3,
    )
    source_ids = ["item-a"] if with_item else []
    plan = _plan(plan_id=f"plan-{user_id}", source_question_ids=source_ids)
    page_state: dict[str, object] = (
        {
            "lesson_packet": {
                "approved_items": [
                    {
                        "id": "item-a",
                        "card_id": "card-a",
                        "stem": "Approved question",
                        "options": [{"key": "A", "text": "Correct"}],
                        "correct_key": "A",
                        "diagnoses": {},
                    }
                ]
            }
        }
        if with_item
        else {}
    )
    store = TeachingRevisionStore(page_state)
    store.record_draft(plan, preparation_hash="preparation-hash", revision=1)
    record = store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
        reviewed_by=user_id,
    )
    generation_id = f"prep-{user_id}"
    generation = GenerationModel(
        id=generation_id,
        user_id=user_id,
        subject="Science",
        context="shared preparation",
        status="awaiting_review",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=_now(),
        chunked_state_json={"page_document_v2": page_state},
    )
    lesson.pack_id = generation_id
    provenance = LessonProvenanceModel(
        pack_id=generation_id,
        path_version_id=version.id,
        path_lesson_id=lesson.id,
        objective_hash=lesson.objective_hash,
        path_lesson_revision=lesson.revision,
    )
    db_session.add_all([user, unit, concept, version, lesson, generation, provenance])
    await db_session.flush()
    source = TeachingPlanSource(
        plan=TeachingPlan.model_validate(record.plan),
        revision_record=record,
        id=record.teaching_plan_id,
        revision=record.revision,
        content_hash=record.content_hash or "",
    )
    return generation, lesson, provenance, source


def _verifier(generation: GenerationModel, lesson: PathLessonModel, *, owner: str):
    return make_approved_source_verifier(
        owner_user_id=owner,
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
    )


@pytest.mark.asyncio
async def test_verifier_locks_and_returns_exact_approved_identity(db_session) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    before = deepcopy(generation.chunked_state_json)

    identity = await _verifier(generation, lesson, owner="source-owner")(
        db_session, verify_teaching_plan_source(source)
    )

    assert identity == verify_teaching_plan_source(source)
    refreshed = await db_session.scalar(
        select(GenerationModel).where(GenerationModel.id == generation.id)
    )
    assert refreshed is not None
    assert refreshed.chunked_state_json == before


@pytest.mark.asyncio
async def test_verifier_rejects_foreign_owner_and_path_owner(db_session) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    requested = verify_teaching_plan_source(source)

    with pytest.raises(ApprovedSourceVerificationError, match="unavailable to this owner"):
        await _verifier(generation, lesson, owner="different-owner")(db_session, requested)


@pytest.mark.asyncio
async def test_verifier_rejects_superseded_generation_and_invalidated_provenance(
    db_session,
) -> None:
    generation, lesson, provenance, source = await _prepared(db_session)
    requested = verify_teaching_plan_source(source)

    lesson.pack_id = "newer-preparation"
    with pytest.raises(ApprovedSourceVerificationError, match="current preparation"):
        await _verifier(generation, lesson, owner="source-owner")(db_session, requested)

    lesson.pack_id = generation.id
    provenance.invalidated_at = _now()
    with pytest.raises(ApprovedSourceVerificationError, match="invalidated"):
        await _verifier(generation, lesson, owner="source-owner")(db_session, requested)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["missing", "hashless", "tampered"])
async def test_verifier_rejects_missing_hashless_or_tampered_approval(
    db_session, mutation: str
) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    state = deepcopy(generation.chunked_state_json)
    page = state["page_document_v2"]
    assert isinstance(page, dict)
    if mutation == "missing":
        page["teaching_revisions"] = []
    elif mutation == "hashless":
        page["teaching_revisions"][0]["content_hash"] = None
    else:
        page["teaching_revisions"][0]["plan"]["arc"] = "Forged arc"
    generation.chunked_state_json = state

    with pytest.raises(ApprovedSourceVerificationError):
        await _verifier(generation, lesson, owner="source-owner")(
            db_session, verify_teaching_plan_source(source)
        )


@pytest.mark.asyncio
async def test_verifier_uses_approved_pointer_when_newer_draft_is_pending(db_session) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    page = generation.chunked_state_json["page_document_v2"]
    assert isinstance(page, dict)
    store = TeachingRevisionStore(page)
    newer = _plan(plan_id=source.id, revision=2)
    store.edit_plan(newer, preparation_hash="preparation-hash")

    identity = await _verifier(generation, lesson, owner="source-owner")(
        db_session, verify_teaching_plan_source(source)
    )
    assert identity.source_revision == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["source_artifact_id", "source_revision", "source_hash"])
async def test_verifier_rejects_source_identity_conflicts(db_session, field: str) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session)
    identity = verify_teaching_plan_source(source)
    changes = {
        "source_artifact_id": "other-plan",
        "source_revision": identity.source_revision + 1,
        "source_hash": "0" * 64,
    }
    requested = identity.model_copy(update={field: changes[field]})

    with pytest.raises(ApprovedSourceVerificationError, match="differs"):
        await _verifier(generation, lesson, owner="source-owner")(db_session, requested)


@pytest.mark.asyncio
async def test_loader_returns_revision_bound_snapshot_after_packet_refresh(db_session) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session, with_item=True)
    requested = verify_teaching_plan_source(source)

    snapshot = await load_approved_item_snapshot(
        session=db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        requested=requested,
    )
    assert snapshot.teaching_plan_id == requested.source_artifact_id
    assert snapshot.teaching_plan_revision == requested.source_revision
    assert snapshot.teaching_plan_hash == requested.source_hash
    assert snapshot.items["item-a"]["stem"] == "Approved question"

    refreshed_state = deepcopy(generation.chunked_state_json)
    refreshed_state["page_document_v2"]["lesson_packet"]["approved_items"][0]["stem"] = (
        "Refreshed packet content"
    )
    generation.chunked_state_json = refreshed_state
    reloaded = await load_approved_item_snapshot(
        session=db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        requested=requested,
    )
    assert reloaded.items["item-a"]["stem"] == "Approved question"


@pytest.mark.asyncio
async def test_loader_rejects_legacy_missing_item_snapshot(db_session) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session, with_item=True)
    tampered_state = deepcopy(generation.chunked_state_json)
    page = tampered_state["page_document_v2"]
    assert isinstance(page, dict)
    page["teaching_revisions"][0]["approved_item_snapshot"] = None
    page["teaching_revisions"][0]["approved_item_snapshot_hash"] = None
    generation.chunked_state_json = tampered_state
    await db_session.flush()

    with pytest.raises(ApprovedSourceVerificationError, match="item snapshot"):
        await load_approved_item_snapshot(
            session=db_session,
            owner_user_id="source-owner",
            path_lesson_id=lesson.id,
            preparation_generation_id=generation.id,
            requested=verify_teaching_plan_source(source),
        )


@pytest.mark.asyncio
async def test_loader_rejects_tampered_snapshot_hash_and_requested_lineage(db_session) -> None:
    generation, lesson, _provenance, source = await _prepared(db_session, with_item=True)
    requested = verify_teaching_plan_source(source)
    tampered_state = deepcopy(generation.chunked_state_json)
    page = tampered_state["page_document_v2"]
    assert isinstance(page, dict)
    page["teaching_revisions"][0]["approved_item_snapshot"]["items"]["item-a"]["stem"] = (
        "Forged after approval"
    )
    generation.chunked_state_json = tampered_state
    await db_session.flush()

    with pytest.raises(ApprovedSourceVerificationError, match="snapshot"):
        await load_approved_item_snapshot(
            session=db_session,
            owner_user_id="source-owner",
            path_lesson_id=lesson.id,
            preparation_generation_id=generation.id,
            requested=requested,
        )

    clean_generation, clean_lesson, _provenance, clean_source = await _prepared(
        db_session, user_id="lineage-owner", with_item=True
    )
    clean_requested = verify_teaching_plan_source(clean_source)
    forged = clean_requested.model_copy(update={"source_revision": 2})
    with pytest.raises(ApprovedSourceVerificationError, match="differs"):
        await load_approved_item_snapshot(
            session=db_session,
            owner_user_id="lineage-owner",
            path_lesson_id=clean_lesson.id,
            preparation_generation_id=clean_generation.id,
            requested=forged,
        )
