from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from document.shared_lesson.document_semantic import (
    DocumentSemanticQAResult,
    DocumentSemanticVerdict,
)
from document.shared_lesson.qa import DocumentQAResult
from document.shared_lesson.qa_runtime import (
    DOCUMENT_QA_ITEM_KEY,
    DOCUMENT_QA_STAGE,
    DocumentQAOutputError,
    DocumentQARuntimeError,
    DocumentQAWorkItemJob,
    DocumentQAWorkItemOutput,
    admit_document_qa_work_item,
    admit_repaired_document_qa_work_item,
    execute_document_qa_work_item,
    load_verified_document_qa,
)
from document.shared_lesson.runtime import TeachingPlanSource
from infra.database.models import (
    ConceptModel,
    GenerationEventModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.generation_runtime import (
    BuildAdmission,
    InvalidWorkItemTransition,
    RunAdmission,
    RunType,
    WorkItemConflict,
    admit_run,
    create_build,
    retry_work_item,
)


def _source_and_document():
    # Reuse the repository contract fixture so this package stays bound to the
    # same approved plan and canonical document builders as the finalizer.
    from test_shared_lesson_repository import _approved_source_and_document

    return _approved_source_and_document()


async def _seed_run(session, source: TeachingPlanSource, *, suffix: str = "qa"):
    owner = f"qa-owner-{suffix}"
    lesson = f"qa-lesson-{suffix}"
    user = UserModel(id=owner, email=f"{owner}@example.invalid")
    concept = ConceptModel(
        id=f"qa-concept-{suffix}",
        canonical_slug=f"qa.{suffix}",
        subject="Science",
        title="QA fixture",
        created_by=owner,
    )
    unit = UnitModel(
        id=f"qa-unit-{suffix}",
        owner_id=owner,
        title="QA fixture",
        topic="QA",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Validate document QA.",
    )
    version = PathVersionModel(
        id=f"qa-path-{suffix}", unit_id=unit.id, version=1, source_plan_json={}
    )
    path_lesson = PathLessonModel(
        id=lesson,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="QA fixture",
        objective="Validate document QA.",
        objective_hash="qa-objective",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all([user, concept, unit, version, path_lesson])
    await session.flush()
    build = await create_build(session, BuildAdmission(owner_user_id=owner, path_lesson_id=lesson))
    admitted = await admit_run(
        session,
        RunAdmission(
            build_id=build.id,
            owner_user_id=owner,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=f"qa-request-{suffix}",
            stage=DOCUMENT_QA_STAGE,
            source_artifact_type="teaching_plan",
            source_artifact_id=source.id,
            source_revision=source.revision,
            source_hash=source.content_hash,
        ),
    )
    return owner, admitted.record.id


def _deterministic(document, *, ready: bool = True):
    return DocumentQAResult(
        document_id=document.id,
        document_revision=document.revision,
        issues=()
        if ready
        else (
            {
                "issue_code": "bad_document",
                "affected_section_id": document.sections[0].id,
                "explanation": "bad",
                "required_correction": "repair",
            },
        ),
    )


async def _pass(_request):
    return DocumentSemanticVerdict(status="pass")


@pytest.mark.asyncio
async def test_document_qa_admission_is_gated_and_idempotent(db_session):
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source)
    deterministic = _deterministic(document)

    first = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=deterministic,
    )
    second = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=deterministic,
    )
    assert first.created is True
    assert second.created is False
    assert first.record.id == second.record.id
    assert first.record.item_key == DOCUMENT_QA_ITEM_KEY

    with pytest.raises(DocumentQARuntimeError, match="deterministic QA"):
        await admit_document_qa_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document, ready=False),
        )


@pytest.mark.asyncio
async def test_document_qa_executes_one_call_and_loader_revalidates_pass(db_session):
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="pass")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )
    calls = 0

    async def provider(_request):
        nonlocal calls
        calls += 1
        return DocumentSemanticVerdict(status="pass")

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=provider,
        )
    )
    assert calls == 1
    assert outcome.qa is not None
    verified = await load_verified_document_qa(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
    )
    assert verified.work_item_id == admitted.record.id
    assert verified.semantic_qa.passed


