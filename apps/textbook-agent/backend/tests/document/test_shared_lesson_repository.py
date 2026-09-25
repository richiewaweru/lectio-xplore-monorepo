from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import select, update

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson import build_shared_lesson_document
from document.shared_lesson.assembly import SharedLessonAssemblyResult
from document.shared_lesson.qa import DocumentQAResult
from document.shared_lesson.repository import (
    SharedLessonDocumentConflict,
    SharedLessonDocumentIntegrityError,
    SharedLessonDocumentNotFound,
    SharedLessonDocumentReadinessError,
    load_shared_lesson_document,
    load_verified_shared_lesson_artifact,
    promote_shared_lesson_document,
    save_shared_lesson_document,
    verify_shared_lesson_source,
)
from document.shared_lesson.runtime import TeachingPlanSource
from infra.database.models import SharedLessonDocumentModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.contracts import SourceIdentity

PLAN_HASH = "a" * 64


def _payload(*, title: str = "Photosynthesis", document_id: str = "lesson-1") -> dict[str, object]:
    return {
        "id": document_id,
        "revision": 1,
        "teaching_plan_id": "plan-1",
        "teaching_plan_revision": 3,
        "teaching_plan_hash": PLAN_HASH,
        "title": title,
        "sections": [
            {
                "id": "section-1",
                "title": "How plants make food",
                "position": 0,
                "nodes": [
                    {
                        "id": "paragraph-1",
                        "kind": "paragraph",
                        "display": {"text": "Plants use light."},
                    }
                ],
            }
        ],
        "created_at": "2026-09-24T09:00:00+03:00",
    }


def _document(**kwargs):
    return build_shared_lesson_document(_payload(**kwargs))


def _approved_source_and_document(*, include_figure: bool = False):
    section = TeachingPlanSection(
        slot_id="section-1",
        specific_purpose="Explain how plants make food",
        display_title="How plants make food",
        entry_state=["Learner is ready to learn"],
        must_establish=["Learner understands how plants make food"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["Learner can explain how plants make food"],
        blocks=[],
    )
    plan = TeachingPlan(
        arc="Teach photosynthesis",
        contract_version=2,
        learner_title="How plants make food",
        starting_state=["Learner is ready to learn"],
        target_state=["Learner can explain photosynthesis"],
        teaching_plan_id="plan-1",
        revision=3,
        sections=[section],
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    source = TeachingPlanSource(
        plan=plan,
        revision_record=TeachingRevisionRecord(
            teaching_plan_id="plan-1",
            revision=3,
            status="approved",
            preparation_hash="preparation-hash",
            content_hash=digest,
            plan=plan.model_dump(mode="json"),
            created_at="2026-09-24T09:00:00Z",
            approved_at="2026-09-24T09:01:00Z",
            reviewed_by="teacher-1",
            approval_hash_binding="submitted",
        ),
        id="plan-1",
        revision=3,
        content_hash=digest,
    )
    nodes = [
        {
            "id": "paragraph-1",
            "kind": "paragraph",
            "display": {"text": "Plants use light to make food."},
        }
    ]
    if include_figure:
        nodes.append(
            {
                "id": "figure-1",
                "kind": "figure",
                "display": {"caption": "A plant using light"},
                "accessibility": {"alt_text": "A plant using light"},
            }
        )
    document = build_shared_lesson_document(
        {
            **_payload(title=plan.learner_title),
            "teaching_plan_hash": digest,
            "sections": [
                {
                    "id": "section-1",
                    "title": "How plants make food",
                    "position": 0,
                    "nodes": nodes,
                }
            ],
        }
    )
    return source, document


def _ready_assembly(document):
    return SharedLessonAssemblyResult(
        document=document,
        qa=DocumentQAResult(document_id=document.id, document_revision=document.revision),
        status="ready",
    )


@pytest.mark.asyncio
async def test_exact_duplicate_save_is_idempotent(db_session) -> None:
    document = _document()

    first = await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )
    second = await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )

    assert second == first
    assert second.status == "draft"
    assert second.storage_hash == content_hash(document.model_dump(mode="json"))
    assert (
        await db_session.scalar(
            select(SharedLessonDocumentModel.revision).where(
                SharedLessonDocumentModel.id == document.id
            )
        )
        == document.revision
    )


@pytest.mark.asyncio
async def test_same_identity_conflicting_content_or_path_is_rejected(db_session) -> None:
    document = _document()
    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)

    with pytest.raises(SharedLessonDocumentConflict, match="different content"):
        await save_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            document=_document(title="Changed title"),
        )
    with pytest.raises(SharedLessonDocumentIntegrityError, match="different lesson"):
        await save_shared_lesson_document(
            db_session, path_lesson_id="path-lesson-2", document=document
        )


@pytest.mark.asyncio
async def test_loader_rejects_corrupted_json_and_explicit_lineage(db_session) -> None:
    document = _document()
    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)

    changed_json = deepcopy(document.model_dump(mode="json"))
    changed_json["title"] = "Corrupted"
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(document_json=changed_json)
    )
    db_session.expire_all()
    with pytest.raises(
        SharedLessonDocumentIntegrityError, match="content hash|canonical|validation"
    ):
        await load_shared_lesson_document(
            db_session, document_id=document.id, revision=document.revision
        )

    await db_session.rollback()
    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(teaching_plan_hash="b" * 64)
    )
    db_session.expire_all()
    with pytest.raises(SharedLessonDocumentIntegrityError, match="teaching_plan_hash"):
        await load_shared_lesson_document(
            db_session, document_id=document.id, revision=document.revision
        )