@pytest.mark.asyncio
async def test_document_qa_provider_output_failure_is_recoverable_and_no_fallback(db_session):
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="malformed")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )
    calls = 0

    async def malformed(_request):
        nonlocal calls
        calls += 1
        return {"status": "pass", "issues": ({"unexpected": True},)}

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=malformed,
        )
    )
    assert calls == 1
    assert outcome.qa is None
    item = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert item is not None
    assert item.status == "failed_recoverable"
    assert item.error_class == "provider_output"


@pytest.mark.asyncio
async def test_document_qa_transport_retry_and_configuration_fail_closed(db_session):
    source, document = _source_and_document()

    owner, run_id = await _seed_run(db_session, source, suffix="transport")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )

    async def transport(_request):
        raise TimeoutError("provider timed out")

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker-transport",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=transport,
        )
    )
    assert outcome.error_code == "document_qa_provider_transport"
    transport_item = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert transport_item is not None
    assert transport_item.status == "failed_recoverable"

    owner, run_id = await _seed_run(db_session, source, suffix="auth")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )

    class AuthError(RuntimeError):
        pass

    async def configuration(_request):
        raise AuthError("provider credentials unavailable")

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker-auth",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=configuration,
        )
    )
    assert outcome.error_code == "document_qa_configuration"
    config_item = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert config_item is not None
    assert config_item.status == "failed_terminal"


@pytest.mark.asyncio
async def test_document_qa_semantic_issue_never_becomes_ready(db_session):
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="issue")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )

    async def issue(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": document.sections[0].id,
                    "explanation": "The section assumes an unapproved fact.",
                    "required_correction": "Repair the affected section input.",
                },
            ),
        )

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=issue,
        )
    )
    assert outcome.qa is None
    item = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert item is not None
    assert item.status == "failed_recoverable"
    with pytest.raises(InvalidWorkItemTransition, match="recovery action"):
        await retry_work_item(
            db_session,
            work_item_id=admitted.record.id,
            owner_user_id=owner,
        )
    issue_events = list(
        (
            await db_session.scalars(
                select(GenerationEventModel)
                .where(GenerationEventModel.work_item_id == admitted.record.id)
                .order_by(GenerationEventModel.seq)
            )
        ).all()
    )
    assert issue_events[-1].event_type == "document_qa_semantic_issues"
    assert issue_events[-1].safe_payload_json["issues"][0]["affected_section_id"] == "section-1"
    repaired = document.model_copy(update={"revision": document.revision + 1})
    replacement = await admit_repaired_document_qa_work_item(
        db_session,
        predecessor_work_item_id=admitted.record.id,
        owner_user_id=owner,
        source=source,
        document=repaired,
        deterministic_qa=_deterministic(repaired),
    )
    assert replacement.replaces_work_item_id == admitted.record.id
    assert replacement.item_key.startswith(f"{DOCUMENT_QA_ITEM_KEY}:")
    assert replacement.id != admitted.record.id
    with pytest.raises(DocumentQAOutputError, match="not ready"):
        await load_verified_document_qa(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            document=document,
        )


@pytest.mark.asyncio
async def test_document_qa_rejects_changed_document_identity_and_tampered_output(db_session):
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="identity")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )
    changed = document.model_copy(update={"revision": document.revision + 1})
    with pytest.raises(WorkItemConflict):
        await admit_document_qa_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            document=changed,
            deterministic_qa=DocumentQAResult(
                document_id=changed.id, document_revision=changed.revision
            ),
        )
    await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=_pass,
        )
    )
    item = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert item is not None
    item.output_json["document_hash"] = "f" * 64
    with pytest.raises(DocumentQAOutputError, match="output hash changed"):
        await load_verified_document_qa(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            document=document,
        )


def test_document_qa_output_is_closed_and_bound():
    with pytest.raises(ValidationError):
        DocumentQAWorkItemOutput(
            source_plan_id="plan",
            source_plan_revision=1,
            source_plan_hash="a" * 64,
            document_id="doc",
            document_revision=1,
            document_hash="b" * 64,
            semantic_qa=DocumentSemanticQAResult(
                document_id="other",
                document_revision=1,
                document_hash="b" * 64,
                status="pass",
                semantic_calls=1,
            ),
        )