@pytest.mark.asyncio
async def test_ready_rows_are_immutable_at_repository_event_boundary(db_session) -> None:
    document = _document()
    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(status="ready")
    )
    await db_session.commit()
    db_session.expire_all()
    ready = await db_session.get(
        SharedLessonDocumentModel, {"id": document.id, "revision": document.revision}
    )
    assert ready is not None
    ready.document_json = {**document.model_dump(mode="json"), "title": "Mutation"}
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
    await db_session.rollback()
    ready = await db_session.get(
        SharedLessonDocumentModel, {"id": document.id, "revision": document.revision}
    )
    assert ready is not None
    await db_session.delete(ready)
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()


@pytest.mark.asyncio
async def test_trusted_runtime_adapters_recompute_source_and_artifact_identity(db_session) -> None:
    document = _document()
    stored = await save_shared_lesson_document(
        db_session, path_lesson_id="path-lesson-1", document=document
    )
    source = SourceIdentity(
        source_artifact_type="shared_lesson_document",
        source_artifact_id=document.id,
        source_revision=document.revision,
        source_hash=document.content_hash,
    )

    assert await verify_shared_lesson_source(db_session, source) == source
    with pytest.raises(SharedLessonDocumentIntegrityError, match="only ready"):
        await load_verified_shared_lesson_artifact(
            db_session, "shared_lesson_document", document.id, document.revision
        )
    await db_session.execute(
        update(SharedLessonDocumentModel)
        .where(SharedLessonDocumentModel.id == document.id)
        .values(status="ready")
    )
    await db_session.commit()
    artifact = await load_verified_shared_lesson_artifact(
        db_session, "shared_lesson_document", document.id, document.revision
    )
    assert artifact.output_hash == content_hash(artifact.output_json)
    assert artifact.output_hash == stored.storage_hash

    with pytest.raises(SharedLessonDocumentConflict, match="source hash"):
        await verify_shared_lesson_source(
            db_session,
            source.model_copy(update={"source_hash": "b" * 64}),
        )


@pytest.mark.asyncio
async def test_ready_promotion_requires_approved_source_and_final_qa(db_session) -> None:
    source, document = _approved_source_and_document()
    assembly = _ready_assembly(document)

    with pytest.raises(SharedLessonDocumentNotFound, match="draft must be persisted"):
        await promote_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            source=source,
            assembly=assembly,
        )

    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)
    promoted = await promote_shared_lesson_document(
        db_session,
        path_lesson_id="path-lesson-1",
        source=source,
        assembly=assembly,
    )
    assert promoted.status == "ready"

    replay = await promote_shared_lesson_document(
        db_session,
        path_lesson_id="path-lesson-1",
        source=source,
        assembly=assembly,
    )
    assert replay == promoted


@pytest.mark.asyncio
async def test_ready_promotion_blocks_failed_qa_required_media_and_lineage_conflict(
    db_session,
) -> None:
    source, document = _approved_source_and_document()
    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)

    blocked = SharedLessonAssemblyResult(
        document=document,
        qa=DocumentQAResult(
            document_id=document.id,
            document_revision=document.revision,
            issues=(
                {
                    "issue_code": "required_media_missing",
                    "affected_section_id": "section-1",
                    "explanation": "figure is not ready",
                    "required_correction": "generate the figure",
                },
            ),
        ),
        status="blocked",
    )
    with pytest.raises(SharedLessonDocumentReadinessError, match="final deterministic QA"):
        await promote_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            source=source,
            assembly=blocked,
            required_media_by_section={"section-1": ("figure-1",)},
        )

    with pytest.raises(SharedLessonDocumentReadinessError, match="required media"):
        await promote_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            source=source,
            assembly=_ready_assembly(document),
            required_media_by_section={"section-1": ("figure-1",)},
        )

    with pytest.raises(SharedLessonDocumentReadinessError, match="approved Teaching Plan"):
        await promote_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            source=source.model_copy(update={"content_hash": "b" * 64}),
            assembly=_ready_assembly(document),
        )


@pytest.mark.asyncio
async def test_ready_promotion_derives_required_figures_when_media_map_is_omitted(
    db_session,
) -> None:
    source, document = _approved_source_and_document(include_figure=True)
    await save_shared_lesson_document(db_session, path_lesson_id="path-lesson-1", document=document)

    with pytest.raises(SharedLessonDocumentReadinessError, match="required media"):
        await promote_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            source=source,
            assembly=_ready_assembly(document),
        )

    with pytest.raises(SharedLessonDocumentReadinessError, match="does not match"):
        await promote_shared_lesson_document(
            db_session,
            path_lesson_id="path-lesson-1",
            source=source,
            assembly=_ready_assembly(document),
            required_media_by_section={"section-1": ()},
        )
